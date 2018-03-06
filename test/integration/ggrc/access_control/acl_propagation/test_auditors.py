# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control roles Auditors propagation."""

import ddt

from ggrc.models import all_models
from integration.ggrc.access_control import rbac_factories
from integration.ggrc.access_control.acl_propagation import base
from integration.ggrc.utils import helpers


@ddt.ddt
class TestAuditorsPropagation(base.TestACLPropagation):
  """Test Auditor role permissions propagation."""

  PERMISSIONS = {
      "Creator": {
          "Audit": {
              "read": True,
              "update": False,
              "delete": False,
              "clone": False,
              "read_revisions": True,
              "map_external_control": False,
              "map_control": False,
              "deprecate": False,
              "archive": False,
              "unarchive": False,
              "summary": True,
          },
          "Assessment": {
              "create": True,
              "generate": True,
              "read": True,
              "update": True,
              "delete": False,
              "read_revisions": True,
              "map_snapshot": True,
              "deprecate": True,
              "map_comment": True,
              "map_document": True,
              "related_assessments": True,
              "related_objects": True,
              "complete": True,
              "in_progress": True,
              "not_started": True,
              "decline": False,
              "verify": False,
          },
          "AssessmentTemplate": {
              "create": False,
              "read": True,
              "update": False,
              "delete": False,
              "read_revisions": True,
          },
          "Snapshot Assessment": {
              "read": True,
              "read_original": False,
              "update": False,
              "get_latest_version": False,
          },
          "Snapshot Audit": {
              "read": True,
              "read_original": False,
              "update": False,
              "get_latest_version": False,
          },
          "Issue Assessment": {
              "read": True,
              "update": True,
              "delete": False,
              "read_revisions": True,
              "map": False,
              "create_and_map": True,
              "raise_issue": True,
              "unmap": True,
          },
          "Issue Audit": {
              "read": True,
              "update": True,
              "delete": False,
              "read_revisions": True,
              "map": False,
              "create_and_map": False,
              "unmap": False,
          },
      },
      "Reader": {
          "Audit": {
              "read": True,
              "update": False,
              "delete": False,
              "clone": False,
              "read_revisions": True,
              "map_control": False,
              "map_external_control": False,
              "deprecate": False,
              "archive": False,
              "unarchive": False,
              "summary": True,
          },
          "Assessment": {
              "create": True,
              "generate": True,
              "read": True,
              "update": True,
              "delete": False,
              "read_revisions": True,
              "map_snapshot": True,
              "deprecate": True,
              "map_comment": True,
              "map_document": True,
              "related_assessments": True,
              "related_objects": True,
              "complete": True,
              "in_progress": True,
              "not_started": True,
              "decline": False,
              "verify": False,
          },
          "AssessmentTemplate": {
              "create": False,
              "read": True,
              "update": False,
              "delete": False,
              "read_revisions": True,
          },
          "Snapshot Assessment": {
              "read": True,
              "read_original": True,
              "update": False,
              "get_latest_version": True,
          },
          "Snapshot Audit": {
              "read": True,
              "read_original": True,
              "update": False,
              "get_latest_version": True,
          },
          "Issue Assessment": {
              "read": True,
              "update": True,
              "delete": False,
              "read_revisions": True,
              "map": False,
              "create_and_map": True,
              "raise_issue": True,
              "unmap": True,
          },
          "Issue Audit": {
              "read": True,
              "update": True,
              "delete": False,
              "read_revisions": True,
              "map": False,
              "create_and_map": False,
              "unmap": False,
          },
      },
      "Editor": {
          "Audit": {
              "read": True,
              "update": True,
              "delete": True,
              "clone": True,
              "read_revisions": True,
              "map_control": True,
              "map_external_control": True,
              "deprecate": True,
              "archive": False,
              "unarchive": False,
              "summary": True,
          },
          "Assessment": {
              "create": True,
              "generate": True,
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
              "map_snapshot": True,
              "deprecate": True,
              "map_comment": True,
              "map_document": True,
              "related_assessments": True,
              "related_objects": True,
              "complete": True,
              "in_progress": True,
              "not_started": True,
              "decline": False,
              "verify": False,
          },
          "AssessmentTemplate": {
              "create": True,
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
          },
          "Snapshot Assessment": {
              "read": True,
              "read_original": True,
              "update": True,
              "get_latest_version": True,
          },
          "Snapshot Audit": {
              "read": True,
              "read_original": True,
              "update": True,
              "get_latest_version": True,
          },
          "Issue Assessment": {
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
              "map": True,
              "create_and_map": True,
              "raise_issue": True,
              "unmap": True,
          },
          "Issue Audit": {
              "read": True,
              "update": True,
              "delete": True,
              "read_revisions": True,
              "map": True,
              "create_and_map": True,
              "unmap": True,
          },
      },
  }

  def init_factory(self, role, model, parent):
    """Initialize RBAC factory with propagated Auditors role.

    Args:
        role: Global Custom role that user have (Creator/Reader/Editor).
        model: Model name for which factory should be got.
        parent: Model name in scope of which objects should be installed.

    Returns:
        Initialized RBACFactory object.
    """
    self.setup_people()
    auditor_acr = all_models.AccessControlRole.query.filter_by(
        name="Auditors",
        object_type="Audit",
    ).first()

    rbac_factory = rbac_factories.get_factory(model)
    return rbac_factory(self.people[role].id, auditor_acr, parent)

  @helpers.unwrap(PERMISSIONS)
  def test_access(self, role, model, action_name, expected_result):
    """Test {2} for {1} under Auditors {0}"""
    self.runtest(role, model, action_name, expected_result)
