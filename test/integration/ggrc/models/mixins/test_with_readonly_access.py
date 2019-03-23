# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Integration test for TestWithReadOnlyAccess mixin"""

# pylint: disable=invalid-name

from collections import OrderedDict
import json

import ddt

from ggrc import views
from ggrc.converters import errors
from ggrc.models import get_model, all_models, mixins
from integration.ggrc import TestCase
from integration.ggrc import api_helper
from integration.ggrc.generator import ObjectGenerator
from integration.ggrc import factories
from integration.ggrc_basic_permissions.models \
    import factories as rbac_factories


@ddt.ddt
class TestWithReadOnlyAccessAPI(TestCase):
  """Test WithReadOnlyAccess mixin"""

  def setUp(self):
    super(TestWithReadOnlyAccessAPI, self).setUp()
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
      ('System', False, False, 200),
      ('System', False, True, 200),
      ('System', False, None, 200),
      ('System', True, False, 405),
      ('System', True, True, 405),
      ('System', True, None, 405),
  )
  @ddt.unpack
  def test_put(self, obj_type, current, new, exp_code):
    """Test {0} PUT readonly={2} for current readonly={1}"""

    factory = factories.get_model_factory(obj_type)
    with factories.single_commit():
      obj = factory(title='a', readonly=current)
      obj_id = obj.id

    data = {'title': 'b'}
    if new is not None:
      data['readonly'] = new

    resp = self.object_generator.api.put(obj, data)

    self.assertStatus(resp, exp_code)
    obj = get_model(obj_type).query.get(obj_id)
    self.assertEqual(obj.readonly, current)

  @ddt.data('System')
  def test_403_if_put_readonly_without_perms(self, obj_type):
    """Test {0} with readonly=True PUT returns 401 instead of 405

    This test ensures that user without permission for the object
    cannot obtain value for flag readonly
    """
    role_obj = all_models.Role.query.filter(
        all_models.Role.name == "Creator").one()

    factory = factories.get_model_factory(obj_type)

    with factories.single_commit():
      # create Global Creator
      person = factories.PersonFactory()
      person_id = person.id
      rbac_factories.UserRoleFactory(role=role_obj, person=person)

      # Create object
      obj = factory(title='a', readonly=True)
      obj_id = obj.id

    self.object_generator.api.set_user(all_models.Person.query.get(person_id))
    obj = get_model(obj_type).query.get(obj_id)
    resp = self.object_generator.api.put(obj, {'title': 'b'})

    self.assert403(resp)

  @ddt.data(
      ('System', False, 200, True),
      ('System', True, 405, False),
  )
  @ddt.unpack
  def test_delete(self, obj_type, readonly, exp_code, exp_deleted):
    """Test {0} DELETE if readonly={1}"""

    factory = factories.get_model_factory(obj_type)
    with factories.single_commit():
      obj = factory(title='a', readonly=readonly)
      obj_id = obj.id

    resp = self.object_generator.api.delete(obj)

    self.assertStatus(resp, exp_code)
    obj = get_model(obj_type).query.get(obj_id)
    if exp_deleted:
      self.assertIsNone(obj)
    else:
      self.assertIsNotNone(obj)

  @ddt.data('System')
  def test_403_if_delete_readonly_without_perms(self, obj_type):
    """Test {0} with readonly=True DELETE returns 401

    This test ensures that user without permission for the object
    cannot obtain value for flag readonly
    """

    role_obj = all_models.Role.query.filter(
        all_models.Role.name == "Creator").one()

    factory = factories.get_model_factory(obj_type)

    with factories.single_commit():
      # create Global Creator
      person = factories.PersonFactory()
      person_id = person.id
      rbac_factories.UserRoleFactory(role=role_obj, person=person)

      # Create object
      obj = factory(title='a', readonly=True)
      obj_id = obj.id

    self.object_generator.api.set_user(all_models.Person.query.get(person_id))
    obj = get_model(obj_type).query.get(obj_id)
    resp = self.object_generator.api.delete(obj)

    self.assert403(resp)
    obj = get_model(obj_type).query.get(obj_id)
    self.assertIsNotNone(obj)


@ddt.ddt
class TestWithReadOnlyAccessImport(TestCase):
  """Test for metrics import."""

  def setUp(self):
    super(TestWithReadOnlyAccessImport, self).setUp()
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
      ("no", False),
      ("yes", True),
      (None, False),
      ("", False),
  )
  @ddt.unpack
  def test_system_update_to_readonly(self, new, expected):
    """Test System readonly={1} if new={0}"""

    with factories.single_commit():
      obj = factories.SystemFactory(title='a', readonly=False)

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

  @ddt.data("no", "yes", None, "", True)
  def test_system_not_updated(self, new):
    """Test readonly System not updated if new={0}"""

    with factories.single_commit():
      obj = factories.SystemFactory(title='a', readonly=True)

    data = OrderedDict([
        ("object_type", "System"),
        ("Code*", obj.slug),
        ("Title", "b"),
    ])
    if new is not None:
      data["Read-only"] = new

    response = self.import_data(data)
    self._check_csv_response(response, {
        "System": {
            "row_errors": {
                errors.READONLY_ACCESS_ERROR.format(line=3),
            },
        }
    })
    obj = get_model("System").query.one()
    self.assertEqual(obj.readonly, True)
    self.assertEqual(obj.title, 'a')

  @ddt.data("no", "yes", None, "", True)
  def test_system_not_updated_without_perms(self, new):
    """Test readonly System not updated if new={0} and user has no perms

    This test ensures that user without permission for the object
    cannot obtain value for flag readonly
    """

    role_obj = all_models.Role.query.filter(
        all_models.Role.name == "Creator").one()

    with factories.single_commit():
      person = factories.PersonFactory()
      person_id = person.id
      rbac_factories.UserRoleFactory(role=role_obj, person=person)

      obj = factories.SystemFactory(title='a', readonly=True)

    data = OrderedDict([
        ("object_type", "System"),
        ("Code*", obj.slug),
        ("Title", "b"),
    ])
    if new is not None:
      data["Read-only"] = new

    response = self.import_data(
        data,
        person=all_models.Person.query.get(person_id)
    )
    self._check_csv_response(response, {
        "System": {
            "row_errors": {
                errors.PERMISSION_ERROR.format(line=3),
            },
        }
    })
    obj = get_model("System").query.one()
    self.assertEqual(obj.readonly, True)
    self.assertEqual(obj.title, 'a')

  def test_system_readonly_invalid_on_update(self):
    """Test System readonly=False on update with invalid data"""

    with factories.single_commit():
      obj = factories.SystemFactory(title='a', readonly=False)

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
    self.assertFalse(obj.readonly)

  def test_readonly_system_not_deleted(self):
    """Test System with readonly=True can be deleted"""

    with factories.single_commit():
      obj = factories.SystemFactory(title='a', readonly=True)
      obj_id = obj.id

    data = OrderedDict([
        ("object_type", "System"),
        ("Code*", obj.slug),
        ("Delete", "yes"),
    ])

    response = self.import_data(data)
    self._check_csv_response(response, {
        "System": {
            "row_errors": {
                "Line 3: Delete column is temporary disabled, please "
                "use web interface to delete current object.",
                errors.READONLY_ACCESS_ERROR.format(line=3),
            },
        }
    })
    obj = get_model("System").query.get(obj_id)
    self.assertIsNotNone(obj)

  def test_readonly_system_not_deleted_without_user_perms(self):
    """Test System with readonly=True can be deleted

    This test ensures that user without permission for the object
    cannot obtain value for flag readonly
    """

    role_obj = all_models.Role.query.filter(
        all_models.Role.name == "Creator").one()

    with factories.single_commit():
      person = factories.PersonFactory()
      person_id = person.id
      rbac_factories.UserRoleFactory(role=role_obj, person=person)

      obj = factories.SystemFactory(title='a', readonly=True)
      obj_id = obj.id

    data = OrderedDict([
        ("object_type", "System"),
        ("Code*", obj.slug),
        ("Delete", "yes"),
    ])

    response = self.import_data(
        data,
        person=all_models.Person.query.get(person_id)
    )
    self._check_csv_response(response, {
        "System": {
            "row_errors": {
                "Line 3: Delete column is temporary disabled, please "
                "use web interface to delete current object.",
                errors.PERMISSION_ERROR.format(line=3),
            },
        }
    })
    obj = get_model("System").query.get(obj_id)
    self.assertIsNotNone(obj)


@ddt.ddt
class TestWithReadOnlyAccessFolder(TestCase):
  """Test for "unmap_objects" view."""

  NOT_PRESENT = object()
  PATH_ADD_FOLDER = '/api/add_folder'
  PATH_REMOVE_FOLDER = '/api/remove_folder'

  FOLDERABLE_MODEL_NAMES = list(m.__name__ for m in all_models.all_models
                                if issubclass(m, mixins.Folderable) and
                                m not in (all_models.Directive,
                                          all_models.SystemOrProcess))

  def setUp(self):
    """setUp"""
    super(TestWithReadOnlyAccessFolder, self).setUp()
    self.api = api_helper.Api()

  def _get_request_data(self, obj_type=NOT_PRESENT, obj_id=NOT_PRESENT,
                        folder=NOT_PRESENT):
    """Prepare request dict"""
    dct = dict()

    if obj_type is not self.NOT_PRESENT:
      dct['object_type'] = obj_type

    if obj_id is not self.NOT_PRESENT:
      dct['object_id'] = obj_id

    if folder is not self.NOT_PRESENT:
      dct['folder'] = folder

    return json.dumps(dct)

  @ddt.data(
      ('System', 'Creator', 403),
      ('System', 'Reader', 403),
      ('System', 'Editor', 405),
      ('System', 'Administrator', 405),
  )
  @ddt.unpack
  def test_readonly_add_folder_with_global_role(self, obj_type, role_name,
                                                expected_status):
    """Test add_folder read-only {0} by user with global role {1}"""

    role_obj = all_models.Role.query.filter(
        all_models.Role.name == role_name).one()

    factory = factories.get_model_factory(obj_type)
    with factories.single_commit():
      obj_id = factory(folder="a", readonly=True).id
      person = factories.PersonFactory()
      rbac_factories.UserRoleFactory(role=role_obj, person=person)
      person_id = person.id

    self.api.set_user(all_models.Person.query.get(person_id))

    response = self.api.client.post(
        self.PATH_ADD_FOLDER, content_type="application/json",
        data=self._get_request_data(obj_type, obj_id, folder="b"))

    self.assertStatus(response, expected_status)
    obj = get_model(obj_type).query.get(obj_id)
    self.assertEqual(obj.folder, "a")

  @ddt.data(
      ('System', 'Creator', 403),
      ('System', 'Reader', 403),
      ('System', 'Editor', 405),
      ('System', 'Administrator', 405),
  )
  @ddt.unpack
  def test_readonly_remove_folder_with_global_role(self, obj_type, role_name,
                                                   expected_status):
    """Test remove_folder read-only {0} by user with global role {1}"""

    role_obj = all_models.Role.query.filter(
        all_models.Role.name == role_name).one()

    factory = factories.get_model_factory(obj_type)
    with factories.single_commit():
      obj_id = factory(folder="a", readonly=True).id
      person = factories.PersonFactory()
      rbac_factories.UserRoleFactory(role=role_obj, person=person)
      person_id = person.id

    self.api.set_user(all_models.Person.query.get(person_id))

    response = self.api.client.post(
        self.PATH_REMOVE_FOLDER, content_type="application/json",
        data=self._get_request_data(obj_type, obj_id, folder="a"))

    self.assertStatus(response, expected_status)
    obj = get_model(obj_type).query.get(obj_id)
    self.assertEqual(obj.folder, "a")


@ddt.ddt
class TestWithReadOnlyAccessExport(TestCase):
  """Test for exporting objects with read-only access."""

  def setUp(self):
    """setUp"""
    super(TestWithReadOnlyAccessExport, self).setUp()
    self.api = api_helper.Api()

  @ddt.data(
      'Creator', 'Reader', 'Editor', 'Administrator'
  )
  def test_export_system(self, role_name):
    """Test exporting of System objects."""
    role_obj = all_models.Role.query.filter(
        all_models.Role.name == role_name
    ).one()

    with factories.single_commit():
      system = factories.SystemFactory()
      user = factories.PersonFactory()
      rbac_factories.UserRoleFactory(role=role_obj, person=user)
      system.add_person_with_role_name(user, "Admin")

    self.api.set_user(user)

    search_request = [{
        "object_name": "System",
        "fields": "all",
        "filters": {
            "expression": {}
        }
    }]

    response = self.export_parsed_csv(search_request, self.api.user_headers)
    self.assertEqual(len(response["System"]), 1)
    self.assertNotIn("Read-only", response["System"][0])

  def test_export_system_template(self):
    """Test exporting of System import template."""
    self.client.get("/login")
    response = self.export_csv_template([{"object_name": "System"}])
    self.assertNotIn("Read-only", response.data)
    self.assertNotIn("readonly", response.data)

  def test_export_system_attributes(self):
    """Test that Read-only flag is not show on export page."""
    export_attributes = views.get_all_attributes_json()
    self.assertNotIn("Read-only", export_attributes)
    self.assertNotIn("readonly", export_attributes)
    self.assertNotIn("hidden", export_attributes)
