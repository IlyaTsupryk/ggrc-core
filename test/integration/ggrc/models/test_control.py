# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for control model."""
import unittest

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
    """Check append category append to control."""
    category = factories.ControlCategoryFactory()
    control = factories.ControlFactory()
    control.categories.append(category)
    db.session.commit()
    self.assertIn(category, control.categories)
    # be really really sure
    control = db.session.query(all_models.Control).get(control.id)
    self.assertIn(category, control.categories)

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
    recipients = "Admin,Primary Contacts,Secondary Contacts"
    send_by_default = 0
    response = self.api.post(all_models.Control, {
        "control": {
            "title": "Control title",
            "context": None,
            "recipients": recipients,
            "send_by_default": send_by_default,
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

    recipients = "Admin,Primary Contacts,Secondary Contacts"
    send_by_default = 0
    self.api.put(control, {
        "recipients": recipients,
        "send_by_default": send_by_default,
    })
    control = db.session.query(all_models.Control).get(control.id)
    self.assertEqual(control.recipients, recipients)
    self.assertEqual(control.send_by_default, send_by_default)

  @unittest.skip("Skipped until control not Reviewable")
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
