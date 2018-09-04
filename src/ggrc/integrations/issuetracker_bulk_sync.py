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
from ggrc.models import all_models, inflector, background_task
from ggrc.models import exceptions as ggrc_exceptions
from ggrc.models.mixins import issue_tracker
from ggrc import utils
from ggrc.rbac import permissions

logger = logging.getLogger(__name__)

# IssueTracker sync errors
WRONG_COMPONENT_ERR = "Component {} does not exist"
WRONG_HOTLIST_ERR = "No Hotlist with id: {}"


@app.route(
    "/_background_tasks/run_children_issues_generation", methods=["POST"]
)
@background_task.queued_task
def run_children_issues_generation(task):
  """Web hook to generate linked buganizer issues for objects of child type."""
  try:
    params = getattr(task, "parameters", {})
    parent_type = params.get("parent", {}).get("type")
    parent_id = params.get("parent", {}).get("id")
    child_type = params.get("child_type")

    bulk_child_creator = IssueTrackerBulkChildCreator()
    return bulk_child_creator.sync_issuetracker(
        parent_type, parent_id, child_type
    )
  except integrations_errors.Error as error:
    logger.error('Bulk issue generation failed with error: %s', error.message)
    raise exceptions.BadRequest(error.message)


@app.route(
    "/_background_tasks/run_issues_generation", methods=["POST"]
)
@background_task.queued_task
def run_issues_generation(task):
  """Web hook to generate linked buganizer issues for provided objects."""
  try:
    params = getattr(task, "parameters", {})
    bulk_creator = IssueTrackerBulkCreator()
    return bulk_creator.sync_issuetracker(params.get("objects"))
  except integrations_errors.Error as error:
    logger.error('Bulk issue generation failed with error: %s', error.message)
    raise exceptions.BadRequest(error.message)


@app.route(
    "/_background_tasks/run_issues_update", methods=["POST"]
)
@background_task.queued_task
def run_issues_update(task):
  """Web hook to update linked buganizer issues for provided objects."""
  try:
    params = getattr(task, "parameters", {})
    bulk_updater = IssueTrackerBulkUpdater()
    return bulk_updater.sync_issuetracker(params.get("objects"))
  except integrations_errors.Error as error:
    logger.error('Bulk issue update failed with error: %s', error.message)
    raise exceptions.BadRequest(error.message)


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
        objects. ([object_type, object_id, hotlist_id, compornent_id])

    Returns:
        flask.wrappers.Response - response with result of generation.
    """
    if not objects_data:
      return self.make_response({}, 200)

    issuetracked_info = []
    objects_info = self.group_objs_by_type(objects_data)
    for obj_type, obj_id_info in objects_info.items():
      for obj in self.get_issuetracked_objects(obj_type, obj_id_info.keys()):
        issuetracked_info.append(
            IssuetrackedObjInfo(obj, *obj_id_info[obj.id])
        )

    _, errors = self.handle_issuetracker_sync(issuetracked_info)
    return self.make_response({"errors": errors}, 200)

  @staticmethod
  def group_objs_by_type(objects):
    """Group objects data by obj type."""
    objects_info = collections.defaultdict(dict)
    for obj in objects:
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

  def handle_issuetracker_sync(self, tracked_objs):  # noqa: ignore=C901
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

        integration_handler = self.INTEGRATION_HANDLERS.get(obj_info.obj.type)
        issue_json = integration_handler.prepare_issue_json(obj_info.obj)
        if not issue_json:
          continue

        if obj_info.hotlist_ids:
          issue_json["hotlist_ids"] = obj_info.hotlist_ids
        if obj_info.component_id:
          issue_json["component_id"] = obj_info.component_id

        issue_id = getattr(obj_info.obj.issuetracker_issue, "issue_id", None)
        res = self.sync_issue(issue_json, issue_id)

        issue_json["enabled"] = True
        if not issue_json.get("issue_id"):
          issue_json["issue_id"] = res.get("issueId")
          from ggrc.models.hooks.issue_tracker import assessment_integration
          # pylint: disable=protected-access
          url = assessment_integration._ISSUE_URL_TMPL % res.get("issueId")
          issue_json["issue_url"] = url

        created[(obj_info.obj.type, obj_info.obj.id)] = issue_json
      except integrations_errors.Error as error:
        errors.append((obj_info.obj.type, obj_info.obj.id, str(error)))
        if self.break_on_errs and error in [
            WRONG_HOTLIST_ERR.format(issue_json["hotlist_ids"]),
            WRONG_COMPONENT_ERR.format(issue_json["component_id"])
        ]:
          break
      except (TypeError, ValueError, ggrc_exceptions.ValidationError) as error:
        errors.append((obj_info.obj.type, obj_info.obj.id, str(error)))
      except exceptions.Forbidden:
        errors.append((obj_info.obj.type, obj_info.obj.id, "Forbidden"))

    self.update_db_issues(created)
    return created, errors

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
  def make_response(body, status):
    """Create response with provided body and status.

    Args:
        body: Dict with data for response body.
        status: Int status of response.

    Returns:
        Created response.
    """
    headers = [("Content-Type", "application/json")]
    return app.make_response((utils.as_json(body), status, headers))


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
    parent = models.get_model(parent_type)
    child = models.get_model(child_type)
    if not issubclass(parent, issue_tracker.IssueTracked) or \
       not issubclass(child, issue_tracker.IssueTracked):
      raise exceptions.BadRequest("Provided model is not IssueTracked.")

    issuetracked_info = []
    handler = self.INTEGRATION_HANDLERS[child.__name__]
    for obj in handler.load_issuetracked_objects(parent_type, parent_id):
      issuetracked_info.append(IssuetrackedObjInfo(obj))

    _, errors = self.handle_issuetracker_sync(issuetracked_info)
    return self.make_response({"errors": errors}, 200)

  def bulk_sync_allowed(self, obj):
    """Check if user has permissions to synchronize issuetracker issue.

    Args:
        obj: instance for which issue should be generated/updated.

    Returns:
        True if it's allowed, False if not allowed.
    """
    handler = self.INTEGRATION_HANDLERS.get(obj.type)
    return handler.bulk_children_gen_allowed(obj)


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
