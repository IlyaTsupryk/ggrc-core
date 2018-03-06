# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Audit RBAC Factory."""
import sqlalchemy as sa

from ggrc import db
from ggrc.models import all_models
from integration.ggrc import Api
from integration.ggrc.models import factories
from integration.ggrc_workflows.models import factories as wf_factories


class BaseRBACFactory(object):
  """Base RBAC factory class."""
  # pylint: disable=too-few-public-methods

  def setup_program_scope(self, user_id, acr, parent=None):
    """Set up base set of objects for permission tests of Program scope models.

    Args:
        acr: Instance of ACR that should be assigned for tested user.
        parent: Model name in scope of which objects should be set up.
    """
    # pylint: disable=attribute-defined-outside-init
    with factories.single_commit():
      self.program = factories.ProgramFactory()
      self.program_id = self.program.id
      self.assign_person(self.program, acr, user_id)
      if parent == "Program":
        return
      self.audit = factories.AuditFactory(program=self.program)
      self.audit_id = self.audit.id
      self.assign_person(self.audit, acr, user_id)
      if parent == "Audit":
        return
      self.assessment = factories.AssessmentFactory(audit=self.audit)
      self.assessment_id = self.assessment.id
      self.assign_person(self.assessment, acr, user_id)
      factories.RelationshipFactory(
          source=self.audit, destination=self.assessment
      )

  def setup_workflow_scope(self, user_id, acr):
    """Set up base set of objects for permission tests of Workflow models.

    Args:
        acr: Instance of ACR that should be assigned for tested user.
        parent: Model name in scope of which objects should be set up.
    """
    with factories.single_commit():
      self.workflow = wf_factories.WorkflowFactory()
      self.workflow_id = self.workflow.id
      self.assign_person(self.workflow, acr, user_id)

      self.task_group = wf_factories.TaskGroupFactory(workflow=self.workflow)
      self.task_group_id = self.task_group.id

      self.task = wf_factories.TaskGroupTaskFactory(task_group=self.task_group)
      self.task_id = self.task.id
      self.assign_person(self.task, acr, user_id)

    self.generate_cycle(self.workflow_id)
    cycle_task = all_models.CycleTaskGroupObjectTask.query.first()
    self.assign_person(cycle_task, acr, user_id)

  @staticmethod
  def generate_cycle(workflow_id, api=None):
    """Create cycle with task automatically."""
    if not api:
      api = Api()
    return api.post(all_models.Cycle, {
        "cycle": {
            "context": None,
            "autogenerate": True,
            "isOverdue": False,
            "workflow": {
                "id": workflow_id,
                "type": "Workflow",
            },
        }
    })

  def assign_person(self, object_, acr, person_id):
    """Assign person to object."""
    if sa.inspect(acr).detached:
      db.session.add(acr)
    if object_.type == acr.object_type:
      factories.AccessControlListFactory(
          object=object_,
          person_id=person_id,
          ac_role=acr,
      )
