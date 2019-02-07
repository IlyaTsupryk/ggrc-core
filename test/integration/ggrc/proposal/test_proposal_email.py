# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""This module contains test about sending emails for proposals."""
import ddt
import mock
from ggrc.notifications import fast_digest
from integration.ggrc import TestCase
from integration.ggrc.api_helper import Api
from integration.ggrc.models import factories


@ddt.ddt
class TestProposalEmail(TestCase):
  """Test case about email sending and email presenting for proposals."""

  def setUp(self):
    super(TestProposalEmail, self).setUp()
    self.api = Api()
    self.client.get("/login")

  @ddt.data(True, False)
  def test_email_presentation(self, is_admin):
    """Test presentation of proposal digest email if is_admin is {0}."""
    person = factories.PersonFactory()
    self.api.set_user(person=person)
    with mock.patch("ggrc.rbac.permissions.is_admin", return_value=is_admin):
      resp = self.client.get("/_notifications/show_fast_digest")
    if is_admin:
      self.assert200(resp)
    else:
      self.assert403(resp)

  def test_email_sending(self):
    """Test sending emails about proposals."""
    role_1 = factories.AccessControlRoleFactory(object_type="Risk",
                                                notify_about_proposal=True)
    role_2 = factories.AccessControlRoleFactory(object_type="Risk",
                                                notify_about_proposal=True)
    role_3 = factories.AccessControlRoleFactory(object_type="Risk",
                                                notify_about_proposal=False)
    with factories.single_commit():
      risk = factories.RiskFactory()
      person_1 = factories.PersonFactory()  # has 1 role
      person_2 = factories.PersonFactory()  # has no roles
      person_3 = factories.PersonFactory()  # has 2 roles
      factories.PersonFactory()  # not related to risk at all
      factories.AccessControlPersonFactory(
          ac_list=risk.acr_acl_map[role_1],
          person=person_1
      )
      factories.AccessControlPersonFactory(
          ac_list=risk.acr_acl_map[role_1],
          person=person_3
      )
      factories.AccessControlPersonFactory(
          ac_list=risk.acr_acl_map[role_2],
          person=person_3
      )
      factories.AccessControlPersonFactory(
          ac_list=risk.acr_acl_map[role_3],
          person=person_2
      )
      proposal_1 = factories.ProposalFactory(
          instance=risk,
          content={
              "fields": {"title": "a"},
              "access_control_list": {},
              "custom_attribute_values": {},
              "mapping_fields": {},
              "mapping_list_fields": {},
          },
          agenda="agenda 1")
      proposal_2 = factories.ProposalFactory(
          instance=risk,
          content={
              "fields": {"title": "b"},
              "access_control_list": {},
              "custom_attribute_values": {},
              "mapping_fields": {},
              "mapping_list_fields": {},
          },
          agenda="agenda 2")
    self.assertIsNone(proposal_1.proposed_notified_datetime)
    self.assertIsNone(proposal_2.proposed_notified_datetime)
    with mock.patch("google.appengine.api.mail.send_mail") as mailer_mock:
      with mock.patch.object(fast_digest.DIGEST_TMPL,
                             "render") as bodybuilder_mock:
        fast_digest.send_notification()
    self.assertIsNotNone(proposal_1.proposed_notified_datetime)
    self.assertIsNotNone(proposal_2.proposed_notified_datetime)
    self.assertEqual(2, len(bodybuilder_mock.call_args_list))
    self.assertEqual(2, len(mailer_mock.call_args_list))
    # email to each required person
    self.assertListEqual(
        sorted([person_1.email, person_3.email]),
        sorted([a[1]["to"] for a in mailer_mock.call_args_list]))
    # no matter how many roles each proposal should be otified
    # only once for that person
    self.assertListEqual(
        [2] * 2,
        [len(a[1]["proposals"]) for a in bodybuilder_mock.call_args_list])
