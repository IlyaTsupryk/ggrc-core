# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Bulk IssueTracker issues creation functionality."""

from collections import defaultdict

import datetime
import logging
import html2text

from werkzeug import exceptions

import sqlalchemy as sa
from sqlalchemy.sql import expression as expr

from ggrc import models, db, login
from ggrc.app import app
from ggrc.integrations import integrations_errors, issues
from ggrc.models import all_models
from ggrc.models import issuetracker_issue
from ggrc.rbac import permissions
from ggrc.models.hooks import issue_tracker
from ggrc import utils

logger = logging.getLogger(__name__)

WRONG_COMPONENT_ERR = "Component {} does not exist"
WRONG_HOTLIST_ERR = "No Hotlist with id: {}"


def handle_children_issues_generation(json_data):
  """Generate IssueTracker issues in bulk.

  Args:
      json_data: Dict with format {"type": <model name>, "ids": <list of ids>}
        where <model name> - name of model for which children issues
        should be generated, <list of ids> - ids of model objects.
        For example, to generate issues for all Assessments in Audits with
        id 10 and 11, json should be like {"type": "Audit", "ids": [10, 11]}.

  Returns:
      flask.wrappers.Response - response with result of generation.
        The response will contain 200 status if any child object
        was updated or if no child object require update in scope
        of provided parent. Body of such response will contain list of errors
        for non-generated issues.
        403 will be raised if user doesn't have update rights on any
        children or read rights on parent.
        If provided parameters are incorrect, status 400 will be used.
  """
  issue_objs = parse_request_data(json_data)

  # If there are no objects for update, return success response,
  # i.e. no need to create issues for objects that already have them or if
  # there are no obje
  if not issue_objs:
    return prepare_response(None, [])

  issues_info = {}
  people_cache = PeopleCache()
  for obj in issue_objs:
    issues_info[(obj.type, obj.id)] = obj
    people_cache.add_obj_roles(obj)

  people_cache.populate_from_db()
  import ipdb;ipdb.set_trace()
  created, errors = bulk_create_issuetracker_info(
      issues_info,
      people_cache.get_people_emails()
  )
  return prepare_response(created, errors)


def parse_request_data(json_data):
  if not json_data:
    raise exceptions.BadRequest("Request data is not provided.")

  parent_data = json_data.get("parent", {})
  parent = models.get_model(parent_data.get("type"))
  parent_id = parent_data.get("id")
  child = models.get_model(json_data.get("child_type"))
  if not issubclass(parent, issuetracker_issue.IssueTracked) or \
     not issubclass(child, issuetracker_issue.IssueTracked):
    raise exceptions.BadRequest("Provided model is not IssueTracked.")

  return load_issue_tracker_objs(parent, parent_id, child).all()


def load_issue_tracker_objs(parent_model, parent_id, child_model=None):
  """Create query to load objects which IssueTrackerIssues should be generated.

  Args:
      model_name: Name of model.
      ids: List of ids of model objects.

  Returns:
      SQLAlchemy query which load necessary objects.
  """
  if parent_model.__name__ == "Audit" and child_model.__name__ == "Assessment":
    issue_tracked_objs = load_audit_assessments(parent_id)
  else:
    issue_tracked_objs = parent_model.query.filter(
        parent_model.id.in_(parent_id)
    )
  return issue_tracked_objs


def load_audit_assessments(audit_id):
  return all_models.Assessment.query.join(
      all_models.IssuetrackerIssue,
      sa.and_(
          all_models.IssuetrackerIssue.object_type == "Assessment",
          all_models.IssuetrackerIssue.object_id == all_models.Assessment.id,
      )
  ).join(
      all_models.Audit,
      all_models.Audit.id == all_models.Assessment.audit_id,
  ).filter(
      all_models.Audit.id == audit_id,
      all_models.IssuetrackerIssue.issue_id.is_(None),
  ).options(
      sa.orm.Load(all_models.Assessment).undefer_group(
          "Assessment_complete",
      ).subqueryload(
          all_models.Assessment.audit
      ).subqueryload(
          all_models.Audit.issuetracker_issue
      )
  )


def allowed_generate_for(obj):
  """Check if current user has permissions to generate issue for obj.

  Args:
      obj: Object for which IssueTracker issue should be generated.

  Returns:
      True if it's allowed, False if not allowed.
  """
  conditions = [permissions.is_allowed_update_for(obj)]
  if hasattr(obj, "audit"):
    conditions.append(permissions.is_allowed_update_for(obj.audit))
  return all(conditions)


def create_asmnt_comment(assessment):
  """Create comment for generated IssueTracker issue related to assessment.

  Args:
      assessment: Instance of Assessment for which comment should be created.

  Returns:
      String with created comments separated with '\n'.
  """
  # pylint: disable=protected-access
  comments = [
      issue_tracker._INITIAL_COMMENT_TMPL %
      issue_tracker._get_assessment_url(assessment)
  ]
  test_plan = assessment.test_plan
  if test_plan:
    comments.extend([
        "Following is the assessment Requirements/Assessment Procedure "
        "from GGRC:",
        html2text.HTML2Text().handle(test_plan).strip("\n"),
    ])

  return "\n".join(comments)


def bulk_create_issuetracker_info(tracked_objs, people_emails):
  """Create IssueTracker issues for tracked objects in bulk.

  Args:
      tracked_objs: [(object_type, object_id)][object] - tracked object info.
      people_emails: dict[(object_type, object_id)][role_name][set(emails)] -
        emails related to object roles.

  Returns:
      Tuple with dicts of created issue info and errors.
  """
  errors = []
  created = {}
  # IssueTracker server api doesn't support collection post, thus we
  # create issues in loop.
  for obj in tracked_objs.values():
    try:
      if not allowed_generate_for(obj):
        raise exceptions.Forbidden()

      issue_info = get_issue_info(obj)
      # pylint: disable=protected-access
      issue_tracker._normalize_issue_tracker_info(issue_info)

      issue_json = prepare_issue_json(obj, issue_info, people_emails)
      if not issue_json:
        continue
      res = issues.Client().create_issue(issue_json)

      issue_json["enabled"] = True
      issue_json["issue_id"] = res.get("issueId")
      issue_url = issue_tracker._ISSUE_URL_TMPL % res.get("issueId")
      issue_json["issue_url"] = issue_url

      created[(obj.type, obj.id)] = issue_json
    except integrations_errors.Error as error:
      errors.append((obj.type, obj.id, str(error)))
      if error in [
          WRONG_HOTLIST_ERR.format(issue_json["hotlist_id"]),
          WRONG_COMPONENT_ERR.format(issue_json["component_id"])
      ]:
        return {}, errors
    except exceptions.Forbidden:
      errors.append((obj.type, obj.id, "Forbidden"))

  update_db_issues(created)
  return created, errors


def prepare_issue_json(obj, issue_tracker_info, people_emails):
  """Create json that will be sent to IssueTracker.

  Args:
      obj: Instance of IssueTracked object.
      issue_tracker_info: Dict with parent IssueTracker info.
      people_emails: dict[(object_type, object_id)][role_name][set(emails)] -
        emails related to object roles.

  Returns:
      Dict with IssueTracker issue creation info.
  """
  # Creation of IssueTracker issue json supported only for Assessment now
  if not isinstance(obj, all_models.Assessment):
    return {}
  hotlist_id = issue_tracker_info.get("hotlist_id")
  audit_roles = people_emails.get(
      (obj.audit.type, obj.audit.id), {}
  )
  reporters = sorted(audit_roles.get("Audit Captains", []))
  asmnt_roles = people_emails.get((obj.type, obj.id), {})
  cc_list = sorted(asmnt_roles.get("Assignees", []))
  assignee = cc_list.pop(0) if cc_list else ""

  return {
      "component_id": issue_tracker_info["component_id"],
      "hotlist_ids": [hotlist_id] if hotlist_id else [],
      "title": obj.title,
      "type": issue_tracker_info["issue_type"],
      "priority": issue_tracker_info["issue_priority"],
      "severity": issue_tracker_info["issue_severity"],
      "reporter": reporters[0] if reporters else "",
      "assignee": assignee,
      "verifier": assignee,
      "ccs": cc_list,
      "comment": create_asmnt_comment(obj),
      "status": issues.STATUSES[obj.status],
  }


def get_issue_info(obj):
  """Retrieve IssueTrackerIssue from obj.

  Args:
      obj: Instance of IssueTracked object.
  """
  if hasattr(obj, "audit"):
    issue_obj = obj.audit.issuetracker_issue
  else:
    issue_obj = obj.issuetracker_issue
  return issue_obj.to_dict() if issue_obj else {}


def update_db_issues(issues_info):
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
    update_values = create_update_values(issues_info)
    db.session.execute(stmt, update_values)
    log_issues(issues_info.keys())
    # Commit is not required here. It's added to activate possible
    # SQLAlchemy hooks.
    db.session.plain_commit()
  except sa.exc.OperationalError as error:
    logger.exception(error)
    raise exceptions.InternalServerError(
        "Failed to update created IssueTracker issues in database."
    )


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


def log_issues(issue_objs):
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
      context_id=None
  )
  try:
    event_id = db.session.execute(event_id_query).inserted_primary_key[0]
    create_revisions(issue_objs, event_id, current_user_id)
  except sa.exc.OperationalError as error:
    logger.exception(error)


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


def prepare_response(created, errors):
  """Prepare response with information about generation errors.

  Args:
      created: Dict with info about created objects.
      errors: Dict with info about generation errors.

  Returns:
      flask.wrappers.Response - response with result of generation.
  """
  res_body = utils.as_json({"errors": errors})

  # Return 200 if any items were created or if no errors are happened
  if created or not errors:
    return make_response(res_body, 200)
  else:
    return make_response(res_body, 400)


def make_response(body, status):
  """Create response with provided body and status.

  Args:
      body: Json data of response body.
      status: Int status of response.

  Returns:
      Created response.
  """
  headers = [("Content-Type", "application/json")]
  return app.make_response((body, status, headers))


class PeopleCache(object):
  """Cache of People required during IssueTracker issues generation."""

  def __init__(self):
    """Setup object."""
    self._people_roles = set()
    self._people_emails = defaultdict(dict)

  def add_obj_roles(self, obj):
    """Collect object roles for which people should be got.

    Args:
        obj: Instance of object which roles should be collected.
    """
    if isinstance(obj, all_models.Assessment):
      self._people_roles.add((obj.type, obj.id, "Assignees"))
      self._people_roles.add((obj.audit.type, obj.audit.id, "Audit Captains"))

  def populate_from_db(self):
    """Get emails of people assigned to objects.

    Args:
        obj_roles: list(object_type, object_id, role_name).
    """
    if not self._people_roles:
      return

    people_query = db.session.query(
        all_models.AccessControlList.object_type,
        all_models.AccessControlList.object_id,
        all_models.AccessControlRole.name,
        all_models.Person.email,
    ).join(
        all_models.Person,
        all_models.Person.id == all_models.AccessControlList.person_id,
    ).join(
        all_models.AccessControlRole,
        all_models.AccessControlRole.id ==
        all_models.AccessControlList.ac_role_id,
    ).filter(
        sa.sql.tuple_(
            all_models.AccessControlList.object_type,
            all_models.AccessControlList.object_id,
            all_models.AccessControlRole.name,
        ).in_(self._people_roles)
    )

    for obj_type, obj_id, ac_role_name, email in people_query:
      self._people_emails[(obj_type, obj_id)].setdefault(
          ac_role_name, set()
      ).add(email)

  def get_people_emails(self):
    """Get collected people emails.

    Returns:
        dict[(object_type, object_id)][role_name][set(emails)].
    """
    return self._people_emails
