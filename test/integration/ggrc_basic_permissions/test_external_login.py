# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for usage of X-external-user header."""


import json
import ddt
import mock

from ggrc.models import all_models

from integration.ggrc import TestCase
from integration.ggrc.models import factories


@ddt.ddt
class TestExternalPermissions(TestCase):
  """Tests for external permissions and modified by."""

  def setUp(self):
    """Set up request mock and mock dependencies."""
    self.allowed_appid = "ggrcq-id"
    self.person = factories.PersonFactory()

    self.settings_patcher = mock.patch("ggrc.login.appengine.settings")
    self.settings_mock = self.settings_patcher.start()
    self.settings_mock.ALLOWED_QUERYAPI_APP_IDS = [self.allowed_appid]

  MODELS = [
      all_models.AccessGroup,
      all_models.Contract,
      all_models.Control,
      all_models.DataAsset,
      all_models.Facility,
      all_models.Issue,
      all_models.Market,
      all_models.Metric,
      all_models.Objective,
      all_models.OrgGroup,
      all_models.Policy,
      all_models.Process,
      all_models.Product,
      all_models.ProductGroup,
      all_models.Program,
      all_models.Project,
      all_models.Regulation,
      all_models.Requirement,
      all_models.Risk,
      all_models.Standard,
      all_models.System,
      all_models.TechnologyEnvironment,
      all_models.Threat,
      all_models.Vendor,
      all_models.Workflow
  ]

  @ddt.data(*MODELS)
  def test_post_modifier(self, model):
    """Test modifier of models when working as external user."""
    headers = {
        "Content-Type": "application/json",
        "X-requested-by": "GGRC",
        "X-appengine-inbound-appid": self.allowed_appid,
        "X-ggrc-user": json.dumps({"email": "external_app@example.com"}),
        "X-external-user": json.dumps({"email": "new_ext_user@example.com"})
    }
    self.client.get("/login", headers=headers)

    model_plural = model._inflector.table_plural
    model_singular = model._inflector.table_singular
    response = self.client.post(
        "api/{}".format(model_plural),
        data=json.dumps({
            model_singular: {
                "title": "{}1".format(model_singular),
                "context": 0
            }
        }),
        headers=headers)
    self.assertEqual(response.status_code, 201)

    # check object modifier
    person = all_models.Person.query.filter_by(
        email="new_ext_user@example.com"
    ).first()
    person_id = person.id
    self.assertEqual(response.json[model_singular]['modified_by']['id'],
                     person_id)
    self.assertEqual(person.system_wide_role, "Creator")

    # check revision modifier
    revision = all_models.Revision.query.filter(
        all_models.Revision.resource_type == model.__name__).order_by(
        all_models.Revision.id.desc()).first()
    self.assertEqual(revision.modified_by_id, person_id)

    # check event modifier
    event = all_models.Event.query.filter(
        all_models.Event.resource_type == model.__name__).order_by(
        all_models.Event.id.desc()).first()
    self.assertEqual(event.modified_by_id, person_id)
