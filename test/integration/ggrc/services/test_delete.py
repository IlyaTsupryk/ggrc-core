# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test suite for DELETE requests."""

from integration.ggrc import TestCase
from integration.ggrc.query_helper import WithQueryApi
from integration.ggrc.models import factories
from integration.ggrc.api_helper import Api

from ggrc import db
from ggrc.models import all_models


class TestDelete(TestCase, WithQueryApi):
  """Test objects deletion."""

  def setUp(self):
    super(TestDelete, self).setUp()
    self.client.get("/login")
    self.api = Api()

  def test_delete(self):
    """Deletion is synchronous and triggers compute_attributes."""
    control = factories.ControlFactory()

    result = self.api.delete(control)

    controls = db.session.query(all_models.Control).all()
    background_tasks = db.session.query(all_models.BackgroundTask).all()

    self.assert200(result)
    self.assertEqual(len(controls), 0)
    self.assertEqual(len(background_tasks), 1)
    self.assertTrue(background_tasks[0].name.startswith("compute_attributes"))

  def test_delete_http400(self):
    """Deletion returns HTTP400 if BadRequest is raised."""
    with factories.single_commit():
      audit = factories.AuditFactory()
      factories.AssessmentFactory(audit=audit)

    result = self.api.delete(audit)

    self.assert400(result)
    self.assertEqual(result.json["message"],
                     "This request will break a mandatory relationship from "
                     "assessments to audits.")

  def test_ca_deleted(self):
    """Test if CADs/CAVs are removed together with parent model."""
    with factories.single_commit():
      asmnt = factories.AssessmentFactory()
      for _ in range(3):
        cad = factories.CustomAttributeDefinitionFactory(
            title=factories.random_str(),
            definition_type=asmnt.type.lower(),
            definition_id=asmnt.id,
            attribute_type="Text",
        )
        factories.CustomAttributeValueFactory(
            custom_attribute=cad,
            attributable=asmnt,
            attribute_value=factories.random_str()
        )

    result = self.api.delete(asmnt)
    self.assert200(result)

    self.assertEqual(all_models.CustomAttributeDefinition.query.count(), 0)
    self.assertEqual(all_models.CustomAttributeValue.query.count(), 0)

  def test_mappings_deleted(self):
    """Test if relationships deleted when one of mapped object deleted."""
    with factories.single_commit():
      audit = factories.AuditFactory()
      asmnt = factories.AssessmentFactory(audit=audit)
      factories.RelationshipFactory(source=audit, destination=asmnt)
      controls = [factories.ControlFactory()]
    snapshots = self._create_snapshots(audit, controls)
    for snapshot in snapshots:
      factories.RelationshipFactory(source=audit, destination=snapshot)
      factories.RelationshipFactory(source=asmnt, destination=snapshot)

    result = self.api.delete(asmnt)
    self.assert200(result)
    rels = db.session.query(
        all_models.Relationship.source_type,
        all_models.Relationship.destination_type
    ).all()
    self.assertEqual(rels, [("Audit", "Snapshot")])
