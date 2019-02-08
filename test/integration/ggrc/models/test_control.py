# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for control model."""
from datetime import datetime
import json

import mock

from ggrc import db
from ggrc.models import all_models
from integration.ggrc import TestCase
from integration.ggrc.models import factories
from integration.ggrc import api_helper


class TestControl(TestCase):
  """Tests for control model."""

  def setUp(self):
    """setUp, nothing else to add."""
    super(TestControl, self).setUp()
    self.api = api_helper.Api()

  def test_simple_categorization(self):
    """Check category append to control."""
    category = factories.ControlCategoryFactory()
    control = factories.ControlFactory()
    control.categories.append(category)
    db.session.commit()
    self.assertIn(category, control.categories)
    # be really really sure
    control = db.session.query(all_models.Control).get(control.id)
    self.assertIn(category, control.categories)

  def test_create_control(self):
    """Test control update with internal user."""
    response = self.api.post(all_models.Control, {"title": "new-title"})
    self.assert403(response)

    control_count = db.session.query(all_models.Control).filter(
        all_models.Control.title == "new-title").count()
    self.assertEqual(0, control_count)

  def test_update_control(self):
    """Test control update with internal user."""
    control = factories.ControlFactory()
    old_title = control.title

    response = self.api.put(control, {"title": "new-title"})
    self.assert403(response)

    control = db.session.query(all_models.Control).get(control.id)
    self.assertEqual(old_title, control.title)

  def test_delete_control(self):
    """Test control update with internal user."""
    control = factories.ControlFactory()

    response = self.api.delete(control)
    self.assert403(response)

    control = db.session.query(all_models.Control).get(control.id)
    self.assertIsNotNone(control.title)


class TestSyncServiceControl(TestCase):
  """Tests for control model using sync service."""

  def setUp(self):
    """setUp, nothing else to add."""
    super(TestSyncServiceControl, self).setUp()
    self.api = api_helper.Api()

    self.app_user_email = "external_app@example.com"
    self.ext_user_email = 'external@example.com'

    custom_headers = {
        'X-GGRC-user': '{"email": "%s"}' % self.app_user_email,
        'X-external-user': '{"email": "%s"}' % self.ext_user_email
    }

    self.api.headers.update(custom_headers)
    self.api.client.get("/login", headers=self.api.headers)

  @mock.patch("ggrc.settings.INTEGRATION_SERVICE_URL", "mock")
  def test_control_create(self):
    """Test control creation using sync service."""
    control_body = self.prepare_control_request_body()

    response = self.api.post(all_models.Control, {
        "control": control_body
    })

    self.assertEqual(201, response.status_code)

    id_ = response.json.get("control").get("id")
    self.assertEqual(control_body["id"], id_)

    control = db.session.query(all_models.Control).get(id_)
    app_user = db.session.query(all_models.Person).filter(
        all_models.Person.email == self.app_user_email).one()
    ext_user = db.session.query(all_models.Person).filter(
        all_models.Person.email == self.ext_user_email).one()

    self.assertEqual(app_user.id, ext_user.modified_by_id)
    self.assertEqual(ext_user.id, control.modified_by_id)

    self.assertEqual(control.title, control_body["title"])
    self.assertEqual(control.slug, control_body["slug"])
    self.assertEqual(control.created_at, control_body["created_at"])
    self.assertEqual(control.updated_at, control_body["updated_at"])

    expected_categories = {
        category["id"] for category in control_body["categories"]
    }
    mapped_categories = {category.id for category in control.categories}
    self.assertEqual(expected_categories, mapped_categories)

    revision = db.session.query(all_models.Revision).filter(
        all_models.Revision.resource_type == "Control",
        all_models.Revision.resource_id == control.id,
        all_models.Revision.action == "created",
        all_models.Revision.created_at == control.updated_at,
        all_models.Revision.updated_at == control.updated_at,
        all_models.Revision.modified_by_id == control.modified_by_id,
    ).one()

    self.assertIsNotNone(revision)

  @staticmethod
  def prepare_control_request_body():
    """Create payload for control creation."""
    created_at = datetime(2018, 1, 1)
    updated_at = datetime(2018, 1, 2)
    category = factories.ControlCategoryFactory()
    assertion = factories.ControlAssertionFactory()

    return {
        "id": 123,
        "title": "new_control",
        "context": None,
        "created_at": created_at,
        "updated_at": updated_at,
        "slug": "CONTROL-01",
        "external_id": factories.SynchronizableExternalId.next(),
        "categories": [
            {
                "id": category.id,
                "type": "ControlCategory"
            }
        ],
        "assertions": [
            {
                "id": assertion.id
            }
        ]
    }

  @mock.patch("ggrc.settings.INTEGRATION_SERVICE_URL", "mock")
  def test_control_update(self):
    """Test control update using sync service."""
    control = factories.ControlFactory()

    response = self.api.get(control, control.id)

    api_link = response.json["control"]["selfLink"]

    control_body = response.json["control"]
    control_body["title"] = "updated_title"
    control_body["created_at"] = "2018-01-04"
    control_body["updated_at"] = "2018-01-05"

    self.api.client.put(api_link,
                        data=json.dumps(response.json),
                        headers=self.api.headers)

    control = db.session.query(all_models.Control).get(control.id)
    self.assertEqual("updated_title", control.title)
    self.assertEqual("2018-01-04", control.created_at.strftime("%Y-%m-%d"))
    self.assertEqual("2018-01-05", control.updated_at.strftime("%Y-%m-%d"))

    revision = db.session.query(all_models.Revision).filter(
        all_models.Revision.resource_type == "Control",
        all_models.Revision.resource_id == control.id,
        all_models.Revision.action == "modified",
        all_models.Revision.created_at == control.updated_at,
        all_models.Revision.updated_at == control.updated_at,
        all_models.Revision.modified_by_id == control.modified_by_id,
    ).one()

    self.assertIsNotNone(revision)

  def test_create_without_assertions(self):
    """Check control creation without assertions fail"""
    response = self.api.post(all_models.Control, {
        "control": {
            "title": "Control title",
            "context": None,
            "recipients": "Admin,Control Operators,Control Owners",
            "send_by_default": 0,
            "external_id": factories.SynchronizableExternalId.next(),
            "assertions": []
        }
    })

    self.assert400(response)
    control = all_models.Control.query.first()
    self.assertIsNone(control)

  def test_create_with_assertions(self):
    """Check control creation with assertions pass"""
    with factories.single_commit():
      assertion = factories.ControlAssertionFactory()

    response = self.api.post(all_models.Control, {
        "control": {
            "title": "Control title",
            "context": None,
            "recipients": "Admin,Control Operators,Control Owners",
            "send_by_default": 0,
            "external_id": factories.SynchronizableExternalId.next(),
            "assertions": [{
                "id": assertion.id
            }]
        }
    })

    self.assertEqual(response.status_code, 201)
    control = all_models.Control.query.first()
    self.assertIsNotNone(control)
    self.assertEqual(assertion.id, control.assertions[0].id)

  def test_has_test_plan(self):
    """Check test plan setup to control."""
    control = factories.ControlFactory(test_plan="This is a test text")
    control = db.session.query(all_models.Control).get(control.id)
    self.assertEqual(control.test_plan, "This is a test text")

  def test_set_end_date(self):
    """End_date can't to be updated."""
    control = factories.ControlFactory()
    self.api.put(control, {"end_date": "2015-10-10"})
    control = db.session.query(all_models.Control).get(control.id)
    self.assertIsNone(control.end_date)

  def test_set_deprecated_status(self):
    """Deprecated status setup end_date."""
    control = factories.ControlFactory()
    self.assertIsNone(control.end_date)
    self.api.put(control, {"status": all_models.Control.DEPRECATED})
    control = db.session.query(all_models.Control).get(control.id)
    self.assertIsNotNone(control.end_date)

  def test_create_commentable(self):
    """Test if commentable fields are set on creation"""
    with factories.single_commit():
      assertion = factories.ControlAssertionFactory()
    recipients = "Admin,Control Operators,Control Owners"
    send_by_default = 0
    response = self.api.post(all_models.Control, {
        "control": {
            "title": "Control title",
            "context": None,
            "recipients": recipients,
            "send_by_default": send_by_default,
            "external_id": factories.SynchronizableExternalId.next(),
            "assertions": [{
                "id": assertion.id
            }]
        },
    })
    self.assertEqual(response.status_code, 201)
    control_id = response.json.get("control").get("id")
    control = db.session.query(all_models.Control).get(control_id)
    self.assertEqual(control.recipients, recipients)
    self.assertEqual(control.send_by_default, send_by_default)

  def test_update_commentable(self):
    """Test update of commentable fields"""
    control = factories.ControlFactory()
    self.assertEqual(control.recipients, "")
    self.assertIs(control.send_by_default, True)

    recipients = "Admin,Control Operators,Control Owners"
    send_by_default = 0
    self.api.put(control, {
        "recipients": recipients,
        "send_by_default": send_by_default,
    })
    control = db.session.query(all_models.Control).get(control.id)
    self.assertEqual(control.recipients, recipients)
    self.assertEqual(control.send_by_default, send_by_default)

  def test_create_without_external_id(self):
    """Check control creation without external_id"""

    request = self.prepare_control_request_body()
    del request['external_id']
    response = self.api.post(all_models.Control, request)

    self.assert400(response)

  # pylint: disable=invalid-name
  def test_create_with_empty_external_id(self):
    """Check control creation with empty external_id"""

    request = self.prepare_control_request_body()
    request['external_id'] = None
    response = self.api.post(all_models.Control, request)

    self.assert400(response)

  def test_create_unique_external_id(self):
    """Check control creation with non-unique external_id"""

    request1 = self.prepare_control_request_body()
    response1 = self.api.post(all_models.Control, {'control': request1})
    prev_external_id = response1.json['control']['external_id']

    request2 = self.prepare_control_request_body()
    request2['external_id'] = prev_external_id
    response2 = self.api.post(all_models.Control, {'control': request2})

    self.assert400(response2)

  def test_update_external_id_to_null(self):
    """Test external_id is not set to None"""
    control = factories.ControlFactory()
    response = self.api.put(control, {"external_id": None})
    self.assert400(response)

    control = db.session.query(all_models.Control).get(control.id)
    self.assertIsNotNone(control.external_id)

  def test_update_external_id(self):
    """Test external_id is updated"""
    control = factories.ControlFactory()
    new_value = factories.SynchronizableExternalId.next()
    self.api.put(control, {"external_id": new_value})

    control = db.session.query(all_models.Control).get(control.id)
    self.assertEquals(control.external_id, new_value)
