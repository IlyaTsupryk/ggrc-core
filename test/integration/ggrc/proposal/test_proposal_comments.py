# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test for proposal api."""

import ddt

from ggrc.models import all_models

from integration.ggrc import TestCase
from integration.ggrc.api_helper import Api
from integration.ggrc.models import factories


@ddt.ddt
class TestCommentsForProposals(TestCase):
  """Test generate comments for proposals."""

  def setUp(self):
    super(TestCommentsForProposals, self).setUp()
    self.api = Api()
    self.client.get("/login")

  TMPLS = all_models.Proposal.CommentTemplatesTextBuilder

  @ddt.data({"agenda": "",
             "comment": TMPLS.PROPOSED_WITHOUT_AGENDA},
            {"agenda": "tmp",
             "comment": TMPLS.PROPOSED_WITH_AGENDA.format(text="tmp")},
            {"agenda": "bla",
             "comment": TMPLS.PROPOSED_WITH_AGENDA.format(text="bla")},
            {"agenda": "<p>bla</p>",
             "comment": TMPLS.PROPOSED_WITH_AGENDA.format(text="bla")})
  @ddt.unpack
  def test_create(self, agenda, comment):
    """Test case create proposal with agenda {agenda}."""
    risk = factories.RiskFactory()
    risk_id = risk.id
    self.assertEqual(0, len(risk.comments))
    resp = self.api.post(
        all_models.Proposal,
        {"proposal": {
            "instance": {
                "id": risk.id,
                "type": risk.type,
            },
            # "content": {"123": 123},
            "full_instance_content": risk.log_json(),
            "agenda": agenda,
            "context": None,
        }})
    self.assertEqual(201, resp.status_code)
    risk = all_models.Risk.query.get(risk_id)
    self.assertEqual(1, len(risk.comments))
    self.assertEqual(comment, risk.comments[0].description)

  @ddt.data({"agenda": "",
             "comment_agenda": "",
             "status": all_models.Proposal.STATES.APPLIED,
             "tmpl": TMPLS.APPLIED_WITHOUT_COMMENT},
            {"agenda": "tmp",
             "comment_agenda": "tmp",
             "status": all_models.Proposal.STATES.APPLIED,
             "tmpl": TMPLS.APPLIED_WITH_COMMENT},
            {"agenda": "<p>tmp</p>",
             "comment_agenda": "tmp",
             "status": all_models.Proposal.STATES.APPLIED,
             "tmpl": TMPLS.APPLIED_WITH_COMMENT},
            {"agenda": "<p>     </p>",
             "comment_agenda": "",
             "status": all_models.Proposal.STATES.APPLIED,
             "tmpl": TMPLS.APPLIED_WITHOUT_COMMENT},
            {"agenda": "bla",
             "comment_agenda": "bla",
             "status": all_models.Proposal.STATES.APPLIED,
             "tmpl": TMPLS.APPLIED_WITH_COMMENT},
            {"agenda": "tmp",
             "comment_agenda": "tmp",
             "status": all_models.Proposal.STATES.DECLINED,
             "tmpl": TMPLS.DECLINED_WITH_COMMENT},
            {"agenda": " <p>tmp</p>      ",
             "comment_agenda": "tmp",
             "status": all_models.Proposal.STATES.DECLINED,
             "tmpl": TMPLS.DECLINED_WITH_COMMENT},
            {"agenda": "BLa",
             "comment_agenda": "BLa",
             "status": all_models.Proposal.STATES.DECLINED,
             "tmpl": TMPLS.DECLINED_WITH_COMMENT},
            {"agenda": "",
             "comment_agenda": "",
             "status": all_models.Proposal.STATES.DECLINED,
             "tmpl": TMPLS.DECLINED_WITHOUT_COMMENT})
  @ddt.unpack
  def test_change_status(self, agenda, comment_agenda, status, tmpl):
    """Test comment proposal status move to {status} with agenda {agenda}."""
    test_email = "foo@example.com"
    with factories.single_commit():
      risk = factories.RiskFactory()
      proposer = factories.PersonFactory(email=test_email)
    with factories.single_commit():
      proposal = factories.ProposalFactory(
          instance=risk,
          content={"field": "a"},
          agenda="agenda content",
          proposed_by=proposer)
    risk_id = risk.id
    if status == all_models.Proposal.STATES.APPLIED:
      resp = self.api.put(
          proposal, {"proposal": {"status": status, "apply_reason": agenda}})
    else:
      resp = self.api.put(
          proposal, {"proposal": {"status": status, "decline_reason": agenda}})
    self.assertEqual(200, resp.status_code)
    risk = all_models.Risk.query.get(risk_id)
    self.assertEqual(1, len(risk.comments))
    comment = tmpl.format(user=test_email, text=comment_agenda)
    self.assertEqual(comment, risk.comments[0].description)
