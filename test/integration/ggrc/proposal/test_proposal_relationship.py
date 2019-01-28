# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test for proposal relationship with parent instance."""

import ddt
import flask
import sqlalchemy as sa

from ggrc import db
from ggrc.models import all_models

from integration.ggrc import TestCase
from integration.ggrc.api_helper import Api
from integration.ggrc.models import factories


@ddt.ddt
class TestProposalRelationship(TestCase):
  """Test relationship for proposals."""

  def setUp(self):
    super(TestProposalRelationship, self).setUp()
    self.api = Api()
    self.client.get("/login")

  @staticmethod
  def proposal_relationships(obj):
    """Get relationships between any Proposal and object.

    Args:
        obj: Instance of Proposalable object.

    Returns:
        Query which return relationship ids.
    """
    return db.session.query(all_models.Relationship.id).filter(
        sa.or_(
            sa.and_(
                all_models.Relationship.source_type == 'Proposal',
                all_models.Relationship.destination_type == obj.type,
            ),
            sa.and_(
                all_models.Relationship.source_type == obj.type,
                all_models.Relationship.destination_type == 'Proposal',
            )
        )
    )

  def create_proposal_for(self, obj):
    """Create Proposal for obj.

    Args:
        obj: Instance of Proposalable object.

    Returns:
        Response with result of Proposal creation.
    """
    response = self.api.post(
        all_models.Proposal,
        {
            "proposal": {
                "instance": {
                    "id": obj.id,
                    "type": obj.type,
                },
                "full_instance_content": obj.log_json(),
                "context": None,
            }
        }
    )
    self.assertEqual(201, response.status_code)
    return response

  @ddt.data("Risk", "Control")
  def test_create(self, model_name):
    """Test if relationship between {} and Proposal is created."""
    obj = factories.get_model_factory(model_name)()
    self.create_proposal_for(obj)
    self.assertEqual(1, self.proposal_relationships(obj).count())

  def test_create_on_post_only(self):
    """Test if proposal relationship is created on post only."""
    control = factories.ControlFactory()
    response = self.create_proposal_for(control)
    post_rels = self.proposal_relationships(control).all()

    proposal = all_models.Proposal.query.get(response.json["proposal"]["id"])
    # Invalidate ACR cache manually as after first post
    # it will in detached state
    flask.g.global_ac_roles = None
    response = self.api.put(
        proposal,
        {
            "proposal": {
                "status": all_models.Proposal.STATES.APPLIED,
                "apply_reason": "test"
            }
        }
    )
    self.assert200(response)
    put_rels = self.proposal_relationships(control).all()
    self.assertEqual(post_rels, put_rels)

  def test_rel_remove_parent(self):
    """Test if relationship will be removed if parent instance is removed."""
    risk = factories.RiskFactory()
    self.create_proposal_for(risk)
    self.assertEqual(1, self.proposal_relationships(risk).count())

    response = self.api.delete(risk)

    self.assert200(response)
    self.assertEqual(0, self.proposal_relationships(risk).count())

  def test_rel_remove_proposal(self):
    """Test if relationship will be removed if proposal is removed."""
    control = factories.ControlFactory()
    response = self.create_proposal_for(control)
    self.assertEqual(1, self.proposal_relationships(control).count())

    proposal = all_models.Proposal.query.get(response.json["proposal"]["id"])
    response = self.api.delete(proposal)
    self.assert200(response)
    self.assertEqual(0, self.proposal_relationships(control).count())
