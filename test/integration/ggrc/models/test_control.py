# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for control model."""
from datetime import datetime
import json

import ddt
import mock

from sqlalchemy.ext import associationproxy
from sqlalchemy.orm import collections

from ggrc import db, settings
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


@ddt.ddt
class TestSyncServiceControl(TestCase):
  """Tests for control model using sync service."""

  def setUp(self):
    """setUp, nothing else to add."""
    super(TestSyncServiceControl, self).setUp()
    self.api = api_helper.Api()

    self.app_user_email = "external_app@example.com"
    self.ext_user_email = 'external@example.com'

    settings.EXTERNAL_APP_USER = self.app_user_email

    custom_headers = {
        'X-GGRC-user': '{"email": "%s"}' % self.app_user_email,
        'X-external-user': '{"email": "%s"}' % self.ext_user_email
    }

    self.api.headers.update(custom_headers)
    self.api.client.get("/login", headers=self.api.headers)

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
        "kind": "test kind",
        "means": "test means",
        "verify_frequency": "test frequency",
        "categories": [
            {
                "id": category.id,
                "type": "ControlCategory"
            }
        ],
        "assertions": [
            {
                "id": assertion.id,
                "type": "ControlAssertion",
            }
        ]
    }

  def normilize_field(self, field):
    """Convert field from date/db.Model/query to string value."""
    # pylint: disable=protected-access
    normilized_field = field
    if isinstance(normilized_field, datetime):
      normilized_field = str(normilized_field.date())
    elif isinstance(normilized_field, db.Model):
      normilized_field = {
          "type": normilized_field.type,
          "id": normilized_field.id
      }
    elif isinstance(normilized_field, dict):
      normilized_field.pop("context_id", None)
      normilized_field.pop("href", None)
    elif isinstance(normilized_field, list):
      normilized_field = [self.normilize_field(i) for i in normilized_field]
    elif isinstance(
        normilized_field,
        (associationproxy._AssociationList, collections.InstrumentedList)
    ):
      normilized_field = [
          {"type": i.type, "id": i.id} for i in normilized_field
      ]
    return normilized_field

  def assert_response_fields(self, response_json, expected_body):
    """Check if data in response is the same with expected."""
    for field, value in expected_body.items():
      response_field = self.normilize_field(response_json[field])
      expected_value = self.normilize_field(value)

      self.assertEqual(
          response_field,
          expected_value,
          "Fields '{}' are not equal".format(field)
      )

  def assert_object_fields(self, object_, expected_body):
    """Check if object field values are the same with expected."""
    for field, value in expected_body.items():
      obj_value = self.normilize_field(getattr(object_, field))
      expected_value = self.normilize_field(value)
      self.assertEqual(
          obj_value,
          expected_value,
          "Fields '{}' are not equal".format(field)
      )

  def test_control_read(self):
    """Test correctness of control field values on read operation."""
    control_body = {
        "title": "test control",
        "slug": "CONTROL-01",
        "kind": "test kind",
        "means": "test means",
        "verify_frequency": "test frequency",
    }
    control = factories.ControlFactory(**control_body)

    response = self.api.get(all_models.Control, control.id)
    self.assert200(response)

    self.assert_response_fields(response.json.get("control"), control_body)
    control = all_models.Control.query.get(control.id)
    self.assert_object_fields(control, control_body)

  @mock.patch("ggrc.settings.INTEGRATION_SERVICE_URL", "mock")
  def test_control_create(self):
    """Test control creation using sync service."""
    control_body = self.prepare_control_request_body()

    response = self.api.post(all_models.Control, {
        "control": control_body
    })

    self.assertEqual(response.status_code, 201)

    id_ = response.json.get("control").get("id")
    self.assertEqual(control_body["id"], id_)

    control = db.session.query(all_models.Control).get(id_)
    app_user = db.session.query(all_models.Person).filter(
        all_models.Person.email == self.app_user_email).one()
    ext_user = db.session.query(all_models.Person).filter(
        all_models.Person.email == self.ext_user_email).one()

    self.assertEqual(ext_user.modified_by_id, app_user.id)
    self.assertEqual(control.modified_by_id, ext_user.id)

    self.assert_response_fields(response.json.get("control"), control_body)
    self.assert_object_fields(control, control_body)

    revision = db.session.query(all_models.Revision).filter(
        all_models.Revision.resource_type == "Control",
        all_models.Revision.resource_id == control.id,
        all_models.Revision.action == "created",
        all_models.Revision.created_at == control.updated_at,
        all_models.Revision.updated_at == control.updated_at,
        all_models.Revision.modified_by_id == control.modified_by_id,
    ).one()
    self.assertIsNotNone(revision)

  @mock.patch("ggrc.settings.INTEGRATION_SERVICE_URL", "mock")
  def test_control_update(self):
    """Test control update using sync service."""
    external_user = factories.PersonFactory(email=self.ext_user_email)
    control = factories.ControlFactory(modified_by=external_user)
    response = self.api.get(control, control.id)

    api_link = response.json["control"].pop("selfLink")
    response.json["control"].pop("viewLink")

    control_body = response.json["control"]
    control_body.update({
        "title": "updated_title",
        "created_at": "2018-01-04",
        "updated_at": "2018-01-05",
        "kind": "test kind",
        "means": "test means",
        "verify_frequency": "test frequency",
    })
    self.api.client.put(api_link,
                        data=json.dumps(response.json),
                        headers=self.api.headers)

    self.assert_response_fields(response.json["control"], control_body)
    control = all_models.Control.query.get(control.id)
    self.assert_object_fields(control, control_body)

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

  @ddt.data(
      ("kind", ["1", "2", "3"], "2"),
      ("means", ["1", "1", "1"], "1"),
      ("verify_frequency", ["3", "2", "3"], "3")
  )
  @ddt.unpack
  def test_control_query(self, field, possible_values, search_value):
    """Test querying '{0}' field for control."""
    with factories.single_commit():
      for val in possible_values:
        factories.ControlFactory(**{field: val})

    request_data = [{
        'fields': [],
        'filters': {
            'expression': {
                'left': field,
                'op': {'name': '='},
                'right': search_value,
            },
        },
        'object_name': 'Control',
        'type': 'values',
    }]
    response = self.api.send_request(
        self.api.client.post,
        data=request_data,
        api_link="/query"
    )
    self.assert200(response)
    response_data = response.json[0]["Control"]

    expected_controls = all_models.Control.query.filter_by(
        **{field: search_value}
    )
    self.assertEqual(expected_controls.count(), response_data.get("count"))

    expected_values = [getattr(i, field) for i in expected_controls]
    actual_values = [val.get(field) for val in response_data.get("values")]
    self.assertEqual(expected_values, actual_values)

  @ddt.data("kind", "means", "verify_frequency")
  def test_new_revision(self, field):
    """Test if content of new revision is correct for Control '{0}' field."""
    field_value = factories.random_str()
    control = factories.ControlFactory(**{field: field_value})

    response = self.api.client.get(
        "/api/revisions"
        "?resource_type={}&resource_id={}".format(control.type, control.id)
    )
    self.assert200(response)
    revisions = response.json["revisions_collection"]["revisions"]
    self.assertEqual(len(revisions), 1)
    self.assertEqual(revisions[0].get("content", {}).get(field), field_value)

  @ddt.data("kind", "means", "verify_frequency")
  def test_old_revision(self, field):
    """Test if old revision content is correct for Control '{0}' field."""
    field_value = factories.random_str()
    control = factories.ControlFactory(**{field: field_value})
    control_revision = all_models.Revision.query.filter_by(
        resource_type=control.type,
        resource_id=control.id
    ).one()
    control_revision.content[field] = {
        "id": "123",
        "title": "some title",
        "type": "Option",
    }
    db.session.commit()

    response = self.api.client.get(
        "/api/revisions"
        "?resource_type={}&resource_id={}".format(control.type, control.id)
    )
    self.assert200(response)
    revisions = response.json["revisions_collection"]["revisions"]
    self.assertEqual(len(revisions), 1)
    self.assertEqual(revisions[0].get("content", {}).get(field), field_value)
