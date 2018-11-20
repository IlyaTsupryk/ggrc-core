# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Unit tests for cloud taskqueue api."""

import unittest

import mock

from ggrc.cloud_api.task_queue import get_app_engine_tasks


class TestTaskQueueAPI(unittest.TestCase):
  """Test class for TaskQueue api."""

  def setUp(self):
    super(TestTaskQueueAPI, self).setUp()

    self.cloud_tasks = {
        "tasks": [
            {
                "scheduleTime": "2018-11-20T10:43:52.011503Z",
                "appEngineHttpRequest": {
                    "httpMethod": "POST",
                    "appEngineRouting": {
                        "host": "example.com"
                    },
                    "relativeUri": "/_background_tasks/reindex",
                    "headers": {
                        "Origin": "https://example.appspot.com",
                        "Content-Length": "13",
                        "Accept-Language": "en-US,en;q=0.9",
                        "X-Usertimezoneoffset": "180",
                        "Accept": "*/*",
                        "Referer": "https://example.com/admin/reindex",
                        "Cookie": "some cookie",
                        "X-Task-Id": "29764",
                        "X-Cloud-Trace-Context": "123",
                        "X-Requested-With": "XMLHttpRequest",
                        "User-Agent": "Mozilla/5.0",
                        "content-type": "application/x-www-form-urlencoded"
                    }
                },
                "view": "BASIC",
                "name": "projects/ggrc-perf/locations/us-central1/queues/"
                        "ggrc/tasks/reindex1542710631_29764",
                "createTime": "2018-11-20T10:43:52Z"
            }
        ]
    }

  def test_taskqueue(self):
    """Test if task name correctly grabbed from cloud task list."""
    with mock.patch(
        "ggrc.cloud_api.task_queue.request_taskqueue_data",
        return_value=self.cloud_tasks
    ):
      tasks = get_app_engine_tasks("ggrc")
    self.assertEqual(tasks, ["reindex1542710631_29764"])
