# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control List"""

from ggrc.fulltext import mysql
from ggrc.models import all_models
from integration.ggrc import TestCase
from integration.ggrc.access_control import acl_helper
from integration.ggrc.models import factories
from integration.ggrc.api_helper import Api


class TestAccessControlList(TestCase):
  """TestAccessControlList"""

  @classmethod
  def setUpClass(cls):
    """Sets objects common for all tests in TestCase."""
    super(TestAccessControlList, cls).setUpClass()
    cls.api = Api()

  def setUp(self):
    super(TestAccessControlList, self).setUp()
    self.api = Api()

    self.person = factories.PersonFactory(name="My Person")
    self.acr = factories.AccessControlRoleFactory(
        object_type="Control", read=True
    )
    self.second_acr = factories.AccessControlRoleFactory(
        object_type="Control", read=True
    )
    self.control = factories.ControlFactory()
    self.assertion = factories.ControlAssertionFactory()
    factories.AccessControlPersonFactory(
        ac_list=self.control.acr_acl_map[self.acr],
        person=self.person,
    )

  def _acl_asserts(self, acl, acr_id, person_id):
    """Run asserts on a given acl list"""
    self.assertEqual(
        len(acl), 1, "Access control list did not get saved {}".format(acl)
    )
    self.assertTrue(acl[0]["id"] > 0, "Acces control list did not set an id")
    self.assertEqual(
        acl[0]["ac_role_id"], acr_id,
        "Access control list does not include the saved role id"
    )
    self.assertEqual(
        acl[0]["person_id"], person_id,
        "Access control list does not include person id {}".format(acl[0])
    )

  def _post_control(self, acr_id, person_id, assertion_id, collection=False):
    """Helper function for posting a control"""
    title = factories.random_str(prefix="Control - ")
    control = {
        "control": {
            "title": title,
            "type": "Control",
            "context": None,
            "access_control_list": [
                acl_helper.get_acl_json(acr_id, person_id)
            ],
            "assertions": [{
                "id": assertion_id
            }],
            "external_id": factories.SynchronizableExternalId.next(),
        },
    }
    with self.api.as_external():
      response = self.api.post(
          all_models.Control, [control] if collection else control)

    self.assertTrue(
        response.status_code == 200 or response.status_code == 201,
        "Control not created successfully {}".format(response.status)
    )

    if collection:
      return response.json[0][1]
    return response.json

  def test_object_roles(self):
    """Test if roles are fetched with the object"""
    acr_id, person_id = self.acr.id, self.person.id
    response = self.api.get(all_models.Control, self.control.id)
    self.assert200(
        response, "Failed to fetch created control {}".format(response.status)
    )
    self.assertIn(
        "access_control_list", response.json["control"],
        "Access Control List not present in {}".format(
            response.json["control"].keys()
        )
    )

    acl = response.json["control"]["access_control_list"]
    self._acl_asserts(acl, acr_id, person_id)

  def test_post_object_roles(self):
    """Test if roles are stored correctly when POSTed with the object"""
    acr_id, person_id = self.acr.id, self.person.id
    assertion_id = self.assertion.id
    response = self._post_control(acr_id, person_id, assertion_id)
    acl = response["control"]["access_control_list"]
    self._acl_asserts(acl, acr_id, person_id)

  def test_acl_revision_content(self):
    """Test if the access control list is added to revisions"""
    acr_id, person_id = self.acr.id, self.person.id
    assertion_id = self.assertion.id
    response = self._post_control(acr_id, person_id, assertion_id)
    control_id = response["control"]["id"]
    rev = all_models.Revision.query.filter(
        all_models.Revision.resource_id == control_id,
        all_models.Revision.resource_type == "Control"
    ).first()

    acl = rev.content["access_control_list"]
    self._acl_asserts(acl, acr_id, person_id)

  def test_put_object_roles(self):
    """Test if PUTing object roles saves them correctly"""
    second_acr_id, person_id = self.second_acr.id, self.person.id
    response = self.api.get(all_models.Control, self.control.id)
    self.assert200(
        response, "Failed to fetch created control {}".format(response.status)
    )

    control = response.json['control']
    control['access_control_list'].append(
        acl_helper.get_acl_json(second_acr_id, person_id))
    with self.api.as_external():
      response = self.api.put(self.control, {"control": control})
    self.assert200(
        response, "PUTing control failed {}".format(response.status)
    )

    acl = response.json['control']['access_control_list']
    self.assertEqual(
        len(acl), 2, "Access control list not updated {}".format(acl)
    )

  def test_put_removing_roles(self):
    """Test if PUTing an empty list removes object roles correct"""
    response = self.api.get(all_models.Control, self.control.id)
    self.assert200(
        response, "Failed to fetch created control {}".format(response.status)
    )

    control = response.json['control']
    control['access_control_list'] = []
    with self.api.as_external():
      response = self.api.put(self.control, {"control": control})
    self.assert200(
        response, "PUTing control failed {}".format(response.status)
    )

    acl = response.json['control']['access_control_list']
    self.assertEqual(
        len(acl), 0, "Access control list not empty {}".format(acl)
    )

  def test_acl_indexing_on_post(self):
    """Test if roles are stored correctly when POSTed with the object"""
    acr_id, person_id = self.acr.id, self.person.id
    assertion_id = self.assertion.id
    response = self._post_control(acr_id, person_id, assertion_id)
    control = response["control"]
    res = mysql.MysqlRecordProperty.query.filter(
        mysql.MysqlRecordProperty.type == "Control",
        mysql.MysqlRecordProperty.key == control["id"],
        mysql.MysqlRecordProperty.property == self.acr.name
    ).all()

    self.assertTrue(
        len(res) > 0,
        "Full text record index not created for {}".format(self.acr.name)
    )

    # email is presented in __sort__ subproperty as well
    self.assertEqual(
        len([r for r in res if r.content == self.person.email]), 2,
        "Person email not indexed {}".format(self.person.email)
    )

    self.assertEqual(
        len([r for r in res if r.content == self.person.name]), 1,
        "Person name not indexed {}".format(self.person.name)
    )

  def test_acl_revision_count(self):
    """Test if acl revision is created when object POSTed and PUTed"""
    acr_id, person_id = self.acr.id, self.person.id
    assertion_id = self.assertion.id

    response = self._post_control(acr_id, person_id, assertion_id)
    # One ACL and Control created in setUp and on by POST
    self.assertEqual(
        all_models.Revision.query.filter_by(
            resource_type="AccessControlPerson"
        ).count(),
        2
    )
    self.assertEqual(
        all_models.Revision.query.filter_by(
            resource_type="Control"
        ).count(),
        2
    )

    # If content of "access_control_list" is changed,
    # new revision should be created for ACL
    control = response["control"]
    control["access_control_list"] = []
    with self.api.as_external():
      self.api.put(
          all_models.Control.query.get(control["id"]),
          {"control": control}
      )
    self.assertEqual(
        all_models.Revision.query.filter_by(
            resource_type="AccessControlPerson"
        ).count(),
        3
    )
    self.assertEqual(
        all_models.Revision.query.filter_by(
            resource_type="Control"
        ).count(),
        3
    )
