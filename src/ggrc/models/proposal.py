# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Defines a Revision model for storing snapshots."""

import sqlalchemy as sa
from sqlalchemy.orm import validates

from ggrc import db
from ggrc.models import inflector
from ggrc.models import mixins
from ggrc.models import reflection
from ggrc.models import relationship
from ggrc.models import types
from ggrc.models import utils
from ggrc.models.mixins import base
from ggrc.models.mixins import synchronizable
from ggrc.fulltext import mixin as ft_mixin
from ggrc.utils import referenced_objects
from ggrc.access_control import roleable
from ggrc.utils.revisions_diff import builder
from ggrc.models import comment

# pylint: disable=too-few-public-methods


class ProposalablePolymorphicRelationship(utils.JsonPolymorphicRelationship):
  """Custom relation for proposalable instance.

  Allow to setup instance over json serializaion."""

  def __call__(self, obj, json_obj):
    instance = super(ProposalablePolymorphicRelationship,
                     self).__call__(obj, json_obj)
    assert isinstance(instance, Proposalable)
    return instance


class FullInstanceContentFased(utils.FasadeProperty):
  """Custom fasade property for full_instance_content property."""

  FIELD_NAME = "content"

  def prepare(self, data):
    data = super(FullInstanceContentFased, self).prepare(data)
    content = builder.prepare(
        referenced_objects.get(data["instance"]["type"],
                               data["instance"]["id"]),
        data["full_instance_content"])

    # pop out unused object_people field out of mapping_list_fields
    if 'mapping_list_fields' in content:
      content['mapping_list_fields'].pop('object_people', None)
      content['mapping_list_fields'].pop('task_group_objects', None)
    return content


# pylint: enable=too-few-public-methods
# pylint: enable=no-self-use


class Proposal(mixins.person_relation_factory("applied_by"),
               mixins.person_relation_factory("declined_by"),
               mixins.person_relation_factory("proposed_by"),
               comment.CommentInitiator,
               mixins.Stateful,
               roleable.Roleable,
               relationship.Relatable,
               base.ContextRBAC,
               mixins.Base,
               ft_mixin.Indexed,
               db.Model):
  """Proposal model.

  Collect all information about propose change to Proposable instances."""

  __tablename__ = 'proposals'

  class STATES(object):
    """All states for proposals."""
    PROPOSED = "proposed"
    APPLIED = "applied"
    DECLINED = "declined"

  class CommentTemplatesTextBuilder(object):
    """Temapltes for comments for proposals."""
    PROPOSED_WITH_AGENDA = ("<p>Proposal has been created with comment: "
                            "{text}</p>")
    APPLIED_WITH_COMMENT = ("<p>Proposal created by {user} has been applied "
                            "with a comment: {text}</p>")
    DECLINED_WITH_COMMENT = ("<p>Proposal created by {user} has been declined "
                             "with a comment: {text}</p>")

    PROPOSED_WITHOUT_AGENDA = "<p>Proposal has been created.</p>"
    APPLIED_WITHOUT_COMMENT = ("<p>Proposal created by {user} "
                               "has been applied.</p>")
    DECLINED_WITHOUT_COMMENT = ("<p>Proposal created by {user} "
                                "has been declined.</p>")
  # pylint: enable=too-few-public-methods

  def build_comment_text(self, reason, text, proposed_by):
    """Build proposal comment dependable from proposal state."""
    if reason == self.STATES.PROPOSED:
      with_tmpl = self.CommentTemplatesTextBuilder.PROPOSED_WITH_AGENDA
      without_tmpl = self.CommentTemplatesTextBuilder.PROPOSED_WITHOUT_AGENDA
    elif reason == self.STATES.APPLIED:
      with_tmpl = self.CommentTemplatesTextBuilder.APPLIED_WITH_COMMENT
      without_tmpl = self.CommentTemplatesTextBuilder.APPLIED_WITHOUT_COMMENT
    elif reason == self.STATES.DECLINED:
      with_tmpl = self.CommentTemplatesTextBuilder.DECLINED_WITH_COMMENT
      without_tmpl = self.CommentTemplatesTextBuilder.DECLINED_WITHOUT_COMMENT
    tmpl = with_tmpl if text else without_tmpl
    return tmpl.format(user=proposed_by.email, text=text)

  VALID_STATES = [STATES.PROPOSED, STATES.APPLIED, STATES.DECLINED]

  instance_id = db.Column(db.Integer, nullable=False)
  instance_type = db.Column(db.String, nullable=False)
  content = db.Column('content', types.LongJsonType, nullable=False)
  agenda = db.Column(db.Text, nullable=False, default=u"")
  decline_reason = db.Column(db.Text, nullable=False, default=u"")
  decline_datetime = db.Column(db.DateTime, nullable=True)
  apply_reason = db.Column(db.Text, nullable=False, default=u"")
  apply_datetime = db.Column(db.DateTime, nullable=True)
  proposed_notified_datetime = db.Column(db.DateTime, nullable=True)

  INSTANCE_TMPL = "{}_proposalable"

  instance = ProposalablePolymorphicRelationship("instance_id",
                                                 "instance_type",
                                                 INSTANCE_TMPL)

  _fulltext_attrs = [
      "instance_id",
      "instance_type",
      "agenda",
      "decline_reason",
      "decline_datetime",
      "apply_reason",
      "apply_datetime",
  ]

  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute("instance", update=False),
      reflection.Attribute("content", create=False, update=False),
      reflection.Attribute("agenda", update=False),
      # ignore create proposal in specific state to be shure
      # new proposal will be only in proposed state
      reflection.Attribute('status', create=False),
      reflection.Attribute('decline_reason', create=False),
      reflection.Attribute('decline_datetime', create=False, update=False),
      reflection.Attribute('declined_by', create=False, update=False),
      reflection.Attribute('apply_reason', create=False),
      reflection.Attribute('apply_datetime', create=False, update=False),
      reflection.Attribute('applied_by', create=False, update=False),
      reflection.Attribute('full_instance_content',
                           create=True,
                           update=False,
                           read=False),
      reflection.Attribute('proposed_by', create=False, update=False),
  )

  full_instance_content = FullInstanceContentFased()

  @staticmethod
  def _extra_table_args(_):
    return (db.Index("fk_instance", "instance_id", "instance_type"),
            db.Index("ix_decline_datetime", "decline_datetime"),
            db.Index("ix_apply_datetime", "apply_datetime"),
            db.Index("ix_proposed_notified_datetime",
                     "proposed_notified_datetime"))

  # pylint: disable=no-self-use
  @validates("instance_type")
  def validate_instance_type(self, _, instance_type):
    """Validate instance_type attribute.

    We preventing creation of proposals for external models.
    """
    instance_class = inflector.get_model(instance_type)

    if issubclass(instance_class, synchronizable.Synchronizable):
      raise ValueError("Trying to create proposal for external model.")

    return instance_type


class Proposalable(object):  # pylint: disable=too-few-public-methods
  """Mixin to setup instance as proposable."""

  @sa.ext.declarative.declared_attr
  def proposals(cls):  # pylint: disable=no-self-argument
    """declare proposals relationship for proposable instance."""
    def join_function():
      return sa.and_(
          sa.orm.foreign(Proposal.instance_type) == cls.__name__,
          sa.orm.foreign(Proposal.instance_id) == cls.id,
      )

    return sa.orm.relationship(
        Proposal,
        primaryjoin=join_function,
        backref=Proposal.INSTANCE_TMPL.format(cls.__name__),
    )
