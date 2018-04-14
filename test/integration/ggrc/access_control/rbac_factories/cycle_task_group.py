# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Cycle Task Group RBAC Factory."""
from ggrc import access_control
from ggrc.models import all_models
from integration.ggrc import Api
from integration.ggrc.access_control.rbac_factories import base
from integration.ggrc.models import factories


class CycleTaskGroupRBACFactory(base.BaseRBACFactory):
  """Cycle Task Group RBAC factory class."""

  def __init__(self, user_id, acr, parent=None):
    """Set up objects for Cycle Task Group permission tests.

    Args:
        user_id: Id of user under which all operations will be run.
        acr: Instance of ACR that should be assigned for tested user.
        parent: Model name in scope of which objects should be set up.
    """
    # pylint: disable=unused-argument
    self.setup_workflow_scope(user_id, acr)

    self.admin_control_id = {
        name: id_ for id_, name
        in access_control.role.get_custom_roles_for("Control").items()
    }["Admin"]
    self.api = Api()

    if user_id:
      user = all_models.Person.query.get(user_id)
      self.api.set_user(user)

  def read(self):
    """Read existing Cycle Task Group object."""
    cycle_tg = all_models.CycleTaskGroup.query.first()
    return self.api.get(all_models.CycleTaskGroup, cycle_tg.id)

  def update(self):
    """Update title of existing Cycle Task Group object."""
    cycle_tg = all_models.CycleTaskGroup.query.first()
    return self.api.put(cycle_tg, {"title": factories.random_str()})

  def delete(self):
    """Delete Cycle Task Group object."""
    cycle_tg = all_models.CycleTaskGroup.query.first()
    return self.api.delete(cycle_tg)
