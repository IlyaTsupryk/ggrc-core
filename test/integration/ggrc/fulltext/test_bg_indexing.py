# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for checking background indexing logic"""
import json
from datetime import datetime

import mock

from ggrc import settings
from ggrc.models import all_models
from integration.ggrc import TestCase, api_helper
from integration.ggrc.models import factories
from integration.ggrc import generator


class TestTaskqueueIndexing(TestCase):
  """Test case for checking background indexing logic"""

  def setUp(self):
    """Set up for test cases."""
    from ggrc.fulltext import listeners
    from ggrc.models.background_task import reindex_on_commit

    super(TestTaskqueueIndexing, self).setUp()
    listeners.reindex_on_commit = reindex_on_commit
    self.api = api_helper.Api()
    self.init_taskqueue()
    self.object_generator = generator.ObjectGenerator()
    self._bg_tasks = {}

  def run_bg_tasks(self):
    """Run background tasks"""
    for task in self.taskqueue_stub.get_filtered_tasks():
      if task.name not in self._bg_tasks:
        task.headers.update({"X-Appengine-Taskname": task.name})
        response = self.api.client.open(task.url,
                                        method=task.method,
                                        data=task.payload,
                                        headers=task.headers)
        self._bg_tasks[task.name] = response

  def assert_bg_tasks_success(self):
    """Check response status of executed background tasks"""
    for task in all_models.BackgroundTask.query.all():
      self.assertEqual(task.status, "Success")

  @mock.patch.object(settings, "APP_ENGINE", True, create=True)
  def test_general_bg_indexing(self):
    """Test indexing in background task"""
    with self.object_generator.api.as_external():
      response, _ = self.object_generator.generate_object(
          all_models.Control,
          data={
              "control": {
                  "title": "testCONTROL_title",
                  "context": None,
              },
          }
      )
    self.assertStatus(response, 201)
    control_id = response.json["control"]["id"]
    modified_by = response.json["control"]["modified_by"]["id"]
    person = all_models.Person.query.get(modified_by)
    person_email = person.email
    person_name = person.name

    self.run_bg_tasks()
    self.assert_bg_tasks_success()

    conditions = (
        ("title", "~", "stCON", 1),
        ("title", "=", "TEST", 0),
        ("title", "=", "testCONTROL_title", 1),
        ("title", "~", "TST", 0),
        ("Last Updated Date", "~", datetime.utcnow().strftime("%m/%d/%Y"), 1),
        ("Last Updated By", "=", person_email, 1),
        ("Last Updated By", "=", person_name, 1),
    )
    for _left, _op, _right, _count in conditions:
      query_request_data = [{
          "object_name": "Control",
          'filters': {
              'expression': {
                  'left': _left,
                  'op': {'name': _op},
                  'right': _right,
              },
          },
          'type': 'ids',
      }]

      response = self.api.send_request(self.api.client.post,
                                       data=query_request_data,
                                       api_link="/query")
      self.assertEqual(len(response.json), 1)
      self.assertEqual(response.json[0]["Control"]["count"], _count)
      if _count:
        self.assertEqual(control_id, response.json[0]["Control"]["ids"][0])

  @mock.patch.object(settings, "APP_ENGINE", True, create=True)
  def test_indexing_header(self):
    """Test response headers contain indexing task.id"""
    with self.object_generator.api.as_external():
      response, _ = self.object_generator.generate_object(
          all_models.Control,
          data={
              "control": {
                  "title": "CONTROL_title",
                  "context": None,
              },
          }
      )

    self.assertStatus(response, 201)
    indexing_task_id = response.headers.get("X-GGRC-Indexing-Task-Id")

    query_request_data = [{
        "object_name": "Control",
        'filters': {
            'expression': {
                'left': "title",
                'op': {'name': "="},
                'right': "CONTROL_title",
            },
        },
        'type': 'ids',
    }]
    response = self.api.send_request(self.api.client.post,
                                     data=query_request_data,
                                     api_link="/query")
    self.assertEqual(response.json[0]["Control"]["count"], 0)

    response = self.api.get(all_models.BackgroundTask, indexing_task_id)
    self.assertStatus(response, 200)
    self.assertEqual(response.json["background_task"]["status"], "Pending")

    self.run_bg_tasks()
    self.assert_bg_tasks_success()

    response = self.api.get(all_models.BackgroundTask, indexing_task_id)
    self.assertStatus(response, 200)
    self.assertEqual(response.json["background_task"]["status"], "Success")

    response = self.api.send_request(self.api.client.post,
                                     data=query_request_data,
                                     api_link="/query")
    self.assertEqual(response.json[0]["Control"]["count"], 1)

  @mock.patch.object(settings, "APP_ENGINE", True, create=True)
  def test_autogenerate_asmt(self):
    """Test assessment autogeneration in background
    using header X-GGRC-BackgroundTask and indexing of assessment(changing
    audit archived status)
    """
    with factories.single_commit():
      audit = factories.AuditFactory()
      control = factories.ControlFactory()
      snapshot = self._create_snapshots(audit, [control])[0]
    assessment_dict = {
        "assessment": {
            "audit": {
                "id": audit.id,
                "type": "Audit"
            },
            "object": {
                "id": snapshot.id,
                "type": "Snapshot"
            },
            "context": {
                "id": audit.context.id,
                "type": "Context"
            },
            "title": "Temp title"
        }
    }
    headers = {
        "X-GGRC-BackgroundTask": "True",
        "X-Requested-By": "GGRC"
    }
    response = self.api.client.post("/api/assessments",
                                    data=json.dumps(assessment_dict),
                                    headers=headers,
                                    content_type="application/json")
    self.assertStatus(response, 200)
    self.assertEqual(response.json["background_task"]["status"], "Pending")
    self.assertEqual(len(all_models.Assessment.query.all()), 0)

    self.run_bg_tasks()  # Autogenerate
    self.run_bg_tasks()  # Indexing
    self.assert_bg_tasks_success()

    self.assertEqual(len(all_models.Assessment.query.all()), 1)

    self.api.put(audit, {"archived": True})
    query_request_data = [{
        "object_name": "Assessment",
        'filters': {
            'expression': {
                'left': "archived",
                'op': {'name': "="},
                'right': "true",
            },
        },
        'type': 'ids',
    }]
    response = self.api.send_request(self.api.client.post,
                                     data=query_request_data,
                                     api_link="/query")
    self.assertEqual(response.json[0]["Assessment"]["count"], 0)
    self.run_bg_tasks()
    response = self.api.send_request(self.api.client.post,
                                     data=query_request_data,
                                     api_link="/query")
    self.assertEqual(response.json[0]["Assessment"]["count"], 1)

  def test_audit_snapshots_reindex(self):
    """Test if Snapshots created in Audit reindexed."""
    with factories.single_commit():
      control = factories.ControlFactory()
      control_title = control.title
      program = factories.ProgramFactory()
      factories.RelationshipFactory(source=control, destination=program)

    response = self.api.post(all_models.Audit, [{
        "audit": {
            "title": "Some Audit",
            "program": {"id": program.id},
            "status": "Planned",
            "context": None
        }
    }])
    self.assertStatus(response, 200)

    query_request_data = [{
        "object_name": "Snapshot",
        "filters": {
            "expression": {
                "left": "title",
                "op": {"name": "="},
                "right": control_title,
            },
        },
        "type": "ids",
    }]
    response = self.api.send_request(self.api.client.post,
                                     data=query_request_data,
                                     api_link="/query")
    self.assertEqual(response.json[0]["Snapshot"]["count"], 1)
