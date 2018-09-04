# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test bulk issuetracker synchronization."""
import ddt
import mock

from ggrc import db
from ggrc.access_control import role
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

  def setup_assessments(self, asmnt_count):
    """Create Audit with couple of Assessments and linked IssueTrackerIssues.

    Args:
        asmnt_count: Count of Assessments in Audit.

    Returns:
        Tuple with Audit id and list of Assessment ids.
    """
    with factories.single_commit():
      audit = factories.AuditFactory()
      factories.AccessControlListFactory(
          object=audit,
          ac_role=role.get_ac_roles_for(audit.type)["Audit Captains"],
          person=self.role_people["Audit Captains"],
      )
      factories.IssueTrackerIssueFactory(
          issue_tracked_obj=audit,
          issue_id=None,
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
          factories.AccessControlListFactory(
              object=asmnt,
              ac_role=role.get_ac_roles_for(asmnt.type)[role_name],
              person=self.role_people[role_name],
          )
        factories.IssueTrackerIssueFactory(
            issue_tracked_obj=asmnt,
            issue_id=None,
            title=None,
        )
        assessment_ids.append(asmnt.id)
      return audit.id, assessment_ids

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
              "child_type": child_type
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
      self.assertEqual(issue.issue_type, None)
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


class TestBulkIssuesGenerate(TestBulkIssuesSync):
  """Test bulk issues generation."""

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

  def test_permission_check(self):
    """Test generation if user has rights on part of objects."""
    _, assessment_ids = self.setup_assessments(3)
    with_rights_ids = assessment_ids[:2]
    without_rights_ids = assessment_ids[2:]
    _, assignee_user = self.gen.generate_person(user_role="Creator")

    with factories.single_commit():
      for id_ in with_rights_ids:
        factories.AccessControlListFactory(
            object_id=id_,
            object_type="Assessment",
            ac_role_id=role.get_ac_roles_for("Assessment")["Creators"].id,
            person_id=assignee_user.id,
        )

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
          factories.AccessControlListFactory(
              object=issue,
              ac_role=role.get_ac_roles_for(issue.type)[role_name],
              person=person,
          )
        factories.IssueTrackerIssueFactory(
            issue_tracked_obj=issue,
            issue_id=None,
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


@ddt.ddt
class TestBulkIssuesChildGenerate(TestBulkIssuesSync):
  """Test bulk issues generation for child objects."""

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

    with factories.single_commit():
      factories.AccessControlListFactory(
          object_id=changed_asmnt_id,
          object_type="Assessment",
          ac_role_id=role.get_ac_roles_for("Assessment")["Creators"].id,
          person_id=assignee_user.id,
      )
      audit_role = factories.AccessControlRoleFactory(
          name="Edit Role",
          object_type="Audit",
          update=True
      )
      factories.AccessControlListFactory(
          object_id=audit_id,
          object_type="Audit",
          ac_role_id=audit_role.id,
          person_id=assignee_user.id,
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
      issue.title = "test title"
      issue.component_id = "1"
      issue.hotlist_id = "1"
      issue.issue_type = "test tipe"
      issue.issue_priority = "P1"
      issue.issue_severity = "S1"
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
    self.assert_obj_issues(asmnt_issuetracker_info, "assignees@example.com")

  def test_issue_bulk_generate(self):
    """Test bulk update of issues for Issues."""
    issue_ids = []
    with factories.single_commit():
      for _ in range(3):
        issue = factories.IssueFactory()
        factories.IssueTrackerIssueFactory(
            issue_tracked_obj=issue,
            issue_id=self.issue_id,
            component_id=12345,
            hotlist_id=54321,
            issue_priority="P2",
            issue_severity="S2",
        )
        issue_ids.append(issue.id)

    with factories.single_commit():
      person = factories.PersonFactory()
      person_email = person.email
      for issue in all_models.Issue.query.all():
        issue.modified_by = person
        for role_name in ["Admin", "Primary Contacts"]:
          factories.AccessControlListFactory(
              object=issue,
              ac_role=role.get_ac_roles_for(issue.type)[role_name],
              person=person,
          )

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
      self.assertEqual(issue.assignee, person_email)
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
