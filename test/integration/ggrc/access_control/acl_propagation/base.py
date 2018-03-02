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

  STATUS_SUCCESS = [200, 201]
  STATUS_FORBIDDEN = [403,]

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

  def assert_result(self, responses, expected_res):
    exp_status = self.STATUS_SUCCESS if expected_res else self.STATUS_FORBIDDEN
    if not isinstance(responses, list):
      responses = [responses]
    for response in responses:
      self.assertIn(
          response.status_code,
          exp_status,
          "Response for current operation has wrong status.{} expected, "
          "{} received".format(str(exp_status), response.status_code)
      )


class TestAuditACLPropagation(TestACLPropagation):

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

  def generate(self, model, role):
    self.setup_base_objects(role)
    snapshot_id = self._create_snapshots(self.audit, [self.control])[0].id
    self.api.set_user(self.get_user_object(role))
    responses = []
    asmnt_data = {
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
    }
    responses.append(self.api.post(all_models.Assessment, asmnt_data))

    asmnt_data["assessment"]["template"] = {
        "id": self.template_id,
        "type": "AssessmentTemplate"
    }
    responses.append(self.api.post(all_models.Assessment, asmnt_data))
    return responses

  def create_object(self, model_name):
    method_name = "create_{}".format(model_name.lower())
    bound_method = getattr(self, method_name)
    if not bound_method:
      raise Exception("Method for creation '{}' does not implemented".
                      format(model_name))

    response = bound_method(model_name)
    if response.status_code in self.STATUS_FORBIDDEN:
      raise Exception("Can't create '{}' object. '{}' error".
                      format(model_name, response.status))
    return response.json.get(model_name.lower(), {}).get("id")

  def read(self, model, role):
    """Test access to model endpoint."""
    self.api.set_user(self.get_user_object(role))
    model_class = get_model(model)
    # ToDo: Check reading of single object also
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
    self.setup_base_objects(role)
    self.api.set_user(self.get_user_object(role))
    return self.api.post(all_models.Audit, {
        "audit": {
            "program": {"id": self.program_id},
            "context": None,
            "operation": "clone",
            "cloneOptions": {
                "sourceObjectId": self.audit_id,
                "mappedObjects": "AssessmentTemplate"
            }
        }
    })

  def read_revisions(self, model, role):
    self.setup_base_objects(role)
    self.api.set_user(self.get_user_object(role))
    model_class = get_model(model)
    responses = []
    for query in ["source_type={}&source_id={}",
                  "destination_type={}&destination_id={}",
                  "resource_type={}&resource_id={}"]:
      id_name = "{}_id".format(model.lower())
      id = getattr(self, id_name)
      responses.append(
          self.api.get_query(model_class, query.format(model, id))
      )
    return responses

  def map_snapshot(self, model, role):
    self.setup_base_objects(role)
    snapshot_id = self._create_snapshots(self.audit, [self.control])[0].id
    self.api.set_user(self.get_user_object(role))
    id_name = "{}_id".format(model.lower())
    id = getattr(self, id_name)
    response = self.api.post(all_models.Relationship, {
        "relationship": {
            "source": {
                "id": id,
                "type": model
            },
            "destination": {
                "id": snapshot_id,
                "type": "Snapshot"
            },
            "context": None
        }
    })
    return response

  def runtest(self, role, model, action_str, expected_result):
    action = getattr(self, action_str, None)
    if not action:
      raise NotImplementedError(
        "Action {} is not implemented for this test.".format(action_str)
      )
    self.assert_result(action(model, role), expected_result)
