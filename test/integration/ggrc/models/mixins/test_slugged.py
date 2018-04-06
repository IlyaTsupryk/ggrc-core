# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration test for Slugged mixin."""

import ddt

from ggrc.models import mixins, all_models

from integration.ggrc import api_helper
from integration.ggrc.query_helper import WithQueryApi
from integration.ggrc import TestCase
from integration.ggrc.models import factories

# Don't include 'Directive', 'SystemOrProcess' and 'Help' as
# we don't work directly with their instances.
SLUGGED_MODELS = [
    m for m in all_models.all_models
    if issubclass(m, mixins.Slugged) and
    m.__name__ not in ("Directive", "SystemOrProcess", "Help")
]


@ddt.ddt
class TestSluggedMixin(WithQueryApi, TestCase):
  """Test cases for Slugged mixin."""

  def setUp(self):
    super(TestSluggedMixin, self).setUp()
    self.client.get("/login")
    self.api = api_helper.Api()

  @ddt.data(*SLUGGED_MODELS)
  def test_not_updatable_slug_via_api(self, model):
    """Test that slug isn't updatable via REST API for {}"""
    obj = factories.get_model_factory(model.__name__)()
    obj_slug = obj.slug

    response = self.api.put(obj, {"slug": factories.random_str()})
    self.assert200(response)
    response_slug = response.json.get(
        model._inflector.table_singular, {}
    ).get("slug")
    self.assertEqual(obj_slug, response_slug)
    db_slug = model.query.first().slug
    self.assertEqual(obj_slug, db_slug)

  def test_not_createble_slug_via_api(self):
    """Test that slug isn't creatable via REST API"""
    # All slug handling is located in mixin, so behavior of slugged models
    # will be the same and testing of one model is enough
    response = self.api.post(all_models.Control, {
        "control": {
            "slug": factories.random_str(),
            "title": "Control title",
            "context": None,
        },
    })
    self.assertEqual(response.status_code, 201)
    response_slug = response.json.get("control").get("slug")
    control = all_models.Control.query.get(
        response.json.get("control").get("id")
    )
    self.assertEqual(control.slug, response_slug)
    self.assertEqual("CONTROL-{}".format(control.id), control.slug)
