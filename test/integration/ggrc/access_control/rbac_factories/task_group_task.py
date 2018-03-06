# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Task Group Task RBAC Factory."""
from datetime import datetime

from ggrc.models import all_models
from integration.ggrc import Api
from integration.ggrc.access_control.rbac_factories import base
from integration.ggrc.models import factories


class TaskGroupTaskRBACFactory(base.BaseRBACFactory):
  """Task Group Task RBAC factory class."""

  def __init__(self, user_id, acr, parent=None):
    """Set up objects for Task Group Task permission tests.

    Args:
        user_id: Id of user under which all operations will be run.
        acr: Instance of ACR that should be assigned for tested user.
        parent: Model name in scope of which objects should be set up.
    """
    self.setup_workflow_scope(user_id, acr)

    self.api = Api()

    if user_id:
      user = all_models.Person.query.get(user_id)
      self.api.set_user(user)

  def create(self):
    """Create new Task Group Task object."""
    person = factories.PersonFactory()
    return self.api.post(all_models.TaskGroupTask, {
        "task_group_task": {
            "title": "New Task Group Task",
            "start_date": datetime.now().strftime("%Y-%m-%d"),
            "end_date": datetime.now().strftime("%Y-%m-%d"),
            "contact": person,
            "context": None,
            "task_group": {
                "id": self.task_group_id,
                "type": "Task Group",
            },
        }
    })

  def read(self):
    """Read existing Task Group Task object."""
    return self.api.get(all_models.TaskGroupTask, self.task_id)

  def update(self):
    """Update title of existing Task Group Task object."""
    task = all_models.TaskGroupTask.query.get(self.task_id)
    return self.api.put(task, {"title": factories.random_str()})

  def delete(self):
    """Delete Task Group Task object."""
    task = all_models.TaskGroupTask.query.get(self.task_id)
    return self.api.delete(task)

  def read_revisions(self):
    """Read revisions for Task Group Task object."""
    responses = []
    for query in ["source_type={}&source_id={}",
                  "destination_type={}&destination_id={}",
                  "resource_type={}&resource_id={}"]:
      responses.append(
          self.api.get_query(
              all_models.TaskGroupTask,
              query.format("task_group_task", self.task_id)
          )
      )
    return responses
