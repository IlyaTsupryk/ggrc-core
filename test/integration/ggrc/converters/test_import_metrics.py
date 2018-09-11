# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for task group task specific export."""
from integration.ggrc import TestCase
from ggrc.converters import errors


class TestMetricsImport(TestCase):
  """Test for metrics import."""

  def setUp(self):
    super(TestMetricsImport, self).setUp()
    self.client.get("/login")

  def test_metrics_import(self):
    """Test metrics import"""
    filename = "import_metrics.csv"
    response = self._import_file(filename)
    metric_response = response[2]
    self.assertEqual(metric_response["created"], 3)
    self._check_csv_response(response, {
        "Metric": {
            "row_warnings": {
                errors.MAPPING_SCOPING_ERROR.format(
                    line=14,
                    object_type="Regulation",
                    action="map",
                ),
                errors.MAPPING_SCOPING_ERROR.format(
                    line=15,
                    object_type="Standard",
                    action="map",
                ),
            },
        }
    })
