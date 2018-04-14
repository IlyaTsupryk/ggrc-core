# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Cycle Task Entry RBAC Factory."""
from ggrc.models import all_models
from integration.ggrc import Api
from integration.ggrc.access_control.rbac_factories import base
from integration.ggrc.models import factories


class CycleTaskEntryRBACFactory(base.BaseRBACFactory):
  """Cycle Task Entry RBAC factory class."""

  def __init__(self, user_id, acr, parent=None):
    """Set up objects for Cycle Task Entry permission tests.

    Args:
        user_id: Id of user under which all operations will be run.
        acr: Instance of ACR that should be assigned for tested user.
        parent: Model name in scope of which objects should be set up.
    """
    # pylint: disable=unused-argument
    self.setup_workflow_scope(user_id, acr)
    self.api = Api()
    self.create()
    if user_id:
      user = all_models.Person.query.get(user_id)
      self.api.set_user(user)

  def create(self):
    """Create new Cycle Task Entry object."""
    cycle_task = all_models.CycleTaskGroupObjectTask.query.first()
    return self.api.post(all_models.CycleTaskEntry, {
        "cycle_task_entry": {
            "description": "New Comment",
            "is_declining_review": "",
            "context": None,
            "cycle_task_group_object_task": {
                "id": cycle_task.id,
                "type": "CycleTaskGroupObjectTask",
            },
            "cycle": {
                "id": cycle_task.cycle.id,
                "type": "Cycle",
            },
        }
    })

  def read(self):
    """Read existing Cycle Task Entry object."""
    cycle_task_entry = all_models.CycleTaskEntry.query.first()
    return self.api.get(cycle_task_entry, cycle_task_entry.id)

  def update(self):
    """Update title of existing Cycle Task Entry object."""
    cycle_task_entry = all_models.CycleTaskEntry.query.first()
    return self.api.put(
        cycle_task_entry,
        {"description": factories.random_str()}
    )

  def delete(self):
    """Delete Cycle Task Entry object."""
    cycle_task_entry = all_models.CycleTaskEntry.query.first()
    return self.api.delete(cycle_task_entry)
