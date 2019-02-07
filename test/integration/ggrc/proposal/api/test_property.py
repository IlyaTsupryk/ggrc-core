# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""TestCase for proposal property api."""

from ggrc.models import all_models

from integration.ggrc.models import factories
from integration.ggrc.proposal.api import base


class TestPropoertyProposals(base.BaseTestProposalApi):
  """Test case for proposal property api."""

  def test_simple_get_proposal(self):
    """Test simple get proposal."""
    with factories.single_commit():
      risk = factories.RiskFactory()
      proposal = factories.ProposalFactory(instance=risk,
                                           content={"field": "a"},
                                           agenda="agenda content")
    instance_dict = {"id": risk.id, "type": risk.type}
    resp = self.api.get(all_models.Proposal, proposal.id)
    self.assert200(resp)
    self.assertIn("proposal", resp.json)
    data = resp.json["proposal"]
    self.assertIn("content", data)
    self.assertIn("instance", data)
    self.assertIn("agenda", data)
    self.assertDictEqual(instance_dict, data["instance"])
    self.assertDictEqual({"field": "a"}, data["content"])
    self.assertEqual("agenda content", data["agenda"])

  def test_simple_create_proposal(self):
    """Test simple create proposal."""
    new_vulnerability = "2"
    risk = factories.RiskFactory(vulnerability="1")
    risk_id = risk.id
    risk.vulnerability = new_vulnerability
    self.assertEqual(0, len(risk.comments))
    self.create_proposal(risk,
                         full_instance_content=risk.log_json(),
                         agenda="update title from 1 to 2",
                         context=None)
    risk = all_models.Risk.query.get(risk_id)
    self.assertEqual(1, len(risk.proposals))
    self.assertIn("fields", risk.proposals[0].content)
    self.assertEqual({"vulnerability": "2"},
                     risk.proposals[0].content["fields"])
    self.assertEqual(1, len(risk.comments))

  def test_simple_apply_status(self):
    """Test simple apply status."""
    with factories.single_commit():
      risk = factories.RiskFactory(title="1")
      proposal = factories.ProposalFactory(
          instance=risk,
          content={"fields": {"title": "2"}},
          agenda="agenda content")
    risk_id = risk.id
    proposal_id = proposal.id
    self.assertEqual(proposal.STATES.PROPOSED, proposal.status)
    self.assertEqual(0, len(risk.comments))
    with self.number_obj_revisions_for(risk):
      self.apply_proposal(proposal, apply_reason="approved")
    risk = all_models.Risk.query.get(risk_id)
    proposal = all_models.Proposal.query.get(proposal_id)

    self.assertEqual(proposal.STATES.APPLIED, proposal.status)
    self.assertEqual("2", risk.title)
    self.assertEqual("2", self.latest_revision_for(risk).content['title'])
    self.assertEqual(1, len(risk.comments))

  def test_simple_decline_status(self):
    """Test simple decline status."""
    with factories.single_commit():
      risk = factories.RiskFactory(title="1")
      proposal = factories.ProposalFactory(
          instance=risk,
          content={"fields": {"title": "2"}},
          agenda="agenda content")
    risk_id = risk.id
    proposal_id = proposal.id
    self.assertEqual(proposal.STATES.PROPOSED, proposal.status)
    self.assertEqual(0, len(risk.comments))
    with self.number_obj_revisions_for(risk, increase_on=0):
      self.decline_proposal(proposal, decline_reason="declined bla")
    risk = all_models.Risk.query.get(risk_id)
    proposal = all_models.Proposal.query.get(proposal_id)
    self.assertEqual(proposal.STATES.DECLINED, proposal.status)
    self.assertEqual("1", risk.title)
    self.assertEqual(1, len(risk.comments))
