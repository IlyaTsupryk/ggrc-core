# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Functionality for working with app engine task queue."""
import logging

from apiclient import discovery

from googleapiclient.errors import HttpError

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
    tasks = request_taskqueue_data(parent)["tasks"]
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
  try:
    response = request.execute()
  except HttpError as error:
    logger.error("Error occurred during tasks requesting: %s", error)
    response = {}
  return response


def get_task_names_from_dict(tasks):
  """Get task names from dicts."""
  task_names = []
  for task in tasks:
    helpers.assert_type(task, dict)
    task_path = task.get("name")
    task_name = task_path.split("/")[-1]
    task_names.append(task_name)
  return task_names
