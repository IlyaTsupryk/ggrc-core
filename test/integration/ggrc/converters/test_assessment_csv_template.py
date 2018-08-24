# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests attributes order in csv file for assessments."""

from integration.ggrc import TestCase
from integration.ggrc.models import factories


class TestAssessmentCSVTemplate(TestCase):
  """Tests order of the attributes in assessment csv.

  Test suite for checking attributes order both in the
  the exported assessment csv (will be the same for
  assessment csv template).
  """

  def setUp(self):
    """Set up for test cases."""
    super(TestAssessmentCSVTemplate, self).setUp()
    self.client.get("/login")
    self.headers = {
        'Content-Type': 'application/json',
        "X-Requested-By": "GGRC",
        "X-export-view": "blocks",
    }

  def test_exported_csv(self):
    """Tests attributes order in exported assessment csv."""
    factories.CustomAttributeDefinitionFactory(
        definition_type="assessment", title="GCA 1", )
    data = [{
        "object_name": "Assessment",
        "filters": {
            "expression": {},
        },
        "fields": "all",
    }]

    response = self.export_csv(data)
    self.assertEqual(response.status_code, 200)
    self.assertIn("Verifiers,Comments,Last Comment,GCA 1", response.data)

  def test_local_cads_abset(self):
    """Test if local CADs absent in Assessment csv template."""
    with factories.single_commit():
      asmnt = factories.AssessmentFactory()
      factories.CustomAttributeDefinitionFactory(
          definition_type="assessment",
          definition_id=asmnt.id,
          title="LCA 1",
      )
      asmnt_template = factories.AssessmentTemplateFactory()
      factories.CustomAttributeDefinitionFactory(
          definition_type="assessment_template",
          definition_id=asmnt_template.id,
          title="LCA 2",
      )
      factories.CustomAttributeDefinitionFactory(
          definition_type="assessment", title="GCA 1",
      )

    data = [{
        "object_name": "Assessment",
        "fields": "all",
    }]
    response = self.export_csv(data)

    self.assertEqual(response.status_code, 200)
    self.assertNotIn("LCA 1", response.data)
    self.assertNotIn("LCA 2", response.data)
