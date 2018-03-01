# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control roles propagation base class"""
from ggrc.models import all_models, get_model
from integration.ggrc import TestCase
from integration.ggrc.models import factories
from integration.ggrc_basic_permissions.models \
    import factories as rbac_factories


class TestACLPropagation(TestCase):
  """TestACLPropagation base class with batch of helper methods"""

  GLOBAL_ROLES = ["Creator", "Reader", "Editor", "Administrator"]

  def get_user_object(self, role_name):
    return all_models.Person.query.get(self.people_ids[role_name])

  def setup_people(self):
    """Setup people with global roles"""
    self.people_ids = {}
    roles_query = all_models.Role.query.filter(
        all_models.Role.name.in_(self.GLOBAL_ROLES)
    )
    global_roles = {role.name: role for role in roles_query}

    with factories.single_commit():
      for role_name in self.GLOBAL_ROLES:
        user = factories.PersonFactory()
        self.people_ids[role_name] = user.id
        rbac_factories.UserRoleFactory(
            role=global_roles[role_name],
            person=user
        )


class TestAuditACLPropagation(TestACLPropagation):

  FORBIDDEN_RESPONSE_STATUSES = [403, ]
  SUCCESSFULL_RESPONSE_STATUSES = [200, 201]

  def setup_base_objects(self, global_role):
    raise NotImplementedError()

  def create_audit(self, model, role=None):
    self.setup_base_objects(role)
    if role:
      self.api.set_user(self.get_user_object(role))
    return self.api.post(all_models.Audit, {
        "audit": {
            "title": "New audit",
            "program": {"id": self.program_id},
            "context": None,
            "access_control_list": [],
        }
    })

  def create_assessment(self, model, role=None):
    self.setup_base_objects(role)
    if role:
      self.api.set_user(self.get_user_object(role))
    return self.api.post(all_models.Assessment, {
        "assessment": {
            "title": "New Assessment",
            "context": None,
            "audit": {"id": self.audit_id},
        },
    })

  def create_assessment_template(self, model, role=None):
    self.setup_base_objects(role)
    if role:
      self.api.set_user(self.get_user_object(role))
    return self.api.post(all_models.AssessmentTemplate, {
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

  def generate_asmnt_without_template(self, model, role):
    self.setup_base_objects(role)
    snapshot_id = self._create_snapshots(self.audit, [self.control])[0].id

    self.api.set_user(self.get_user_object(role))
    return self.api.post(all_models.Assessment, {
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

  def generate_asmnt_with_template(self, model, role):
    self.setup_base_objects(role)
    snapshot_id = self._create_snapshots(self.audit, [self.control])[0].id

    self.api.set_user(self.get_user_object(role))
    return self.api.post(all_models.Assessment, {
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

  def create_object(self, model_name):
    method_name = "create_{}".format(model_name.lower())
    bound_method = getattr(self, method_name)
    if not bound_method:
      raise Exception("Method for creation '{}' does not implemented".
                      format(model_name))

    response = bound_method(model_name)
    if response.status_code in self.FORBIDDEN_RESPONSE_STATUSES:
      raise Exception("Can't create '{}' object. '{}' error".
                      format(model_name, response.status))
    return response.json.get(model_name.lower(), {}).get("id")

  def read(self, model, role):
    """Test access to model endpoint."""
    self.api.set_user(self.get_user_object(role))
    model_class = get_model(model)
    # ToDo: Check reading single object also
    return self.api.get_query(model_class, "")

  def update(self, model, role):
    obj_id = self.create_object(model)
    self.api.set_user(self.get_user_object(role))
    model_class = get_model(model)
    obj = model_class.query.get(obj_id)
    return self.api.put(obj, {"title": factories.random_str()})

  def delete(self, model, role):
    obj_id = self.create_object(model)
    self.api.set_user(self.get_user_object(role))
    model_class = get_model(model)
    obj = model_class.query.get(obj_id)
    return self.api.delete(obj)

  def clone(self, model, role):
    return None

  def runtest(self, role, model, action_str, expected_result):
    action = getattr(self, action_str, None)
    if not action:
      raise NotImplementedError(
        "Action {} is not implemented for this test.".format(action_str)
      )
    response = action(model, role)
    expected_statuses = self.SUCCESSFULL_RESPONSE_STATUSES if expected_result \
      else self.FORBIDDEN_RESPONSE_STATUSES
    self.assertEqual(response.status_code in expected_statuses, True)
