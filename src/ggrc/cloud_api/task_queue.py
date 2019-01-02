# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Functionality for working with app engine task queue."""
import logging

from apiclient import discovery

from ggrc import settings
from ggrc.utils import benchmark
from ggrc.utils import helpers

API_SERVICE_NAME = "cloudtasks"
API_VERSION = "v2beta3"

logger = logging.getLogger(__name__)


def get_app_engine_tasks(queue_name):
  """Collect list of tasks that are currently in appengine taskqueue."""
  with benchmark("Collect app engine queued tasks."):
    instance_name = settings.APPENGINE_INSTANCE
    location = settings.APPENGINE_LOCATION
    parent = "projects/{}/locations/{}/queues/{}".format(
        instance_name,
        location,
        queue_name
    )
    tasks = request_taskqueue_data(parent).get("tasks", [])
    helpers.assert_type(tasks, list)
    logger.info("%s tasks were found in queue", len(tasks))
    return get_task_names_from_dict(tasks)


def request_taskqueue_data(parent):
  """Request tasks from taskqueue using cloud api."""
  # Use default service accaunt credentianls
  service = discovery.build(API_SERVICE_NAME, API_VERSION)
  request = service.projects().locations().queues().tasks().list(
      parent=parent
  )
  return request.execute()


def get_task_names_from_dict(tasks):
  """Get task names from dicts."""
  task_names = []
  for task in tasks:
    helpers.assert_type(task, dict)
    task_path = task.get("name")
    task_name = task_path.split("/")[-1]
    task_names.append(task_name)
  return task_names


def delete_task(name):
  """Delete cloud task from queue."""
  service = discovery.build(API_SERVICE_NAME, API_VERSION)
  request = service.projects().locations().queues().tasks().delete(name=name)
  return request.execute()


def stop_bg_tasks(task_names, queue_name):
  """Stop background tasks."""
  for task_name in task_names:
    with benchmark("Stop task '{}'".format(task_name)):
      name = "projects/{}/locations/{}/queues/{}/tasks/{}".format(
          settings.APPENGINE_INSTANCE,
          settings.APPENGINE_LOCATION,
          queue_name,
          task_name
      )
      delete_task(name)
