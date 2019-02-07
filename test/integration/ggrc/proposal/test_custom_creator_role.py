# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test for proposal in case of usage of custom creator role"""

import json

from ggrc.models import all_models

from integration.ggrc import TestCase
from integration.ggrc.access_control import acl_helper
from integration.ggrc.api_helper import Api
from integration.ggrc.models import factories
from integration.ggrc_basic_permissions.models \
    import factories as rbac_factories
from integration.ggrc.query_helper import WithQueryApi


class TestOwnerAccess(TestCase, WithQueryApi):
  """Ensure that global creator has access to created proposal by him"""

  def setUp(self):
    super(TestOwnerAccess, self).setUp()
    self.client.get("/login")
    self.api = Api()

  @staticmethod
  def _get_create_proposal_request(risk_id, acr_id, person_id):
    """Prepare dict with proposal creation request"""

    return {
        "proposal": {
            "instance": {
                "id": risk_id,
                "type": all_models.Risk.__name__,
            },
            "full_instance_content": {"title": "new_title"},
            "agenda": "update cav",
            "context": None,
            "access_control_list": [acl_helper.get_acl_json(acr_id, person_id)]
        }
    }

  @staticmethod
  def _get_query_proposal_request(risk_id):
    """Prepare dict with proposal creation request"""

    return [{
        "limit": [0, 5],
        "object_name": all_models.Proposal.__name__,
        "order_by":[
            {"name": "status", "desc": True},
            {"name": "created_at", "desc": True},
        ],
        "filters": {
            "expression": {
                "left": {
                    "left": "instance_type",
                    "op": {"name": "="},
                    "right": all_models.Risk.__name__,
                },
                "op": {"name": "AND"},
                "right": {
                    "left": "instance_id",
                    "op": {"name": "="},
                    "right": risk_id,
                },
            },
        },
    }]

  def test_admin_has_access(self):
    """Ensure that global creator has access to created proposal by him"""
    role_creator = all_models.Role.query.filter(
        all_models.Role.name == "Creator").one()

    # prepare - create risk, assign roles
    factories.AccessControlRoleFactory(
        name="ACL_Reader",
        object_type="Risk",
        update=0
    )
    with factories.single_commit():
      risk = factories.RiskFactory()
      person = factories.PersonFactory()
      rbac_factories.UserRoleFactory(role=role_creator, person=person)
      factories.AccessControlPersonFactory(
          ac_list=risk.acr_name_acl_map["ACL_Reader"],
          person=person,
      )
      risk_id = risk.id

    # make query to create proposal
    self.api.set_user(person)
    self.client.get("/login")

    acr_class = all_models.AccessControlRole
    acr = acr_class.query.filter(acr_class.name == 'ProposalEditor',
                                 acr_class.object_type == 'Proposal').one()

    create_data = self._get_create_proposal_request(
        risk_id, acr.id, person.id)
    self.api.post(all_models.Proposal, create_data)

    query_data = self._get_query_proposal_request(risk_id)
    headers = {"Content-Type": "application/json", }
    resp = self.api.client.post("/query",
                                data=json.dumps(query_data),
                                headers=headers).json
    self.assertEqual(1, len(resp))
    self.assertEqual(resp[0]["Proposal"]["count"], 1)

  def test_nonadmin_has_no_access(self):
    """Test access to proposal for non creator of proposal"""
    role_creator = all_models.Role.query.filter(
        all_models.Role.name == "Creator").one()

    # prepare - create risk, assign roles
    factories.AccessControlRoleFactory(
        name="ACL_Reader",
        object_type="Risk",
        update=0
    )
    with factories.single_commit():
      risk = factories.RiskFactory()
      person1 = factories.PersonFactory()
      person2 = factories.PersonFactory()
      for person in (person1, person2):
        rbac_factories.UserRoleFactory(role=role_creator, person=person)
        factories.AccessControlPersonFactory(
            ac_list=risk.acr_name_acl_map["ACL_Reader"],
            person=person,
        )
      risk_id = risk.id
      person2_id = person2.id

    # make query to create proposal by person1
    self.api.set_user(person1)
    self.client.get("/login")

    acr_class = all_models.AccessControlRole
    acr = acr_class.query.filter(acr_class.name == 'ProposalEditor',
                                 acr_class.object_type == 'Proposal').one()

    create_data = self._get_create_proposal_request(
        risk_id, acr.id, person1.id)
    self.api.post(all_models.Proposal, create_data)

    # login as person2 and make request
    self.api.set_user(all_models.Person.query.get(person2_id))
    self.client.get("/login")

    query_data = self._get_query_proposal_request(risk_id)
    headers = {"Content-Type": "application/json", }
    resp = self.api.client.post("/query",
                                data=json.dumps(query_data),
                                headers=headers).json
    self.assertEqual(1, len(resp))
    self.assertEqual(resp[0]["Proposal"]["count"], 0)
