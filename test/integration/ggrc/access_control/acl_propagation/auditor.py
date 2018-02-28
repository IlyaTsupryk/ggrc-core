import ddt

from ggrc.models import all_models
from integration.ggrc import Api
from integration.ggrc.access_control.acl_propagation import base
from integration.ggrc.models import factories
from integration.ggrc.utils import helpers


@ddt.ddt
class TestAuditorPropagation(base.TestAuditACLPropagation):
  """Test Auditor role permissions propagation"""

  PERMISSIONS = {
      "Creator": {
          "Audit": {
              "create_audit": False,
              "read": True,
              "update": True,
              "delete": True,
          },
          "Assessment": {
              "create_assessment": True,
              "generate_asmnt_without_template": True,
              "generate_asmnt_with_template": True,
              "read": True,
              "update": True,
              "delete": True,
          },
          "Assessment Template": {
              "create_assessment_template": False,
          }
      },
      "Reader": {
          "Audit": {
              "create_audit": False,
              "read": True,
              "update": True,
              "delete": True,
          },
          "Assessment": {
              "create_assessment": True,
              "generate_asmnt_without_template": True,
              "generate_asmnt_with_template": True,
              "read": True,
              "update": True,
              "delete": True,
          },
          "Assessment Template": {
              "create_assessment_template": False,
          }
      },
      "Editor": {
          "Audit": {
              "create_audit": True,
              "read": True,
              "update": True,
              "delete": True,
          },
          "Assessment": {
              "create_assessment": True,
              "generate_asmnt_without_template": True,
              "generate_asmnt_with_template": True,
              "read": True,
              "update": True,
              "delete": True,
          },
          "Assessment Template": {
              "create_assessment_template": True,
          }
      },
  }

  def setUp(self):
    super(TestAuditorPropagation, self).setUp()
    self.auditor_acr = all_models.AccessControlRole.query.filter_by(
        name="Auditors"
    ).first()
    self.api = Api()
    self.setup_people()

  def setup_base_objects(self, global_role):
    with factories.single_commit():
      self.program_id = factories.ProgramFactory().id
      self.audit = factories.AuditFactory(
          program_id=self.program_id,
          access_control_list=[{
              "ac_role": self.auditor_acr,
              "person": self.people[global_role]
          }]
      )
      self.audit_id = self.audit.id
      self.control = factories.ControlFactory()
      self.template_id = factories.AssessmentTemplateFactory(
          audit=self.audit,
      ).id

  @helpers.unwrap(PERMISSIONS)
  def test_CRUD(self, role, model, action_str, expected_result):
    """Test {2} for {1} under Auditor {0}"""
    self.runtest(role, model, action_str, expected_result)
