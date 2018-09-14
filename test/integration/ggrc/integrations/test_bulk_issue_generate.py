# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test bulk issuetracker synchronization."""
import unittest

import ddt
import mock

from flask import g

from ggrc import db
from ggrc import views
from ggrc.app import app

from ggrc.notifications import data_handlers
from ggrc.integrations import integrations_errors, issuetracker_bulk_sync
from ggrc.integrations.synchronization_jobs import sync_utils
from ggrc.models import all_models, inflector
from integration.ggrc import TestCase, generator
from integration.ggrc.api_helper import Api
from integration.ggrc.models import factories


class TestBulkIssuesSync(TestCase):
  """Base class for bulk issuetracker synchronization tests."""

  def setUp(self):
    """Set up for test methods."""
    super(TestBulkIssuesSync, self).setUp()
    self.api = Api()
    self.gen = generator.ObjectGenerator()

    self.role_people = {
        "Audit Captains": factories.PersonFactory(email="captain@example.com"),
        "Creators": factories.PersonFactory(email="creators@example.com"),
        "Assignees": factories.PersonFactory(email="assignees@example.com"),
        "Verifiers": factories.PersonFactory(email="verifiers@example.com"),
    }
    self.issue_id = "42"

  def setup_assessments(self, asmnt_count, issue_id=None, enabled=True):
    """Create Audit with couple of Assessments and linked IssueTrackerIssues.

    Args:
        asmnt_count: Count of Assessments in Audit.

    Returns:
        Tuple with Audit id and list of Assessment ids.
    """
    with factories.single_commit():
      audit = factories.AuditFactory()
      audit.add_person_with_role_name(
          self.role_people["Audit Captains"],
          "Audit Captains",
      )
      factories.IssueTrackerIssueFactory(
          enabled=enabled,
          issue_tracked_obj=audit,
          issue_id=issue_id,
          issue_type="BUG",
          component_id=12345,
          hotlist_id=12345,
          issue_priority="P2",
          issue_severity="S2",
      )

      assessment_ids = []
      for _ in range(asmnt_count):
        asmnt = factories.AssessmentFactory(audit=audit)
        factories.RelationshipFactory(source=audit, destination=asmnt)
        for role_name in ["Creators", "Assignees", "Verifiers"]:
          asmnt.add_person_with_role_name(
              self.role_people[role_name],
              role_name,
          )
        factories.IssueTrackerIssueFactory(
            enabled=enabled,
            issue_tracked_obj=asmnt,
            issue_id=issue_id,
            title=None,
        )
        assessment_ids.append(asmnt.id)
      return audit.id, assessment_ids

  @staticmethod
  def setup_issues(issue_count, issue_id=None, enabled=True):
    """Create issues with enabled integration."""
    with factories.single_commit():
      issue_ids = []
      for _ in range(issue_count):
        issue = factories.IssueFactory()
        factories.IssueTrackerIssueFactory(
            enabled=enabled,
            issue_tracked_obj=issue,
            issue_id=issue_id,
            title=None,
        )
        issue_ids.append(issue.id)
      return issue_ids

  def issuetracker_sync_mock(self, sync_func_name):
    """IssueTracker sync method mock."""
    return mock.patch.object(
        sync_utils,
        sync_func_name,
        return_value={"issueId": self.issue_id}
    )

  def generate_children_issues_for(self, parent_type, parent_id, child_type):
    """Generate IssueTracker issue for objects with provided type and ids.

    Args:
        obj_type: Type of objects. Now only 'Assessment' supported.
        obj_ids: List with ids of objects.

    Returns:
        Response with result of issues generation.
    """
    with self.issuetracker_sync_mock("create_issue"):
      return self.api.send_request(
          self.api.client.post,
          api_link="/generate_children_issues",
          data={
              "parent": {"type": parent_type, "id": parent_id},
              "child_type": child_type,
          }
      )

  def generate_issues_for(self, object_info):
    """Generate IssueTracker issues for provided objects."""
    with self.issuetracker_sync_mock("create_issue"):
      return self.api.send_request(
          self.api.client.post,
          api_link="/generate_issues",
          data={
              "objects": [{
                  "type": type_,
                  "id": id_,
                  "hotlist_ids": hotlist_id,
                  "component_id": component_id,
              } for type_, id_, hotlist_id, component_id in object_info],
          }
      )

  def update_issues_for(self, object_info):
    """Update IssueTracker issues for provided objects."""
    with self.issuetracker_sync_mock("update_issue"):
      return self.api.send_request(
          self.api.client.post,
          api_link="/update_issues",
          data={
              "objects": [{
                  "type": type_,
                  "id": id_,
                  "hotlist_ids": hotlist_id,
                  "component_id": component_id,
              } for type_, id_, hotlist_id, component_id in object_info],
          }
      )

  def assert_obj_issues(self, issuetracker_info, assignee=None):
    """Check correctness of created IssueTracker issues."""
    for type_, id_, hotlist_id, component_id in issuetracker_info:
      obj = inflector.get_model(type_).query.get(id_)
      issue = obj.issuetracker_issue

      self.assertEqual(issue.enabled, 1)
      self.assertEqual(issue.title, obj.title)
      self.assertEqual(issue.component_id, component_id)
      self.assertEqual(issue.hotlist_id, hotlist_id)
      self.assertEqual(issue.issue_type, "BUG")
      self.assertEqual(issue.issue_priority, "P2")
      self.assertEqual(issue.issue_severity, "S2")
      self.assertEqual(issue.assignee, assignee)
      self.assertEqual(issue.cc_list, "")
      self.assertEqual(issue.issue_id, self.issue_id)
      self.assertEqual(
          issue.issue_url,
          "http://issue/{}".format(self.issue_id)
      )

  def assert_children_asmnt_issues(self, asmnt_ids):
    """Check if Assessments IssueTracker issues inherit data from Audit."""
    assessments = all_models.Assessment.query.filter(
        all_models.Assessment.id.in_(asmnt_ids)
    )
    for asmnt in assessments:
      issue = asmnt.issuetracker_issue
      parent_issue = asmnt.audit.issuetracker_issue

      self.assertEqual(issue.enabled, 1)
      self.assertEqual(issue.title, asmnt.title)
      self.assertEqual(issue.component_id, parent_issue.component_id)
      self.assertEqual(issue.hotlist_id, parent_issue.hotlist_id)
      self.assertEqual(issue.issue_type, parent_issue.issue_type)
      self.assertEqual(issue.issue_priority, parent_issue.issue_priority)
      self.assertEqual(issue.issue_severity, parent_issue.issue_severity)
      self.assertEqual(issue.assignee, "assignees@example.com")
      self.assertEqual(issue.cc_list, "")
      self.assertEqual(issue.issue_id, self.issue_id)
      self.assertEqual(
          issue.issue_url,
          "http://issue/{}".format(self.issue_id)
      )

  def assert_not_updated(self, object_type, object_ids):
    """Check if IssueTracker issues have empty fields.

    Args:
        object_type: Type of objects which issues should be checked.
        object_ids: List with ids for objects which issues should be checked.

    Raise:
        AssertionError if relevant Issues have non-empty base fields.
    """
    issues = all_models.IssuetrackerIssue.query.filter(
        all_models.IssuetrackerIssue.object_type == object_type,
        all_models.IssuetrackerIssue.object_id.in_(object_ids),
    )
    for issue in issues:
      self.assertEqual(issue.issue_id, None)
      self.assertEqual(issue.assignee, None)
      self.assertEqual(issue.cc_list, "")
      self.assertEqual(issue.title, None)


@ddt.ddt
class TestBulkIssuesGenerate(TestBulkIssuesSync):
  """Test bulk issues generation."""

  def test_get_objects_method_assmt(self):
    """Test get_issuetracked_objects() for not linked assessments."""
    _, assessment_ids_enabled = self.setup_assessments(3)
    _, assessment_ids_disabled = self.setup_assessments(2, enabled=False)
    assessment_ids = assessment_ids_enabled + assessment_ids_disabled
    creator = issuetracker_bulk_sync.IssueTrackerBulkCreator

    result = creator.get_issuetracked_objects("Assessment", assessment_ids)
    result_ids = [assmt.id for assmt in result]
    self.assertEqual(set(assessment_ids_enabled), set(result_ids))

  def test_get_objects_method_issue(self):
    """Test get_issuetracked_objects() for not linked issues."""
    issue_ids_enabled = self.setup_issues(3)
    issue_ids_disabled = self.setup_issues(2, enabled=False)
    issue_ids = issue_ids_enabled + issue_ids_disabled
    creator = issuetracker_bulk_sync.IssueTrackerBulkCreator

    result = creator.get_issuetracked_objects("Issue", issue_ids)
    result_ids = [issue.id for issue in result]
    self.assertEqual(set(issue_ids_enabled), set(result_ids))

  @ddt.data(
      ("IssueTrackerBulkCreator", "background_generate_issues"),
      ("IssueTrackerBulkUpdater", "background_update_issues"),
  )
  @ddt.unpack
  def test_issue_generate_call(self, class_name, func_name):
    """Test generate_issue call creates task for bulk generate."""
    user = all_models.Person.query.filter_by(email="user@example.com").one()
    setattr(g, '_current_user', user)
    _, assessment_ids = self.setup_assessments(3)

    data = {
        "objects": [{
            "type": "Assessment",
            "id": id_,
        } for id_ in assessment_ids],
    }

    response = app.make_response(("success", 200, ))
    func_addr = ("ggrc.integrations.issuetracker_bulk_sync." +
                 class_name + ".sync_issuetracker")
    with mock.patch(func_addr, return_value=response) as generate_mock:
      callable_func = getattr(views, func_name)
      result = callable_func(data)

    self.assert200(result)
    bg_task = all_models.BackgroundTask.query.one()
    self.assertEqual(bg_task.status, "Success")
    generate_mock.assert_called_once()

  def test_asmnt_bulk_generate(self):
    """Test bulk generation of issues for Assessments."""
    _, assessment_ids = self.setup_assessments(3)
    asmnt_issuetracker_info = [
        ("Assessment", id_, "123", "321") for id_ in assessment_ids
    ]
    response = self.generate_issues_for(asmnt_issuetracker_info)
    self.assert200(response)
    self.assertEqual(response.json.get("errors"), [])
    self.assert_obj_issues(asmnt_issuetracker_info, "assignees@example.com")

  @unittest.skip("Not implemented.")
  def test_permission_check(self):
    """Test generation if user has rights on part of objects."""
    _, assessment_ids = self.setup_assessments(3)
    with_rights_ids = assessment_ids[:2]
    without_rights_ids = assessment_ids[2:]
    _, assignee_user = self.gen.generate_person(user_role="Creator")

    with factories.single_commit():
      for id_ in with_rights_ids:
        assessment = all_models.Assessment.query.get(id_)
        assessment.add_person_with_role_name(assignee_user, "Creators")

    self.api.set_user(assignee_user)

    asmnt_issuetracker_info = [
        ("Assessment", id_, "123", "321") for id_ in assessment_ids
    ]
    response = self.generate_issues_for(asmnt_issuetracker_info)
    self.assert200(response)
    forbidden_err = "403 Forbidden: You don't have the permission to access " \
                    "the requested resource. It is either read-protected or " \
                    "not readable by the server."
    expected_errors = [
        ["Assessment", id_, forbidden_err] for id_ in without_rights_ids
    ]
    self.assertEqual(response.json.get("errors"), expected_errors)
    with_rights_info = [
        ("Assessment", id_, "123", "321") for id_ in with_rights_ids
    ]
    self.assert_obj_issues(with_rights_info, "assignees@example.com")
    self.assert_not_updated("Assessment", without_rights_ids)

  def test_issue_bulk_generate(self):
    """Test bulk generation of issuetracker issues for Issue."""
    issue_ids = []
    with factories.single_commit():
      person = factories.PersonFactory()
      person_email = person.email
      for _ in range(3):
        issue = factories.IssueFactory(modified_by=person)
        for role_name in ["Admin", "Primary Contacts"]:
          issue.add_person_with_role_name(person, role_name)
        factories.IssueTrackerIssueFactory(
            enabled=True,
            issue_tracked_obj=issue,
            issue_id=None,
            title='',
            component_id=12345,
            hotlist_id=54321,
            issue_priority="P2",
            issue_severity="S2",
        )
        issue_ids.append(issue.id)

    issue_issuetracker_info = [
        ("Issue", id_, None, None) for id_ in issue_ids
    ]
    response = self.generate_issues_for(issue_issuetracker_info)
    self.assert200(response)
    self.assertEqual(response.json.get("errors"), [])

    issues = all_models.IssuetrackerIssue.query.filter(
        all_models.IssuetrackerIssue.object_type == "Issue",
        all_models.IssuetrackerIssue.object_id.in_(issue_ids)
    ).all()
    for issue in issues:
      parent_obj = issue.Issue_issue_tracked
      self.assertEqual(issue.enabled, 1)
      self.assertEqual(issue.title, parent_obj.title)
      self.assertEqual(issue.component_id, "12345")
      self.assertEqual(issue.hotlist_id, "54321")
      self.assertEqual(issue.issue_priority, "P2")
      self.assertEqual(issue.issue_severity, "S2")
      self.assertEqual(issue.assignee, person_email)
      self.assertEqual(issue.cc_list, "")

      self.assertEqual(issue.issue_id, self.issue_id)
      self.assertEqual(
          issue.issue_url,
          "http://issue/{}".format(self.issue_id)
      )

  def test_rate_limited_generate(self):
    """Test tickets generation when issuetracker raise 429 error."""
    _, assessment_ids = self.setup_assessments(3)

    error = integrations_errors.HttpError(data="Test Error", status=429)
    with mock.patch(
        "ggrc.integrations.issues.Client.create_issue",
        side_effect=error
    ) as create_issue_mock:
      with mock.patch("time.sleep"):
        response = self.api.send_request(
            self.api.client.post,
            api_link="/generate_issues",
            data={
                "objects": [{
                    "type": "Assessment",
                    "id": id_
                } for id_ in assessment_ids],
            }
        )
      self.assert200(response)
      expected_errors = [
          ["Assessment", id_, "429 Test Error"]
          for id_ in assessment_ids
      ]
      self.assertEqual(response.json.get("errors"), expected_errors)
      # 10 times for each assessment
      self.assertEqual(create_issue_mock.call_count, 30)

  def test_exception_notification(self):
    """Test notification about failed bulk update."""
    filename = "test.csv"
    updater = issuetracker_bulk_sync.IssueTrackerBulkUpdater()
    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      updater.send_notification(filename, "user@example.com", failed=True)

    self.assertEqual(send_mock.call_count, 1)
    (email, _, body), _ = send_mock.call_args_list[0]
    self.assertEqual(email, "user@example.com")
    self.assertIn(updater.ERROR_TITLE.format(filename=filename), body)
    self.assertIn(updater.EXCEPTION_TEXT, body)

  def test_succeeded_notification(self):
    """Test notification about succeeded bulk generation."""
    creator = issuetracker_bulk_sync.IssueTrackerBulkCreator()
    filename = "test_file.csv"
    recipient = "user@example.com"
    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      creator.send_notification(filename, recipient)

    self.assertEqual(send_mock.call_count, 1)
    (email, _, body), _ = send_mock.call_args_list[0]
    self.assertEqual(email, recipient)
    self.assertIn(creator.SUCCESS_TITLE.format(filename=filename), body)
    self.assertIn(creator.SUCCESS_TEXT, body)

  def test_error_notification(self):
    """Test notification about bulk generation with errors"""
    creator = issuetracker_bulk_sync.IssueTrackerBulkCreator()
    filename = "test_file.csv"
    recipient = "user@example.com"
    assmt = factories.AssessmentFactory()

    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      creator.send_notification(filename, recipient, errors=[(assmt, "")])

    self.assertEqual(send_mock.call_count, 1)
    (email, _, body), _ = send_mock.call_args_list[0]
    self.assertEqual(email, recipient)
    self.assertIn(creator.ERROR_TITLE.format(filename=filename), body)
    self.assertIn(assmt.slug, body)
    self.assertIn(assmt.title, body)
    self.assertIn(data_handlers.get_object_url(assmt), body)

  def test_issuetracker_sync_history(self):
    """Test if issuetracker_sync_history table updated with failed objs."""
    _, assessment_ids = self.setup_assessments(3)
    with mock.patch(
        "ggrc.integrations.issues.Client.create_issue",
        side_effect=integrations_errors.HttpError(data="Test Error")
    ):
      response = self.api.send_request(
          self.api.client.post,
          api_link="/generate_issues",
          data={
              "objects": [{
                  "type": "Assessment",
                  "id": id_
              } for id_ in assessment_ids],
          }
      )
      self.assert200(response)

    sync_history = all_models.IssuetrackerSyncHistory
    history = sync_history.query.join(
        all_models.BackgroundTask,
        all_models.BackgroundTask.id == sync_history.bg_task_id
    ).filter(
        sync_history.object_type == "Assessment",
        sync_history.object_id.in_(assessment_ids),
    )
    self.assertEqual(history.count(), len(assessment_ids))
    for sync_res in history:
      self.assertEqual(sync_res.result, False)
      self.assertEqual(sync_res.error, "500 Test Error")


@ddt.ddt
class TestBulkIssuesChildGenerate(TestBulkIssuesSync):
  """Test bulk issues generation for child objects."""

  def test_get_objects_method_assmt(self):
    """Test get_issuetracked_objects() for linked assessments."""
    _, assessment_ids_enabled = self.setup_assessments(3, issue_id=123)
    _, assessment_ids_disabled = self.setup_assessments(2,
                                                        issue_id=123,
                                                        enabled=False)
    assessment_ids = assessment_ids_enabled + assessment_ids_disabled
    updater = issuetracker_bulk_sync.IssueTrackerBulkUpdater

    result = updater.get_issuetracked_objects("Assessment", assessment_ids)
    result_ids = [assmt.id for assmt in result]
    self.assertEqual(set(assessment_ids_enabled), set(result_ids))

  def test_get_objects_method_issue(self):
    """Test get_issuetracked_objects() for linked issues."""
    issue_ids_enabled = self.setup_issues(3, issue_id=123)
    issue_ids_disabled = self.setup_issues(2, issue_id=123, enabled=False)
    issue_ids = issue_ids_enabled + issue_ids_disabled
    updater = issuetracker_bulk_sync.IssueTrackerBulkUpdater

    result = updater.get_issuetracked_objects("Issue", issue_ids)
    result_ids = [issue.id for issue in result]
    self.assertEqual(set(issue_ids_enabled), set(result_ids))

  def test_asmnt_bulk_child_generate(self):
    """Test generation of issues for all Assessments in Audit."""
    audit_id, assessment_ids = self.setup_assessments(3)
    response = self.generate_children_issues_for(
        "Audit", audit_id, "Assessment"
    )
    self.assert200(response)
    self.assertEqual(response.json.get("errors"), [])
    self.assert_children_asmnt_issues(assessment_ids)

  def test_norights(self):
    """Test generation if user doesn't have rights on Audit and Assessment."""
    audit_id, assessment_ids = self.setup_assessments(3)
    _, side_user = self.gen.generate_person(user_role="Creator")
    self.api.set_user(side_user)
    response = self.generate_children_issues_for(
        "Audit", audit_id, "Assessment"
    )
    self.assert200(response)
    self.assert_not_updated("Assessment", assessment_ids)

  def test_partially_rights(self):
    """Test generation if user has rights on part of Assessments."""
    audit_id, assessment_ids = self.setup_assessments(3)
    changed_asmnt_id = assessment_ids[0]
    norights_asmnt_ids = assessment_ids[1:]
    _, assignee_user = self.gen.generate_person(user_role="Creator")

    audit_role = factories.AccessControlRoleFactory(
        name="Edit Role",
        object_type="Audit",
        update=True
    )
    with factories.single_commit():
      assessment = all_models.Assessment.query.get(changed_asmnt_id)
      assessment.add_person_with_role_name(assignee_user, "Creators")
      acl = factories.AccessControlListFactory(
          object_id=audit_id,
          object_type="Audit",
          ac_role_id=audit_role.id,
      )
      factories.AccessControlPersonFactory(
          person=assignee_user,
          ac_list=acl,
      )

    self.api.set_user(assignee_user)
    response = self.generate_children_issues_for(
        "Audit", audit_id, "Assessment"
    )
    self.assert200(response)
    self.assert_children_asmnt_issues([changed_asmnt_id])
    self.assert_not_updated("Assessment", norights_asmnt_ids)

  @ddt.data(
      issuetracker_bulk_sync.WRONG_COMPONENT_ERR,
      issuetracker_bulk_sync.WRONG_HOTLIST_ERR,
  )
  def test_invalid_component_id(self, error):
    """Test generation of issues if '{}' error raised."""
    audit_id, assessment_ids = self.setup_assessments(3)

    error = error.format("12345")
    with mock.patch(
        "ggrc.integrations.issues.Client.create_issue",
        side_effect=integrations_errors.HttpError(error)
    ) as create_issue_mock:
      response = self.api.send_request(
          self.api.client.post,
          api_link="/generate_children_issues",
          data={
              "parent": {"type": "Audit", "id": audit_id},
              "child_type": "Assessment"
          }
      )
    self.assert200(response)
    self.assertEqual(
        response.json.get("errors"),
        [["Assessment", assessment_ids[0], "500 {}".format(error)]]
    )
    self.assertEqual(create_issue_mock.call_count, 1)
    query = all_models.IssuetrackerIssue.query.filter(
        all_models.IssuetrackerIssue.issue_id.isnot(None)
    )
    self.assertEqual(query.count(), 0)

  def test_related_assessments(self):
    """Assessment with empty issuetracker_issue should be synced"""
    with factories.single_commit():
      audit = factories.AuditFactory()
      factories.IssueTrackerIssueFactory(
          issue_tracked_obj=audit,
          issue_id=None,
          component_id=12345,
          hotlist_id=54321,
          issue_priority="P2",
          issue_severity="S2",
      )
      assess1 = factories.AssessmentFactory(audit=audit)
      assess1_id = assess1.id
      assess2 = factories.AssessmentFactory(audit=audit)
      assess2_id = assess2.id
      factories.IssueTrackerIssueFactory(
          issue_tracked_obj=assess2,
          issue_id=None,
          component_id=9999,
          hotlist_id=7777,
          issue_priority="P1",
          issue_severity="S1",
      )

    self.assertIsNone(assess1.issuetracker_issue)
    response = self.generate_children_issues_for(
        audit.type, audit.id, assess1.type
    )
    self.assert200(response)
    self.assertEqual(response.json.get("errors"), [])
    assess1 = all_models.Assessment.query.get(assess1_id)
    self.assertIsNotNone(
        assess1.issuetracker_issue,
        "issuetracker_issue was not created for assessment {}".format(
            assess1.id
        )
    )
    self.assertEqual("12345", assess1.issuetracker_issue.component_id)
    self.assertEqual("54321", assess1.issuetracker_issue.hotlist_id)
    self.assertEqual("P2", assess1.issuetracker_issue.issue_priority)
    self.assertEqual("S2", assess1.issuetracker_issue.issue_severity)
    assess2 = all_models.Assessment.query.get(assess2_id)

    self.assertEqual("9999", assess2.issuetracker_issue.component_id)
    self.assertEqual("7777", assess2.issuetracker_issue.hotlist_id)
    self.assertEqual("P1", assess2.issuetracker_issue.issue_priority)
    self.assertEqual("S1", assess2.issuetracker_issue.issue_severity)

  def test_bg_operation_status(self):
    """Test background operation status endpoint."""
    audit_id, _ = self.setup_assessments(3)
    response = self.generate_children_issues_for(
        "Audit", audit_id, "Assessment"
    )
    self.assert200(response)
    url = "background_task_status/{}/{}".format("audit", audit_id)
    response = self.api.client.get(url)
    self.assert200(response)
    self.assertEqual(response.json.get("status"), "Success")
    self.assertEqual(
        response.json.get("operation"),
        "generate_children_issues"
    )
    self.assertEqual(response.json.get("errors"), [])

  def test_task_already_run_status(self):
    """Test if new task started when another is in progress."""
    audit_id, _ = self.setup_assessments(1)
    response = self.generate_children_issues_for(
        "Audit", audit_id, "Assessment"
    )
    self.assert200(response)
    db.session.query(all_models.BackgroundTask).update({"status": "Running"})
    db.session.commit()

    with factories.single_commit():
      asmnt = factories.AssessmentFactory(audit_id=audit_id)
      audit = all_models.Audit.query.get(audit_id)
      factories.RelationshipFactory(source=audit, destination=asmnt)
      factories.IssueTrackerIssueFactory(
          issue_tracked_obj=asmnt,
          issue_id=None,
          title=None,
      )
    response = self.generate_children_issues_for(
        "Audit", audit_id, "Assessment"
    )
    self.assert400(response)
    self.assertEqual(
        response.json["message"],
        "Task 'generate_children_issues' already run for Audit {}.".format(
            audit_id
        )
    )

    url = "background_task_status/{}/{}".format("audit", audit_id)
    response = self.api.client.get(url)
    self.assert200(response)
    self.assertEqual(response.json.get("status"), "Running")
    self.assertEqual(
        response.json.get("operation"),
        "generate_children_issues"
    )
    self.assertEqual(response.json.get("errors"), [])

  def test_task_failed_status(self):
    """Test background task status if it failed."""
    audit_id, _ = self.setup_assessments(2)
    with mock.patch(
        "ggrc.integrations.issuetracker_bulk_sync."
        "IssueTrackerBulkChildCreator.sync_issuetracker",
        side_effect=Exception("Test Error")
    ):
      response = self.generate_children_issues_for(
          "Audit", audit_id, "Assessment"
      )
    self.assert200(response)
    url = "background_task_status/{}/{}".format("audit", audit_id)
    response = self.api.client.get(url)
    self.assert200(response)
    self.assertEqual(response.json.get("status"), "Failure")
    self.assertEqual(
        response.json.get("operation"),
        "generate_children_issues"
    )
    self.assertEqual(response.json.get("errors"), [])

  def test_errors_task_status(self):
    """Test background task status if it failed."""
    audit_id, assessment_ids = self.setup_assessments(2)
    with mock.patch(
        "ggrc.integrations.issues.Client.create_issue",
        side_effect=integrations_errors.HttpError("Test Error")
    ):
      response = self.api.send_request(
          self.api.client.post,
          api_link="/generate_children_issues",
          data={
              "parent": {"type": "Audit", "id": audit_id},
              "child_type": "Assessment"
          }
      )
    self.assert200(response)
    url = "background_task_status/{}/{}".format("audit", audit_id)
    response = self.api.client.get(url)
    self.assert200(response)
    self.assertEqual(response.json.get("status"), "Success")
    self.assertEqual(
        response.json.get("errors"),
        [["Assessment", id_, "500 Test Error"] for id_ in assessment_ids]
    )

  def test_child_err_notification(self):
    """Test notification about failed bulk child generation."""
    audit_id, _ = self.setup_assessments(3)
    _, side_user = self.gen.generate_person(user_role="Creator")
    self.api.set_user(side_user)
    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      response = self.generate_children_issues_for(
          "Audit", audit_id, "Assessment"
      )
    self.assert200(response)
    self.assertEqual(send_mock.call_count, 1)
    (email, title, body), _ = send_mock.call_args_list[0]
    cur_user = all_models.Person.query.get(side_user.id)
    self.assertEqual(email, cur_user.email)
    self.assertEqual(title, issuetracker_bulk_sync.ISSUETRACKER_SYNC_TITLE)
    self.assertIn("There were some errors in generating tickets", body)

  def test_child_notification(self):
    """Test notification about succeeded bulk child generation."""
    audit_id, _ = self.setup_assessments(3)
    with mock.patch("ggrc.notifications.common.send_email") as send_mock:
      response = self.generate_children_issues_for(
          "Audit", audit_id, "Assessment"
      )
    self.assert200(response)
    self.assertEqual(send_mock.call_count, 1)
    (email, title, body), _ = send_mock.call_args_list[0]
    self.assertEqual(email, "user@example.com")
    self.assertEqual(title, issuetracker_bulk_sync.ISSUETRACKER_SYNC_TITLE)
    title = all_models.Audit.query.get(audit_id).title
    self.assertIn(
        "Tickets generation for audit \"{}\" was completed".format(title),
        body
    )


@ddt.ddt
class TestBulkIssuesUpdate(TestBulkIssuesSync):
  """Test bulk issues update."""

  def test_asmnt_bulk_update(self):
    """Test bulk update of issues for Assessments."""
    _, assessment_ids = self.setup_assessments(3)

    issues = all_models.IssuetrackerIssue.query.filter(
        all_models.IssuetrackerIssue.object_type == "Assessment",
        all_models.IssuetrackerIssue.object_id.in_(assessment_ids)
    )
    for issue in issues:
      issue.enabled = 1
      issue.title = ""
      issue.component_id = "1"
      issue.hotlist_id = "1"
      issue.issue_type = "BUG"
      issue.issue_priority = "P2"
      issue.issue_severity = "S2"
      issue.assignee = "test@example.com"
      issue.cc_list = ""
      issue.issue_id = 123
      issue.issue_url = "http://issue/{}".format(self.issue_id)
    db.session.commit()

    asmnt_issuetracker_info = [
        ("Assessment", id_, "123", "321") for id_ in assessment_ids
    ]
    response = self.update_issues_for(asmnt_issuetracker_info)
    self.assert200(response)
    self.assertEqual(response.json.get("errors"), [])
    self.assert_obj_issues(asmnt_issuetracker_info)

  def test_issue_bulk_generate(self):
    """Test bulk update of issues for Issues."""
    issue_ids = []
    with factories.single_commit():
      for _ in range(3):
        issue = factories.IssueFactory()
        factories.IssueTrackerIssueFactory(
            enabled=True,
            issue_tracked_obj=issue,
            issue_id=self.issue_id,
            title="",
            component_id=12345,
            hotlist_id=54321,
            issue_priority="P2",
            issue_severity="S2",
        )
        issue_ids.append(issue.id)

    with factories.single_commit():
      person = factories.PersonFactory()
      for issue in all_models.Issue.query.all():
        issue.modified_by = person
        for role_name in ["Admin", "Primary Contacts"]:
          issue.add_person_with_role_name(person, role_name)

    # Verify that IssueTracker issues hasn't updated data
    issues = all_models.IssuetrackerIssue.query.filter(
        all_models.IssuetrackerIssue.object_type == "Issue",
        all_models.IssuetrackerIssue.object_id.in_(issue_ids)
    ).all()
    for issue in issues:
      parent_obj = issue.Issue_issue_tracked
      self.assertNotEqual(issue.title, parent_obj.title)
      self.assertEqual(issue.assignee, None)

    issue_issuetracker_info = [
        ("Issue", id_, None, None) for id_ in issue_ids
    ]
    response = self.update_issues_for(issue_issuetracker_info)
    self.assert200(response)
    self.assertEqual(response.json.get("errors"), [])

    # IssueTracker issues should be updated with proper values
    issues = all_models.IssuetrackerIssue.query.filter(
        all_models.IssuetrackerIssue.object_type == "Issue",
        all_models.IssuetrackerIssue.object_id.in_(issue_ids)
    ).all()
    for issue in issues:
      parent_obj = issue.Issue_issue_tracked
      self.assertEqual(issue.title, parent_obj.title)
      self.assertEqual(issue.cc_list, "")

  def test_rate_limited_update(self):
    """Test tickets update when issuetracker raise 429 error."""
    _, assessment_ids = self.setup_assessments(3)
    for issue in all_models.IssuetrackerIssue.query.all():
      issue.issue_id = self.issue_id
    db.session.commit()

    error = integrations_errors.HttpError(data="Test Error", status=429)
    with mock.patch(
        "ggrc.integrations.issues.Client.update_issue",
        side_effect=error
    ) as update_issue_mock:
      with mock.patch("time.sleep"):
        response = self.api.send_request(
            self.api.client.post,
            api_link="/update_issues",
            data={
                "objects": [{
                    "type": "Assessment",
                    "id": id_
                } for id_ in assessment_ids],
            }
        )
    self.assert200(response)
    expected_errors = [
        ["Assessment", id_, "429 Test Error"]
        for id_ in assessment_ids
    ]
    self.assertEqual(response.json.get("errors"), expected_errors)
    # 10 times for each assessment
    self.assertEqual(update_issue_mock.call_count, 30)

  @ddt.data("Issue", "Assessment")
  def test_get_issue_json(self, model):
    """Test get_issue_json method issue's update"""
    with factories.single_commit():
      factory = factories.get_model_factory(model)
      obj = factory()
      factories.IssueTrackerIssueFactory(
          enabled=True,
          issue_tracked_obj=obj,
          title='title',
          component_id=111,
          hotlist_id=222,
          issue_type="BUG",
          issue_priority="P2",
          issue_severity="S2",
      )
    expected_result = {
        'component_id': 111,
        'severity': u'S2',
        'title': u'title',
        'hotlist_ids': [222],
        'priority': u'P2',
        'type': u'BUG'
    }
    updater = issuetracker_bulk_sync.IssueTrackerBulkUpdater()
    # pylint: disable=protected-access
    result = updater._get_issue_json(obj)
    self.assertEqual(expected_result, result)
