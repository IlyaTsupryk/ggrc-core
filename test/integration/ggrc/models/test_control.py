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

  def test_review_get(self):
    """Test that review data is present in control get response"""
    with factories.single_commit():
      control = factories.ControlFactory()
      review = factories.ReviewFactory(reviewable=control)
      review_id = review.id

    resp = self.api.get(all_models.Control, control.id)
    self.assert200(resp)
    resp_control = resp.json["control"]
    self.assertIn("review", resp_control)
    self.assertEquals(review_id, resp_control["review"]["id"])


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
