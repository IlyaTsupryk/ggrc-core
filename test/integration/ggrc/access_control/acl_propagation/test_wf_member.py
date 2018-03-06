# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control roles Workflow Member propagation"""

import ddt

from ggrc.models import all_models
from integration.ggrc.access_control import rbac_factories
from integration.ggrc.access_control.acl_propagation import base
from integration.ggrc.utils import helpers


@ddt.ddt
class TestWfMemberPropagation(base.TestACLPropagation):
  """Test Workflow Member role permissions propagation"""

  PERMISSIONS = {
      "Creator": {
          "Workflow": {
              "read": True,
              "update": False,
              "delete": False,
              "read_revisions": True,
              "clone": False,
          },
          "TaskGroup": {
              "create": False,
              "read": True,
              "update": False,
              "delete": False,
              "read_revisions": True,
              "map_control": False,
              "map_created_control": False,
              "read_mapped_control": False,
              "upmap_control": False,
              "clone": False,
          },
          "TaskGroupTask": {
              "create": False,
              "read": True,
              "update": False,
              "delete": False,
              "read_revisions": True,
          },
          "Cycle": {
              "activate": False,
              "create": False,
              "read": True,
              "update": False,
              "delete": False,
              "end": False,
          },
          "CycleTaskGroup": {
              "read": True,
              "update": False,
              "delete": False,
          },
          "CycleTask": {
              "create": False,
              "read": True,
              "update": False,
              "delete": False,
              "map_control": False,
              "map_created_control": False,
              "read_mapped_control": False,
              "upmap_control": False,
              "start": False,
              "end": False,
              "verify": False,
              "decline": False,
              "restore": False,
          },
          "CycleTaskEntry": {
              "create": False,
              "read": True,
              "update": False,
              "delete": False,
          },
      },
      "Reader": {
          "Workflow": {
              "read": True,
              "update": False,
              "delete": False,
              "read_revisions": True,
              "clone": False,
          },
          "TaskGroup": {
              "create": False,
              "read": True,
              "update": False,
              "delete": False,
              "read_revisions": True,
              "map_control": False,
              "map_created_control": False,
              "read_mapped_control": True,
              "upmap_control": False,
              "clone": False,
          },
          "TaskGroupTask": {
              "create": False,
              "read": True,
              "update": False,
              "delete": False,
              "read_revisions": True,
          },
          "Cycle": {
              "activate": False,
              "create": False,
              "read": True,
              "update": False,
              "delete": False,
              "end": False,
          },
          "CycleTaskGroup": {
              "read": True,
              "update": False,
              "delete": False,
          },
          "CycleTask": {
              "create": False,
              "read": True,
              "update": False,
              "delete": False,
              "map_control": False,
              "map_created_control": False,
              "read_mapped_control": True,
              "upmap_control": False,
              "start": False,
              "end": False,
              "verify": False,
              "decline": False,
              "restore": False,
          },
          "CycleTaskEntry": {
              "create": False,
              "read": True,
              "update": False,
              "delete": False,
          },
      },
      "Editor": {
          "Workflow": {
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
              "clone": True,
          },
          "TaskGroup": {
              "create": True,
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
              "map_control": True,
              "map_created_control": True,
              "read_mapped_control": True,
              "upmap_control": True,
              "clone": True,
          },
          "TaskGroupTask": {
              "create": True,
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
          },
          "Cycle": {
              "activate": True,
              "create": True,
              "update": False,
              "delete": False,
              "read": True,
              "end": False,
          },
          "CycleTaskGroup": {
              "read": True,
              "update": False,
              "delete": False,
          },
          "CycleTask": {
              "create": True,
              "read": True,
              "update": True,
              "delete": False,
              "map_control": True,
              "map_created_control": True,
              "read_mapped_control": True,
              "upmap_control": True,
              "start": True,
              "end": True,
              "verify": True,
              "decline": True,
              "restore": True,
          },
          "CycleTaskEntry": {
              "create": True,
              "read": True,
              "update": True,
              "delete": True,
          },
      },
  }

  def init_factory(self, role, model, parent):
    """Initialize RBAC factory with propagated Workflow Member role.

    Args:
        role: Global Custom role that user have (Creator/Reader/Editor).
        model: Model name for which factory should be got.
        parent: Model name in scope of which objects should be installed.

    Returns:
        Initialized RBACFactory object.
    """
    self.setup_people()
    wf_member_acr = all_models.AccessControlRole.query.filter_by(
        name="Workflow Member",
        object_type="Workflow",
    ).first()

    rbac_factory = rbac_factories.get_factory(model)
    return rbac_factory(self.people[role].id, wf_member_acr, parent)

  @helpers.unwrap(PERMISSIONS)
  def test_access(self, role, model, action_name, expected_result):
    """Test {2} for {1} under Workflow Member {0}"""
    self.runtest(role, model, action_name, expected_result)
