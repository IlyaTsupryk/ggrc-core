# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test /generate_issues endpoint."""
import ddt
import mock

from ggrc import utils as ggrc_utils
from ggrc.access_control import role
from ggrc.integrations import utils as issue_utils
from ggrc.models import all_models
from integration.ggrc import TestCase, generator
from integration.ggrc.api_helper import Api
from integration.ggrc.models import factories


@ddt.ddt
class TestBulkIssuesGenerate(TestCase):
  """Test /generate_issues for Audit."""

  def setUp(self):
    """Set up for test methods."""
    super(TestBulkIssuesGenerate, self).setUp()
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
      audit_id = audit.id
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

      asmnt_ids = []
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
        asmnt_ids.append(asmnt.id)
      return audit_id, asmnt_ids

  def generate_asmnt_issues_for(self, obj_type, obj_id):
    """Generate IssueTracker issue for objects with provided type and ids.

    Args:
        obj_type: Type of objects. Now only 'Assessment' supported.
        obj_ids: List with ids of objects.

    Returns:
        Response with result of Issues generation.
    """
    client_mock = mock.MagicMock()
    client_mock.create_issue = lambda arg: dict(
        arg, **{"issueId": self.issue_id}
    )
    client_patch = mock.patch.object(
        issue_utils.issues,
        "Client",
        return_value=client_mock
    )
    with client_patch:
      return self.api.send_request(
          self.api.client.post,
          api_link="/generate_children_issues",
          data={
              "parent": {"type": obj_type, "id": obj_id},
              "child_type": "Assessment"
          }
      )

  def assert_asmnt_issues(self, assessment_ids):
    """Check correctness of Assessments IssueTracker issues.

    Args:
        assessment_ids: List with ids of Assessments to check.

    Raise:
        AssertionError in case of inconsistency Issue and Assessment.
    """
    asmnts = all_models.Assessment.query.filter(
        all_models.Assessment.id.in_(assessment_ids)
    )
    for asmnt in asmnts:
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

  def test_issues_generate(self):
    """Test generation of issues for all Assessments in Audit."""
    audit_id, asmnt_ids = self.setup_assessments(3)
    response = self.generate_asmnt_issues_for("Audit", audit_id)
    self.assert200(response)
    self.assertEqual(response.json.get("errors"), [])
    self.assert_asmnt_issues(asmnt_ids)

  def test_norights(self):
    """Test generation if user doesn't have rights on Audit and Assessment."""
    audit_id, _ = self.setup_assessments(3)
    _, side_user = self.gen.generate_person(user_role="Creator")
    self.api.set_user(side_user)
    response = self.generate_asmnt_issues_for("Audit", audit_id)
    self.assert403(response)

  def test_partially_rights(self):
    """Test generation if user has rights on part of Assessments."""
    audit_id, asmnt_ids = self.setup_assessments(3)
    _, assignee_user = self.gen.generate_person(user_role="Creator")
    changed_asmnt_id = asmnt_ids[0]
    norights_asmnt_ids = asmnt_ids[1:]
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
    response = self.generate_asmnt_issues_for("Audit", audit_id)
    self.assert200(response)
    self.assert_asmnt_issues([changed_asmnt_id])
    self.assert_not_updated("Assessment", norights_asmnt_ids)

  @ddt.data(1, 3, 10)
  def test_const_query_count(self, asmnt_count):
    """Test query count on generation for {} Assessments."""
    audit_id, asmnt_ids = self.setup_assessments(asmnt_count)

    with ggrc_utils.QueryCounter() as counter:
      response = self.generate_asmnt_issues_for("Audit", audit_id)
    self.assert200(response)
    self.assertEqual(response.json.get("errors"), [])
    self.assertEqual(counter.get, 25)
    self.assert_asmnt_issues(asmnt_ids)
