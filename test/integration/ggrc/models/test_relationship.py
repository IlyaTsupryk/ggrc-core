# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for integration tests for Relationship."""

import json

import ddt

from ggrc.models import all_models
from ggrc.models.scoping_models import SCOPING_MODELS_NAMES
from ggrc.models.exceptions import ValidationError

from integration.ggrc import TestCase
from integration.ggrc import api_helper
from integration.ggrc.models import factories
from integration.ggrc_basic_permissions.models \
    import factories as rbac_factories


@ddt.ddt
class TestRelationship(TestCase):
  """Integration test suite for Relationship."""
  # pylint: disable=invalid-name

  def setUp(self):
    """Create a Person, an Assessment, prepare a Relationship json."""
    super(TestRelationship, self).setUp()
    self.api = api_helper.Api()
    self.client.get("/login")
    self.person = factories.PersonFactory()
    self.assessment = factories.AssessmentFactory()

  HEADERS = {
      "Content-Type": "application/json",
      "X-requested-by": "GGRC",
  }
  REL_URL = "/api/relationships"

  SCOPING_OBJECT_FACTORIES = [
      factories.get_model_factory(name) for name in SCOPING_MODELS_NAMES]

  @staticmethod
  def build_relationship_json(source, destination):
    """Builds relationship create request json."""
    return json.dumps([{
        "relationship": {
            "source": {"id": source.id, "type": source.type},
            "destination": {"id": destination.id, "type": destination.type},
            "context": {"id": None},
        }
    }])

  def test_changing_log_on_doc_change(self):
    """Changing object documents should generate new object revision."""
    url_link = u"www.foo.com"
    with factories.single_commit():
      control = factories.ControlFactory()
      url = factories.DocumentReferenceUrlFactory(link=url_link)

    def get_revisions():
      return all_models.Revision.query.filter(
          all_models.Revision.resource_id == control.id,
          all_models.Revision.resource_type == control.type,
      ).order_by(
          all_models.Revision.id.desc()
      ).all()

    # attach an url to a control
    revisions = get_revisions()
    count = len(revisions)
    response = self.client.post(
        self.REL_URL,
        data=self.build_relationship_json(control, url),
        headers=self.HEADERS)
    self.assert200(response)

    relationship = all_models.Relationship.query.get(
        response.json[0][-1]["relationship"]["id"])

    # check if a revision was created and contains the attached url
    revisions = get_revisions()
    self.assertEqual(count + 1, len(revisions))
    url_list = revisions[0].content.get("documents_reference_url") or []
    self.assertEqual(1, len(url_list))
    self.assertIn("link", url_list[0])
    self.assertEqual(url_link, url_list[0]["link"])

    # now test whether a new revision is created when url is unmapped
    self.assert200(self.api.delete(relationship))

    revisions = get_revisions()
    self.assertEqual(count + 2, len(revisions))
    url_list = revisions[0].content.get("documents_reference_url") or []
    self.assertEqual(url_list, [])

  def test_relationship_disallowed_type(self):
    """Validation fails when source-destination are snapshottable."""
    audit = factories.AuditFactory()
    snapshottable = factories.ControlFactory()

    ctrl_revision = all_models.Revision.query.filter(
        all_models.Revision.resource_id == snapshottable.id,
        all_models.Revision.resource_type == snapshottable.type,
    ).first()
    snapshot = factories.SnapshotFactory(
        parent=audit,
        revision_id=ctrl_revision.id,
        child_type=snapshottable.type,
        child_id=snapshottable.id,
    )
    with self.assertRaises(ValidationError):
      factories.RelationshipFactory(source=snapshottable, destination=snapshot)
    with self.assertRaises(ValidationError):
      factories.RelationshipFactory(source=snapshot, destination=snapshottable)

  @ddt.data(*SCOPING_OBJECT_FACTORIES)
  def test_relationship_scoping_directive(self, factory):
    """Validation fails when source-destination types pair disallowed."""
    scoping_object = factory()
    directive = factories.DirectiveFactory()

    with self.assertRaises(ValidationError):
      factories.RelationshipFactory(source=scoping_object,
                                    destination=directive)
    with self.assertRaises(ValidationError):
      factories.RelationshipFactory(source=directive,
                                    destination=scoping_object)


class TestExternalRelationship(TestCase):
  """Integration test suite for External Relationship."""
  # pylint: disable=invalid-name

  def setUp(self):
    """Init API helper"""
    super(TestExternalRelationship, self).setUp()
    self.api = api_helper.Api()
    with factories.single_commit():
      editor_role = all_models.Role.query.filter(
          all_models.Role.name == "Editor").first()
      self.person_ext = factories.PersonFactory(
          email="external_app@example.com")
      self.person = factories.PersonFactory(
          email="regular_user@example.com")
      rbac_factories.UserRoleFactory(
          role=editor_role, person=self.person)

  HEADERS = {
      "Content-Type": "application/json",
      "X-requested-by": "External App",
      "X-ggrc-user": "{\"email\": \"external_app@example.com\"}",
      "X-appengine-inbound-appid": "test_external_app",
  }
  REL_URL = "/api/relationships"

  @staticmethod
  def build_relationship_json(source, destination, is_external):
    """Builds relationship create request json."""
    return json.dumps([{
        "relationship": {
            "source": {"id": source.id, "type": source.type},
            "destination": {"id": destination.id, "type": destination.type},
            "context": {"id": None},
            "is_external": is_external
        }
    }])

  @staticmethod
  def create_relationship(source, destination, is_external, user):
    """Creates relationship in database with given params."""
    return factories.RelationshipFactory(
        source=source,
        destination=destination,
        is_external=is_external,
        modified_by_id=user.id,
    )

  def test_create_ext_user_ext_relationship(self):
    """Validation external app user creates external relationship."""
    self.api.set_user(self.person_ext)
    with factories.single_commit():
      product = factories.ProductFactory()
      system = factories.SystemFactory()
    response = self.api.client.post(
        self.REL_URL,
        data=self.build_relationship_json(product, system, True),
        headers=self.HEADERS)
    self.assert200(response)

    relationship = all_models.Relationship.query.get(
        response.json[0][-1]["relationship"]["id"])
    self.assertEqual(relationship.source_type, "Product")
    self.assertEqual(relationship.source_id, product.id)
    self.assertEqual(relationship.destination_type, "System")
    self.assertEqual(relationship.destination_id, system.id)
    self.assertTrue(relationship.is_external)
    self.assertEqual(relationship.modified_by_id, self.person_ext.id)
    self.assertIsNone(relationship.parent_id)
    self.assertIsNone(relationship.automapping_id)
    self.assertIsNone(relationship.context_id)

  def test_create_ext_user_reg_relationship(self):
    """Validation external app user creates regular relationship."""
    self.api.set_user(self.person_ext)
    with factories.single_commit():
      product = factories.ProductFactory()
      system = factories.SystemFactory()
    response = self.api.client.post(
        self.REL_URL,
        data=self.build_relationship_json(product, system, False),
        headers=self.HEADERS)
    self.assert400(response)
    self.assertEqual(
        response.json[0],
        [400, "External application can create only external relationships."])

  def test_update_ext_user_ext_relationship(self):
    """Validation external app user updates external relationship."""
    self.api.set_user(self.person_ext)
    with factories.single_commit():
      product = factories.ProductFactory()
      system = factories.SystemFactory()

    self.create_relationship(product, system, True, self.person_ext)

    response = self.api.client.post(
        self.REL_URL,
        data=self.build_relationship_json(product, system, True),
        headers=self.HEADERS)
    self.assert200(response)

    relationship = all_models.Relationship.query.get(
        response.json[0][-1]["relationship"]["id"])
    self.assertEqual(relationship.source_type, "Product")
    self.assertEqual(relationship.source_id, product.id)
    self.assertEqual(relationship.destination_type, "System")
    self.assertEqual(relationship.destination_id, system.id)
    self.assertTrue(relationship.is_external)
    self.assertEqual(relationship.modified_by_id, self.person_ext.id)
    self.assertIsNone(relationship.parent_id)
    self.assertIsNone(relationship.automapping_id)
    self.assertIsNone(relationship.context_id)

  def test_update_ext_user_reg_relationship(self):
    """Validation external app user updates regular relationship."""
    self.api.set_user(self.person_ext)
    with factories.single_commit():
      product = factories.ProductFactory()
      system = factories.SystemFactory()

    self.create_relationship(product, system, False, self.person_ext)

    response = self.api.client.post(
        self.REL_URL,
        data=self.build_relationship_json(product, system, True),
        headers=self.HEADERS)
    self.assert400(response)
    self.assertEqual(
        response.json[0],
        [400, "External application can create only external relationships."])

  def test_delete_ext_user_ext_relationship(self):
    """Validation external app user deletes external relationship."""
    self.api.set_user(self.person_ext)
    with factories.single_commit():
      product = factories.ProductFactory()
      system = factories.SystemFactory()

    rel = self.create_relationship(product, system, True, self.person_ext)

    response = self.api.delete(rel)
    self.assert200(response)
    relationship = all_models.Relationship.query.get(rel.id)
    self.assertIsNone(relationship)

  def test_delete_ext_user_reg_relationship(self):
    """Validation external app user deletes regular relationship."""
    self.api.set_user(self.person_ext)
    with factories.single_commit():
      product = factories.ProductFactory()
      system = factories.SystemFactory()

    rel = self.create_relationship(product, system, False, self.person_ext)
    response = self.api.delete(rel)
    self.assert400(response)
    self.assertEqual(
        response.json,
        {
            'message': 'External application can delete only external '
                       'relationships.',
            'code': 400
        })

  def test_update_reg_user_ext_relationship(self):
    """Validation regular app user updates external relationship."""
    self.api.set_user(self.person)
    with factories.single_commit():
      product = factories.ProductFactory()
      system = factories.SystemFactory()

    self.create_relationship(product, system, True, self.person)

    response = self.api.client.post(
        self.REL_URL,
        data=self.build_relationship_json(product, system, False),
        headers=self.HEADERS)
    self.assert200(response)

  def test_delete_reg_user_ext_relationship(self):
    """Validation regular user deletes external relationship."""
    self.api.set_user(self.person)
    with factories.single_commit():
      product = factories.ProductFactory()
      system = factories.SystemFactory()

    rel = self.create_relationship(product, system, True, self.person)

    response = self.api.delete(rel)
    self.assert200(response)
    relationship = all_models.Relationship.query.get(rel.id)
    self.assertIsNone(relationship)
