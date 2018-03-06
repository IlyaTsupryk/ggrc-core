# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""WF Cycle RBAC Factory."""

from ggrc.models import all_models
from integration.ggrc import Api
from integration.ggrc.access_control.rbac_factories import base
from integration.ggrc.models import factories
from integration.ggrc_workflows.models import factories as wf_factories


class CycleRBACFactory(base.BaseRBACFactory):
  """Cycle RBAC factory class."""

  def __init__(self, user_id, acr, parent=None):
    """Set up objects for Cycle permission tests.

    Args:
        user_id: Id of user under which all operations will be run.
        object_acl: Dict with format: {
        acr: Instance of ACR that should be assigned for tested user.
        parent: Model name in scope of which objects should be set up.
    """
    self.setup_workflow_scope(user_id, acr)
    self.api = Api()
    if user_id:
      user = all_models.Person.query.get(user_id)
      self.api.set_user(user)

  def create(self):
    """Create new cycle for Workflow."""
    return self.generate_cycle(self.workflow_id, self.api)

  def update(self):
    """Update existing cycle."""
    cycle = all_models.Cycle.query.first()
    return self.api.put(cycle, {"title": factories.random_str()})

  def delete(self):
    """Delete existing cycle."""
    cycle = all_models.Cycle.query.first()
    return self.api.delete(cycle)

  def activate(self):
    """Activate Workflow."""
    workflow = all_models.Workflow.query.get(self.workflow_id)
    cycle = wf_factories.CycleFactory(workflow=workflow)
    return self.api.put(workflow, {
        "status": "Active",
        "recurrences": bool(workflow.repeat_every and workflow.unit),
        "cycles": [{
            "id": cycle.id,
            "type": "Cycle",
        }]
    })

  def read(self):
    """Read existing Cycle object."""
    cycle = all_models.Cycle.query.first()
    return self.api.get(cycle, cycle.id)

  def end(self):
    """End existing Cycle."""
    cycle = all_models.Cycle.query.first()
    return self.api.put(cycle, {"is_current": False})
