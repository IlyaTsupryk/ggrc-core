# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control roles propagation base class"""
from ggrc import db
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

  TEST_ROLE = None

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

  def create(self, model, role=None):
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

  def read(self, model, role):
    """Test access to model endpoint."""
    self.api.set_user(self.get_user_object(role))
    audit = all_models.Audit.query.get(self.audit_id)
    responses = []
    responses.append(self.api.get_query(all_models.Audit, ""))
    responses.append(self.api.get_query(all_models.Audit, audit.id))
    return responses

  def update(self, model, role):
    self.api.set_user(self.get_user_object(role))
    audit = all_models.Audit.query.get(self.audit_id)
    return self.api.put(audit, {"title": factories.random_str()})

  def delete(self, model, role):
    self.api.set_user(self.get_user_object(role))
    audit = all_models.Audit.query.get(self.audit_id)
    return self.api.delete(audit)

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


class TestAssessmentACLPropagation(TestACLPropagation):

  # def setup_audit(self, global_role):
  #
  #   self.asmnt_acr = all_models.AccessControlRole.query.filter_by(
  #       name=self.TEST_ROLE
  #   ).first()
  #
  #   with factories.single_commit():
  #     person = self.get_user_object(global_role)
  #
  #     self.program_id = factories.ProgramFactory().id
  #     self.audit = factories.AuditFactory(
  #         program_id=self.program_id,
  #         access_control_list=[{
  #             "ac_role": self.asmnt_acr,
  #             "person": person,
  #         }]
  #     )
  #     self.audit_id = self.audit.id
  #     # self.control = factories.ControlFactory()
  #     # self.template_id = factories.AssessmentTemplateFactory(
  #     #     audit=self.audit,
  #     # ).id
  #     # self.assessment_id = factories.AssessmentFactory(audit=self.audit).id

  def setup_assessment(self, global_role):
    self.asmnt_acr = all_models.AccessControlRole.query.filter_by(
          name=self.TEST_ROLE
      ).first()

    with factories.single_commit():
      self.program_id = factories.ProgramFactory().id
      self.audit = factories.AuditFactory(program_id=self.program_id)
      self.audit_id = self.audit.id
      self.assessment = factories.AssessmentFactory(
        audit=self.audit,
        access_control_list=[{
          "ac_role": self.asmnt_acr,
          "person": self.get_user_object(global_role)
        }]
      )
      self.assessment_id = self.assessment.id
      self.control = factories.ControlFactory()
      self.template_id = factories.AssessmentTemplateFactory(
        audit=self.audit
      ).id

  # def create(self, model, role):
  #   self.setup_assessment(role)
  #   self.api.set_user(self.get_user_object(role))
  #   return self.api.post(all_models.Assessment, {
  #       "assessment": {
  #           "title": "New Assessment",
  #           "context": None,
  #           "audit": {"id": self.audit_id},
  #       },
  #   })
  #
  # def generate(self, model, role):
  #   self.setup_assessment(role)
  #   snapshot_id = self._create_snapshots(self.audit, [self.control])[0].id
  #   self.api.set_user(self.get_user_object(role))
  #
  #   responses = []
  #   asmnt_data = {
  #       "assessment": {
  #           "_generated": True,
  #           "audit": {
  #               "id": self.audit_id,
  #               "type": "Audit"
  #           },
  #           "object": {
  #               "id": snapshot_id,
  #               "type": "Snapshot"
  #           },
  #           "context": None,
  #           "title": "New assessment",
  #       }
  #   }
  #   responses.append(self.api.post(all_models.Assessment, asmnt_data))
  #
  #   asmnt_data["assessment"]["template"] = {
  #       "id": self.template_id,
  #       "type": "AssessmentTemplate"
  #   }
  #   responses.append(self.api.post(all_models.Assessment, asmnt_data))
  #   return responses
  #
  # def read(self, model, role):
  #   """Test access to model endpoint."""
  #   self.setup_assessment(role)
  #   asmnt_id = factories.AssessmentFactory(audit=self.audit).id
  #   self.api.set_user(self.get_user_object(role))
  #
  #   responses = []
  #   responses.append(self.api.get_query(all_models.Assessment, ""))
  #   #responses.append(self.api.get_query(all_models.Assessment, asmnt_id))
  #   return responses
  #
  # def update(self, model, role):
  #   self.setup_assessment(role)
  #   self.api.set_user(self.get_user_object(role))
  #
  #   asmnt = all_models.Assessment.query.get(self.assessment_id)
  #   return self.api.put(asmnt, {"title": factories.random_str()})
  #
  # def delete(self, model,role):
  #   self.setup_assessment(role)
  #   self.api.set_user(self.get_user_object(role))
  #
  #   asmnt = all_models.Assessment.query.get(self.assessment_id)
  #   return self.api.delete(asmnt)
  #
  # def base_action(self, model, role):
  #
