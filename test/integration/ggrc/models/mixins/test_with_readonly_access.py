# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration test for TestWithReadOnlyAccess mixin"""

import ddt

from ggrc.models import get_model
from integration.ggrc import TestCase
from integration.ggrc.generator import ObjectGenerator
from integration.ggrc import factories


@ddt.ddt
class TestWithReadOnlyAccess(TestCase):
  """Test WithReadOnlyAccess mixin"""

  def setUp(self):
    super(TestWithReadOnlyAccess, self).setUp()
    self.object_generator = ObjectGenerator()
    self.object_generator.api.login_as_normal()

  @ddt.data(
      ('System', True),
      ('System', False),
      ('System', None),
      ('System', "qwert"),
  )
  @ddt.unpack
  def test_readonly_ignored_on_post(self, obj_type, readonly):
    """Test flag readonly ignored on object {0} POST for body readonly={1}"""

    dct = dict()
    if readonly is not None:
      dct['readonly'] = readonly
    resp, obj = self.object_generator.generate_object(
        get_model(obj_type),
        {'readonly': readonly},
    )

    self.assertStatus(resp, 201)

    self.assertFalse(obj.readonly)

  @ddt.data(
      ('System', False, False),
      ('System', True, False),
      ('System', False, True),
      ('System', True, True),
  )
  @ddt.unpack
  def test_readonly_ignored_on_put(self, obj_type, current, new):
    """Test {0} PUT readonly={2} for current readonly={1}"""

    factory = factories.get_model_factory(obj_type)
    with factories.single_commit():
      obj = factory(title='a', readonly=current)

    resp, obj = self.object_generator.modify(
        obj,
        obj_type.lower(),
        {
            'title': 'b',
            'readonly': new
        },
    )

    self.assert200(resp)
    self.assertEqual(obj.readonly, current)
