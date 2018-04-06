# coding: utf-8

# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for last_deprecated_date field in cycle tasks."""

import datetime
import operator
from ggrc.models import all_models
from freezegun import freeze_time
from integration.ggrc import TestCase
from integration.ggrc.api_helper import Api
from integration.ggrc.models import factories


class TestCycleTaskDeprecated(TestCase):
  """Test for correct working field last_deprecated_date."""

  def setUp(self):
    super(TestCycleTaskDeprecated, self).setUp()
    self.api = Api()

  def test_redefine_status(self):
    """Test cycle task create and change status to Deprecated."""
    cycle_task = factories.get_model_factory("CycleTaskGroupObjectTask")()

    with freeze_time("2017-01-25"):
      self.api.modify_object(cycle_task, {
          "status": "Deprecated"
      })

    cycle_task_result = all_models.CycleTaskGroupObjectTask.query.filter(
        all_models.CycleTaskGroupObjectTask.id == cycle_task.id
    ).one()

    self.assertEquals(cycle_task_result.last_deprecated_date,
                      datetime.date(2017, 1, 25))

  def test_keep_date_unchanged(self):
    """Test set status to Deprecated, and then set status to Finished."""
    cycle_task = factories.get_model_factory("CycleTaskGroupObjectTask")()

    with freeze_time("2017-01-25"):
      self.api.modify_object(cycle_task, {
          "status": "Deprecated"
      })

    with freeze_time("2017-01-26"):
      self.api.modify_object(cycle_task, {
          "status": "Finished"
      })

      cycle_task_result = all_models.CycleTaskGroupObjectTask.query.filter(
          all_models.CycleTaskGroupObjectTask.id == cycle_task.id
      ).one()

    self.assertEquals(cycle_task_result.status, "Finished")
    self.assertEquals(cycle_task_result.last_deprecated_date,
                      datetime.date(2017, 1, 25))

  def test_repeat_deprecated_state(self):
    """Test updating of last deprecated date by multiply changing of status."""
    cycle_task = factories.get_model_factory("CycleTaskGroupObjectTask")()

    with freeze_time("2017-01-25"):
      self.api.modify_object(cycle_task, {
          "status": "Deprecated"
      })

    with freeze_time("2017-01-26"):
      self.api.modify_object(cycle_task, {
          "status": "Finished"
      })
    with freeze_time("2017-02-25"):
      self.api.modify_object(cycle_task, {
          "status": "Deprecated"
      })
    with freeze_time("2017-02-26"):
      self.api.modify_object(cycle_task, {
          "status": "Finished"
      })

    cycle_task_result = all_models.CycleTaskGroupObjectTask.query.filter(
        all_models.CycleTaskGroupObjectTask.id == cycle_task.id
    ).one()

    self.assertEquals(cycle_task_result.status, "Finished")
    self.assertEquals(cycle_task_result.last_deprecated_date,
                      datetime.date(2017, 2, 25))

  def test_filter_by_deprecated_date(self):
    """Test filter cycle task by last deprecated date."""
    amount_of_cycle_tasks = 5
    list_of_ids = []
    cycle_task_factory = factories.get_model_factory(
        "CycleTaskGroupObjectTask"
    )
    with factories.single_commit():
      with freeze_time("2017-01-25"):
        for _ in range(amount_of_cycle_tasks):
          list_of_ids.append(
              cycle_task_factory(status="Deprecated").id
          )

    query_request_data = [{
        "object_name": "CycleTaskGroupObjectTask",
        'filters': {
            'expression': {
                'left': 'task Last Deprecated Date',
                'op': {'name': '='},
                'right': "2017-01-25",
            },
        },
        'type': 'ids',
    }]

    result = self.api.send_request(self.api.client.post,
                                   data=query_request_data,
                                   api_link="/query")
    self.assertItemsEqual(list_of_ids,
                          result.json[0]["CycleTaskGroupObjectTask"]["ids"])

  def test_sort_by_deprecated_date(self):
    """Test sorting results of filter cycle tasks by deprecated date."""
    dict_of_dates = {}
    date_list = ["2017-01-25", "2017-01-29", "2017-01-02", "2017-01-26"]
    cycle_task_factory = factories.get_model_factory(
        "CycleTaskGroupObjectTask"
    )
    with factories.single_commit():
      for date in date_list:
        with freeze_time(date):
          dict_of_dates[cycle_task_factory(status="Deprecated").id] = date

    sorted_dict = sorted(dict_of_dates.items(), key=operator.itemgetter(1))
    sorted_list_ids = [item[0] for item in sorted_dict]

    query_request_data = [{
        "object_name": "CycleTaskGroupObjectTask",
        'filters': {
            'expression': {
                'left': 'task Last Deprecated Date',
                'op': {'name': '='},
                'right': "2017-01",
            },
        },
        "order_by": [{"name": "last_deprecated_date"}],
        'type': 'ids',
    }]

    result = self.api.send_request(self.api.client.post,
                                   data=query_request_data,
                                   api_link="/query")
    self.assertItemsEqual(sorted_list_ids,
                          result.json[0]["CycleTaskGroupObjectTask"]["ids"])
