# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control roles Assignees propagation"""

import ddt

from ggrc.models import all_models
from integration.ggrc import Api
from integration.ggrc.access_control.acl_propagation import base
from integration.ggrc.models import factories
from integration.ggrc.utils import helpers


@ddt.ddt
class TestAssigneesPropagation(base.TestAuditACLPropagation):
  """Test Assignees role permissions propagation"""

  PERMISSIONS = {
      "Creator": {
          "Assessment": {
              "read": True,
              "update": True,
              "delete": False,
              "map_snapshot": False,
          },
      },
      "Reader": {
          "Assessment": {
              "read": True,
              "update": True,
              "delete": False,
              "map_snapshot": False,
          },
      },
      "Editor": {
          "Assessment": {
              "read": True,
              "update": True,
              "delete": True,
              "map_snapshot": True,
          },
      },
  }

  def setUp(self):
    super(TestAssigneesPropagation, self).setUp()
    self.assignees_acr = all_models.AccessControlRole.query.filter_by(
        name="Assignees"
    ).first()
    self.api = Api()
    self.setup_people()

  def setup_base_objects(self, global_role):
    with factories.single_commit():
      if global_role is not None:
        person = self.get_user_object(global_role)
      else:
        person = self.get_user_object("Administrator")

      self.program_id = factories.ProgramFactory().id
      self.audit = factories.AuditFactory(program_id=self.program_id)
      self.audit_id = self.audit.id
      self.assessment = factories.AssessmentFactory(
          audit=self.audit,
          access_control_list=[{
              "ac_role": self.assignees_acr,
              "person": person
          }]
      )
      self.assessment_id = self.assessment.id
      self.control = factories.ControlFactory()
      self.template_id = factories.AssessmentTemplateFactory(
          audit=self.audit
      ).id

  @helpers.unwrap(PERMISSIONS)
  def test_CRUD(self, role, model, action_str, expected_result):
    """Test {2} for {1} under Assignee {0}"""
    self.runtest(role, model, action_str, expected_result)
