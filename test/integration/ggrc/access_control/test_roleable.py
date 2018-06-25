# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control Roleable mixin"""
import ddt
from ggrc import db
from ggrc.models import all_models
from integration.ggrc import TestCase, api_helper
from integration.ggrc.models import factories


@ddt.ddt
class TestAccessControlRoleable(TestCase):
  """Test AccessControlList"""

  def setUp(self):
    super(TestAccessControlRoleable, self).setUp()
    self.api = api_helper.Api()
    with factories.single_commit():
      self.role = factories.AccessControlRoleFactory()
      self.person = factories.PersonFactory()

  @ddt.data(lambda self: [{
      "ac_role_id": self.role.id,
      "person": {
          "id": self.person.id
      }
  }], lambda self: [{
      "person": self.person,
      "ac_role": self.role
  }])
  def test_with_dict(self, acl_list):
    """Test access_control_list setter with a basic dict object
    This is the format the frontend uses"""
    obj = all_models.Control(
        title="New Control",
        access_control_list=acl_list(self))
    self.assertIsNotNone(obj.access_control_list)
    acl = obj.access_control_list[0]
    self.assertIsNotNone(acl)
    self.assertIsInstance(acl, all_models.AccessControlList)
    self.assertEqual(acl.person.id, self.person.id)
    self.assertEqual(acl.ac_role.id, self.role.id)
    self.assertEqual(acl.object, obj)

  def test_with_dict_objs_multiple(self):
    """Test access_control_list setter without ids"""

    def acl_query():
      return db.session.query(
          all_models.AccessControlList.person_id,
          all_models.AccessControlList.ac_role_id
      ).filter(
          all_models.AccessControlList.object_id == obj.id,
          all_models.AccessControlList.object_type == "Control"
      ).all()
    person_1 = all_models.Person(name="Frodo", email="frodo@baggins.com")
    person_2 = all_models.Person(name="Bilbo", email="bilbo@baggins.com")
    person_3 = factories.PersonFactory(name="Merry", email="merry@buck.com")
    role = all_models.AccessControlRole(name="Hobbit")
    obj = all_models.Control(title="Test Control", access_control_list=[{
        "person": person_1,
        "ac_role": self.role,
    }, {
        "person": person_2,
        "ac_role": role,
    }])
    db.session.commit()
    self.assertIsNotNone(obj.access_control_list)
    self.assertEqual(len(obj.access_control_list), 2)
    self.assertEqual(obj.access_control_list[0].person, person_1)
    self.assertEqual(obj.access_control_list[1].person, person_2)

    acls = acl_query()
    self.assertItemsEqual([
        (person_1.id, self.role.id),
        (person_2.id, role.id)
    ], acls)

    obj.access_control_list = [{
        "person": {
            "id": person_2.id,
        },
        "ac_role_id": role.id,
    }, {
        "person": {
            "id": person_3.id,
        },
        "ac_role_id": role.id,
    }]
    db.session.commit()

    acls = acl_query()
    self.assertItemsEqual([
        (person_2.id, role.id),
        (person_3.id, role.id)
    ], acls)

  def test_acl_cleanup_on_obj_delete(self):
    """Test if propagated roles of parent object is removed with child."""
    program_editor_acr = all_models.AccessControlRole.query.filter_by(
        object_type="Program",
        name="Program Editors",
    ).first()

    with factories.single_commit():
      person = factories.PersonFactory()
      program = factories.ProgramFactory()
      control = factories.ControlFactory()
      factories.RelationshipFactory(source=program, destination=control)

      factories.AccessControlListFactory(
          object=program,
          ac_role=program_editor_acr,
          person=person
      )

    response = self.api.delete(control)
    self.assertEqual(response.status_code, 200)
    acl_obj_types = db.session.query(all_models.AccessControlList.object_type)
    # All roles for first person should be removed
    self.assertEqual(acl_obj_types.count(), 1)
    self.assertEqual(acl_obj_types.first()[0], "Program")
