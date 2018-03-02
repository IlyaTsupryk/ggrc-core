# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control roles Assignees propagation"""

import ddt

from ggrc.models import all_models
from integration.ggrc import Api
from integration.ggrc.access_control import rbac_factories
from integration.ggrc.access_control.acl_propagation import base
from integration.ggrc.models import factories
from integration.ggrc.utils import helpers


@ddt.ddt
class TestAssigneesPropagation(base.TestACLPropagation):
  """Test Assignees role permissions propagation"""

  PERMISSIONS = {
      "Creator": {
          "Assessment": {
              "read": True,
              "update": True,
              "delete": False,
              "map_snapshot": False,
              "read_revisions": True,
          },
      },
      "Reader": {
          "Assessment": {
              "read": True,
              "update": True,
              "delete": False,
              "map_snapshot": False,
              "read_revisions": True,
          },
      },
      "Editor": {
          "Assessment": {
              "read": True,
              "update": True,
              "delete": True,
              "map_snapshot": True,
              "read_revisions": True,
          },
      },
  }

  def setUp(self):
    super(TestAssigneesPropagation, self).setUp()
    self.api = Api()
    self.assignees_acr = all_models.AccessControlRole.query.filter_by(
        name="Assignees"
    ).first()
    self.setup_people()

  @helpers.unwrap(PERMISSIONS)
  def test_CRUD(self, role, model, action_name, expected_result):
    """Test {2} for {1} under Assignee {0}"""
    audit_id = factories.AuditFactory().id
    assessment_id = factories.AssessmentFactory(
        audit_id=audit_id,
        access_control_list=[{
            "ac_role": self.assignees_acr,
            "person": self.get_user_object(role)
        }]
    ).id
    rbac_factory = rbac_factories.get_factory(model)(
        audit_id, assessment_id, self.get_user_object(role)
    )
    action = getattr(rbac_factory, action_name, None)
    if not action:
      raise NotImplementedError(
          "Action {} is not implemented for this test.".format(action_name)
      )

    self.assert_result(action(), expected_result)
