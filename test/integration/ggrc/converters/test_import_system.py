# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test import of object System"""

# pylint: disable=invalid-name

from collections import OrderedDict

import ddt

from ggrc.converters import errors
from ggrc.models import get_model
from integration.ggrc import TestCase
from integration.ggrc import factories


@ddt.ddt
class TestImportSystem(TestCase):
  """Test for metrics import."""

  def setUp(self):
    super(TestImportSystem, self).setUp()
    self.client.get("/login")

  @ddt.data(
      ("yes", True),
      ("no", False),
      (None, False),
      ("", False),
  )
  @ddt.unpack
  def test_system_readonly_set_on_post(self, readonly, expected):
    """Test flag readonly={0} for new System"""

    data = OrderedDict([
        ("object_type", "System"),
        ("Code*", "CODE"),
        ("Admin", "user@example.com"),
        ("Assignee", "user@example.com"),
        ("Verifier", "user@example.com"),
        ("Title", "b"),
    ])
    if readonly is not None:
      data["Read-only"] = readonly

    response = self.import_data(data)
    self._check_csv_response(response, {})
    obj = get_model("System").query.one()
    self.assertEqual(obj.readonly, expected)

  def test_system_on_post_with_invalid_data(self):
    """Test invalid readonly value for new System"""

    data = OrderedDict([
        ("object_type", "System"),
        ("Code*", "CODE"),
        ("Admin", "user@example.com"),
        ("Assignee", "user@example.com"),
        ("Verifier", "user@example.com"),
        ("Title", "b"),
        ("Read-only", "qwerty")
    ])

    response = self.import_data(data)
    self._check_csv_response(response, {
        "System": {
            "row_warnings": {
                errors.WRONG_VALUE.format(line=3, column_name="Read-only")
            },
        }
    })
    obj = get_model("System").query.one()
    self.assertFalse(obj.readonly)

  @ddt.data(
      (False, "no", False),
      (False, "yes", True),
      (False, None, False),
      (False, "", False),
      (True, "no", False),
      (True, "yes", True),
      (True, None, True),
      (True, "", True),
  )
  @ddt.unpack
  def test_system_readonly_set_on_put(self, current, new, expected):
    """Test System PUT readonly={2} for current readonly={0} and new={1}"""

    with factories.single_commit():
      obj = factories.SystemFactory(title='a', readonly=current)

    data = OrderedDict([
        ("object_type", "System"),
        ("Code*", obj.slug),
        ("Title", "b"),
    ])
    if new is not None:
      data["Read-only"] = new

    response = self.import_data(data)
    self._check_csv_response(response, {})
    obj = get_model("System").query.one()
    self.assertEqual(obj.readonly, expected)

  @ddt.data(True, False)
  def test_system_readonly_invalid_on_put(self, current):
    """Test System readonly={0} on PUt with invalid data"""

    with factories.single_commit():
      obj = factories.SystemFactory(title='a', readonly=current)

    data = OrderedDict([
        ("object_type", "System"),
        ("Code*", obj.slug),
        ("Title", "b"),
        ("Read-only", "qwerty")
    ])

    response = self.import_data(data)
    self._check_csv_response(response, {
        "System": {
            "row_warnings": {
                errors.WRONG_VALUE.format(line=3, column_name="Read-only")
            },
        }
    })
    obj = get_model("System").query.one()
    self.assertEqual(obj.readonly, current)
