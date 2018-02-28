# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control roles propagation base class"""
from ggrc.models import all_models
from integration.ggrc import TestCase
from integration.ggrc.models import factories
from integration.ggrc_basic_permissions.models \
    import factories as rbac_factories


class TestACLPropagation(TestCase):
  """TestACLPropagation base class with batch of helper methods"""

  GLOBAL_ROLES = ["Creator", "Reader", "Editor", "Administrator"]

  def setup_people(self):
    """Setup people with global roles"""
    self.people = {}
    roles_query = all_models.Role.query.filter(
        all_models.Role.name.in_(self.GLOBAL_ROLES)
    )
    global_roles = {role.name: role for role in roles_query}

    with factories.single_commit():
      for role_name in self.GLOBAL_ROLES:
        user = factories.PersonFactory()
        self.people[role_name] = user
        rbac_factories.UserRoleFactory(
            role=global_roles[role_name],
            person=user
        )


class TestAuditACLPropagation(TestACLPropagation):

  def setup_base_objects(self, global_role):
    raise NotImplementedError()

  def create_audit(self, model, role):
    self.setup_base_objects(role)
    self.api.set_user(self.people[role])
    response = self.api.post(all_models.Audit, {
        "audit": {
            "title": "New audit",
            "program": {"id": self.program_id},
            "context": None,
            "access_control_list": [],
        }
    })
    if response.status_code == 201:
      return True
    elif response.status_code == 403:
      return False
    else:
      raise Exception(
          "Creation of Audit resulted with {}".format(response.status_code)
      )

  def create_assessment(self, model, role):
    self.setup_base_objects(role)
    self.api.set_user(self.people[role])
    response = self.api.post(all_models.Assessment, {
        "assessment": {
            "title": "New Assessment",
            "context": None,
            "audit": {"id": self.audit_id},
        },
    })
    if response.status_code == 201:
      return True
    elif response.status_code == 403:
      return False
    else:
      raise Exception(
          "Creation of Assessment resulted with {}".format(response.status_code)
      )

  def create_assessment_template(self, model, role):
    self.setup_base_objects(role)
    self.api.set_user(self.people[role])
    response = self.api.post(all_models.AssessmentTemplate, {
        "assessment_template": {
            "audit": {"id": self.audit_id},
            "context": None,
            "default_people": {
                "assignees": "Admin",
                "verifiers": "Admin",
            },
            "title": "New Assessment Template"
        }
    })
    if response.status_code == 201:
      return True
    elif response.status_code == 403:
      return False
    else:
      raise Exception(
        "Creation of Assessment resulted with {}".format(response.status_code)
      )

  def generate_asmnt_without_template(self, model, role):
    self.setup_base_objects(role)
    snapshot_id = self._create_snapshots(self.audit, [self.control])[0].id

    self.api.set_user(self.people[role])
    response = self.api.post(all_models.Assessment, {
        "assessment": {
            "_generated": True,
            "audit": {
                "id": self.audit_id,
                "type": "Audit"
            },
            "object": {
                "id": snapshot_id,
                "type": "Snapshot"
            },
            "context": None,
            "title": "New assessment",
        }
    })

    if response.status_code == 201:
      return True
    elif response.status_code == 403:
      return False
    else:
      raise Exception(
          "Creation of Assessment resulted with {}".format(response.status_code)
      )

  def generate_asmnt_with_template(self, model, role):
    self.setup_base_objects(role)
    snapshot_id = self._create_snapshots(self.audit, [self.control])[0].id

    self.api.set_user(self.people[role])
    response = self.api.post(all_models.Assessment, {
        "assessment": {
            "_generated": True,
            "audit": {
                "id": self.audit_id,
                "type": "Audit"
            },
            "object": {
                "id": snapshot_id,
                "type": "Snapshot"
            },
            "context": None,
            "title": "New assessment",
            "template": {
                "id": self.template_id,
                "type": "AssessmentTemplate"
            },
        }
    })

    if response.status_code == 201:
      return True
    elif response.status_code == 403:
      return False
    else:
      raise Exception(
          "Creation of Assessment resulted with {}".format(response.status_code)
      )

  def create(self, model, role):
    return True

  def read(self, model, role):
    return True

  def update(self, model, role):
    return True

  def delete(self, model, role):
    return True

  def clone(self, model, role):
    return True

  def runtest(self, role, model, action_str, expected_result):
    action = getattr(self, action_str, None)
    if not action:
      raise NotImplementedError(
        "Action {} is not implemented for this test.".format(action_str)
      )
    action_result = action(model, role)
    self.assertEqual(action_result, expected_result)
