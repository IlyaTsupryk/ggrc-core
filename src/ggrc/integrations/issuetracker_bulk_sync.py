# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Bulk IssueTracker issues creation functionality."""

import collections
import datetime
import logging

from werkzeug import exceptions

import sqlalchemy as sa
from sqlalchemy.sql import expression as expr

from ggrc import models, db, login
from ggrc.app import app
from ggrc.integrations import integrations_errors, issues
from ggrc.integrations.synchronization_jobs import sync_utils
from ggrc.models import all_models, inflector
from ggrc.models import exceptions as ggrc_exceptions
from ggrc.models.hooks.issue_tracker import integration_utils
from ggrc import utils
from ggrc.rbac import permissions
from ggrc.utils import benchmark

logger = logging.getLogger(__name__)

# IssueTracker sync errors
WRONG_COMPONENT_ERR = "Component {} does not exist"
WRONG_HOTLIST_ERR = "No Hotlist with id: {}"


class IssueTrackerBulkCreator(object):
  """Class with methods for bulk tickets creation in issuetracker."""

  # IssueTracker integration modules with handlers for specific models
  INTEGRATION_HANDLERS = {
      "Assessment": models.hooks.issue_tracker.assessment_integration,
      "Issue": models.hooks.issue_tracker.issue_integration,
  }

  def __init__(self):
    self.break_on_errs = False
    self.client = issues.Client()

  def sync_issuetracker(self, objects_data):
    """Generate IssueTracker issues in bulk.

    Args:
        objects. ([object_type, object_id, hotlist_ids, component_id])

    Returns:
        flask.wrappers.Response - response with result of generation.
    """
    issuetracked_info = []
    with benchmark("Load issuetracked objects from database"):
      objects_info = self.group_objs_by_type(objects_data)
      for obj_type, obj_id_info in objects_info.items():
        for obj in self.get_issuetracked_objects(obj_type, obj_id_info.keys()):
          issuetracked_info.append(
              IssuetrackedObjInfo(obj, *obj_id_info[obj.id])
          )

    created, errors = self.handle_issuetracker_sync(issuetracked_info)

    logger.info(
        "Synchronized issues count: %s, failed count: %s",
        len(created),
        len(errors)
    )
    return self.make_response(errors)

  @staticmethod
  def group_objs_by_type(object_data):
    """Group objects data by obj type."""
    objects_info = collections.defaultdict(dict)
    for obj in object_data:
      objects_info[obj.get("type")][obj.get("id")] = (
          obj.get("hotlist_ids"),
          obj.get("component_id"),
      )
    return objects_info

  @staticmethod
  def get_issuetracked_objects(obj_type, obj_ids):
    """Fetch issuetracked objects from db."""
    issuetracked_model = inflector.get_model(obj_type)
    return issuetracked_model.query.join(
        all_models.IssuetrackerIssue,
        sa.and_(
            all_models.IssuetrackerIssue.object_type == obj_type,
            all_models.IssuetrackerIssue.object_id == issuetracked_model.id
        )
    ).filter(
        all_models.IssuetrackerIssue.object_id.in_(obj_ids),
        all_models.IssuetrackerIssue.issue_id.is_(None),
    ).options(
        sa.orm.Load(issuetracked_model).undefer_group(
            "{}_complete".format(obj_type),
        )
    )

  def handle_issuetracker_sync(self, tracked_objs):
    """Create IssueTracker issues for tracked objects in bulk.

    Args:
        tracked_objs: [(object_type, object_id)][object] - tracked object info.

    Returns:
        Tuple with dicts of created issue info and errors.
    """
    errors = []
    created = {}

    # IssueTracker server api doesn't support collection post, thus we
    # create issues in loop.
    for obj_info in tracked_objs:
      try:
        if not self.bulk_sync_allowed(obj_info.obj):
          raise exceptions.Forbidden()

        issue_json = self._get_issue_json(obj_info.obj)
        self._populate_issue_json(obj_info, issue_json)

        issue_id = getattr(obj_info.obj.issuetracker_issue, "issue_id", None)
        with benchmark("Synchronize issue for {} with id {}".format(
            obj_info.obj.type, obj_info.obj.id
        )):
          res = self.sync_issue(issue_json, issue_id)

        self._process_result(res, issue_json)
        created[(obj_info.obj.type, obj_info.obj.id)] = issue_json
      except integrations_errors.Error as error:
        self._add_error(errors, obj_info.obj, error)
        if self.break_on_errs and getattr(error, "data", None) in (
            WRONG_HOTLIST_ERR.format(issue_json["hotlist_ids"][0]),
            WRONG_COMPONENT_ERR.format(issue_json["component_id"]),
        ):
          break
      except (TypeError, ValueError, ggrc_exceptions.ValidationError,
              exceptions.Forbidden) as error:
        self._add_error(errors, obj_info.obj, error)

    with benchmark("Update issuetracker issues in db"):
      self.update_db_issues(created)
    return created, errors

  def _get_issue_json(self, object_):
    """Get json data for issuetracker issue related to provided object."""
    issue_json = None
    integration_handler = self.INTEGRATION_HANDLERS.get(object_.type)
    if hasattr(integration_handler, "prepare_issue_json"):
      issue_json = integration_handler.prepare_issue_json(object_)

    if not issue_json:
      raise integrations_errors.Error(
          "Can't create issuetracker issue json for {}".format(object_.type)
      )
    return issue_json

  @staticmethod
  def _populate_issue_json(obj_info, issue_json):
    """Populate issue json with parameters from request."""
    if obj_info.hotlist_ids:
      issue_json["hotlist_ids"] = obj_info.hotlist_ids
    if obj_info.component_id:
      issue_json["component_id"] = obj_info.component_id
    integration_utils.normalize_issue_tracker_info(issue_json)

  @staticmethod
  def _process_result(result, issue_json):
    """Process result of issuetracker synchronization."""
    if result and not issue_json.get("issue_id"):
      issue_json["enabled"] = True
      issue_json["issue_id"] = result.get("issueId")
      issue_json["issue_url"] = integration_utils.build_issue_tracker_url(
          result.get("issueId")
      )
    elif not result and not issue_json.get("issue_id"):
      raise integrations_errors.Error("Unknown error")

  @staticmethod
  def _add_error(error_list, object_, error):
    """Save error information"""
    logger.error("Issue sync failed with error: %s", str(error))
    error_list.append((object_, str(error)))

  def sync_issue(self, issue_json, issue_id=None):
    """Create new issue in issuetracker with provided params."""
    del issue_id
    return sync_utils.create_issue(
        self.client,
        issue_json,
        max_attempts=10,
        interval=10
    )

  @staticmethod
  def bulk_sync_allowed(obj):
    """Check if user has permissions to synchronize issuetracker issue.

    Args:
        obj: instance for which issue should be generated/updated.

    Returns:
        True if it's allowed, False if not allowed.
    """
    return permissions.is_allowed_update_for(obj)

  def update_db_issues(self, issues_info):
    """Update db IssueTracker issues with provided data.

    Args:
        issues_info: Dict with issue properties.
    """
    if not issues_info:
      return
    issuetracker = all_models.IssuetrackerIssue.__table__
    stmt = issuetracker.update().where(
        sa.and_(
            issuetracker.c.object_type == expr.bindparam("object_type_"),
            issuetracker.c.object_id == expr.bindparam("object_id_"),
        )
    ).values({
        "cc_list": expr.bindparam("cc_list"),
        "enabled": expr.bindparam("enabled"),
        "title": expr.bindparam("title"),
        "component_id": expr.bindparam("component_id"),
        "hotlist_id": expr.bindparam("hotlist_id"),
        "issue_type": expr.bindparam("issue_type"),
        "issue_priority": expr.bindparam("issue_priority"),
        "issue_severity": expr.bindparam("issue_severity"),
        "assignee": expr.bindparam("assignee"),
        "issue_id": expr.bindparam("issue_id"),
        "issue_url": expr.bindparam("issue_url"),
    })

    try:
      update_values = self.create_update_values(issues_info)
      db.session.execute(stmt, update_values)
      self.log_issues(issues_info.keys())
      db.session.commit()
    except sa.exc.OperationalError as error:
      logger.exception(error)
      raise exceptions.InternalServerError(
          "Failed to update created IssueTracker issues in database."
      )

  @staticmethod
  def create_update_values(issue_info):
    """Prepare issue data for bulk update in db.

    Args:
        issue_json: Dict with issue properties.

    Returns:
        List of dicts with issues data to update in db.
    """
    return [{
        "object_type_": obj_type,
        "object_id_": obj_id,
        "cc_list": ",".join(info["ccs"]),
        "enabled": info["enabled"],
        "title": info["title"],
        "component_id": info["component_id"],
        "hotlist_id": info["hotlist_ids"][0] if info["hotlist_ids"] else None,
        "issue_type": info["type"],
        "issue_priority": info["priority"],
        "issue_severity": info["severity"],
        "assignee": info["assignee"],
        "issue_id": info["issue_id"],
        "issue_url": info["issue_url"],
    } for (obj_type, obj_id), info in issue_info.items()]

  def log_issues(self, issue_objs):
    """Create log information about issues such as event and revisions.

    Args:
        issue_objs: [(obj_type, obj_id)] List with types and ids of objects.
    """
    current_user_id = login.get_current_user_id()
    event_id_query = all_models.Event.__table__.insert().values(
        modified_by_id=current_user_id,
        action='BULK',
        resource_id=0,
        resource_type=None,
    )
    try:
      event_id = db.session.execute(event_id_query).inserted_primary_key[0]
      self.create_revisions(issue_objs, event_id, current_user_id)
    except sa.exc.OperationalError as error:
      logger.exception(error)

  @staticmethod
  def create_revisions(resources, event_id, user_id):
    """Create revisions for provided objects in bulk.

    Args:
        resources: [(obj_type, obj_id)] List with types and ids of objects.
        event_id: id of event that lead to revisions creation.
        user_id: id of user for which revisions should be created.
    """
    issue_objs = all_models.IssuetrackerIssue.query.filter(
        sa.tuple_(
            all_models.IssuetrackerIssue.object_type,
            all_models.IssuetrackerIssue.object_id
        ).in_(resources)
    )
    revision_data = [
        {
            "resource_id": obj.id,
            "resource_type": obj.type,
            "event_id": event_id,
            "action": 'modified',
            "content": obj.log_json(),
            "resource_slug": None,
            "source_type": None,
            "source_id": None,
            "destination_type": None,
            "destination_id": None,
            "updated_at": datetime.datetime.utcnow(),
            "modified_by_id": user_id,
            "created_at": datetime.datetime.utcnow(),
            "context_id": obj.context_id,
        }
        for obj in issue_objs
    ]
    inserter = all_models.Revision.__table__.insert()
    db.session.execute(inserter.values(revision_data))

  @staticmethod
  def make_response(errors):
    """Create response with provided body and status.

    Args:
        errors: List with errors to return in response.

    Returns:
        Created response.
    """
    error_list = []
    for obj, err in errors:
      error_list.append((obj.type, obj.id, err))

    return app.make_response((
        utils.as_json({"errors": error_list}),
        200,
        [("Content-Type", "application/json")]
    ))


class IssueTrackerBulkUpdater(IssueTrackerBulkCreator):
  """Class with methods for bulk tickets update in issuetracker."""

  @staticmethod
  def get_issuetracked_objects(obj_type, obj_ids):
    """Fetch issuetracked objects from db."""
    issuetracked_model = inflector.get_model(obj_type)
    return issuetracked_model.query.join(
        all_models.IssuetrackerIssue,
        sa.and_(
            all_models.IssuetrackerIssue.object_type == obj_type,
            all_models.IssuetrackerIssue.object_id == issuetracked_model.id
        )
    ).filter(
        all_models.IssuetrackerIssue.object_id.in_(obj_ids),
        all_models.IssuetrackerIssue.issue_id.isnot(None),
    ).options(
        sa.orm.Load(issuetracked_model).undefer_group(
            "{}_complete".format(obj_type),
        )
    )

  def sync_issue(self, issue_json, issue_id=None):
    """Update existing issue in issuetracker with provided params."""
    return sync_utils.update_issue(
        self.client,
        issue_id,
        issue_json,
        max_attempts=10,
        interval=10
    )


class IssueTrackerBulkChildCreator(IssueTrackerBulkCreator):
  """Class with methods for bulk tickets creation for child objects."""

  def __init__(self):
    super(IssueTrackerBulkChildCreator, self).__init__()
    self.break_on_errs = True

  # pylint: disable=arguments-differ
  def sync_issuetracker(self, parent_type, parent_id, child_type):
    """Generate IssueTracker issues in bulk for child objects.

    Args:
        parent_type: type of parent object
        parent_id: id of parent object
        child_type: type of child object

    Returns:
        flask.wrappers.Response - response with result of generation.
    """
    issuetracked_info = []
    with benchmark("Load issuetracked objects from database"):
      handler = self.INTEGRATION_HANDLERS[child_type]
      if not hasattr(handler, "load_issuetracked_objects"):
        raise integrations_errors.Error(
            "Creation tickets for {} in scope of {} is not supported.".format(
                parent_type, child_type
            )
        )

      for obj in handler.load_issuetracked_objects(parent_type, parent_id):
        issuetracked_info.append(IssuetrackedObjInfo(obj))

    created, errors = self.handle_issuetracker_sync(issuetracked_info)

    logger.info("Synchronized issues count: %s, failed count: %s",
                len(created), len(errors))
    return self.make_response(errors)

  def bulk_sync_allowed(self, obj):
    """Check if user has permissions to synchronize issuetracker issue.

    Args:
        obj: instance for which issue should be generated/updated.

    Returns:
        True if it's allowed, False if not allowed.
    """
    handler = self.INTEGRATION_HANDLERS.get(obj.type)
    allow_func = getattr(
        handler,
        "bulk_children_gen_allowed",
        self.bulk_sync_allowed
    )
    return allow_func(obj)


class IssuetrackedObjInfo(collections.namedtuple(
    "IssuetrackedObjInfo", ["obj", "hotlist_ids", "component_id"]
)):
  """Class for keeping Issuetracked objects info."""
  __slots__ = ()

  def __new__(cls, obj, hotlist_ids=None, component_id=None):
    if hotlist_ids and not isinstance(hotlist_ids, list):
      hotlist_ids = [hotlist_ids]
    return super(IssuetrackedObjInfo, cls).__new__(
        cls, obj, hotlist_ids, component_id
    )
