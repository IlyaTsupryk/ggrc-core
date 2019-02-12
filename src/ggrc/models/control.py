# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for control model and related classes."""

from sqlalchemy import orm
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property

from ggrc import db
from ggrc import login
from ggrc.models.comment import Commentable
from ggrc.models.mixins.with_similarity_score import WithSimilarityScore
from ggrc.models.object_document import PublicDocumentable
from ggrc.models.categorization import Categorizable
from ggrc.models.category import CategoryBase
from ggrc.models.mixins import base
from ggrc.models.mixins import synchronizable
from ggrc.models import mixins, review
from ggrc.models.mixins.with_last_assessment_date import WithLastAssessmentDate
from ggrc.models.deferred import deferred
from ggrc.models.object_person import Personable
from ggrc.models.relationship import Relatable
from ggrc.fulltext.mixin import Indexed
from ggrc.fulltext import attributes
from ggrc.models import reflection
from ggrc.models import proposal


class ControlCategory(CategoryBase):
  """Custom Category class for Control"""
  __mapper_args__ = {
      'polymorphic_identity': 'ControlCategory'
  }
  _table_plural = 'control_categories'


class ControlAssertion(CategoryBase):
  """Custom Assertion class for Control"""
  __mapper_args__ = {
      'polymorphic_identity': 'ControlAssertion'
  }
  _table_plural = 'control_assertions'


class ControlCategorized(Categorizable):
  """Mixin for control only. Declate categorizations for controls."""

  @declared_attr
  def categorizations(cls):  # pylint: disable=no-self-argument
    return cls.declare_categorizable(
        "ControlCategory", "category", "categories", "categorizations")

  _fulltext_attrs = [
      attributes.MultipleSubpropertyFullTextAttr(
          "categories",
          "categorizations",
          ["category"]
      ),
  ]
  _api_attrs = reflection.ApiAttributes(
      'categories',
      reflection.Attribute('categorizations', create=False, update=False),
  )

  _include_links = []

  _aliases = {
      "categories": "Categories",
  }

  @classmethod
  def eager_query(cls):
    """Eager Query"""
    query = super(ControlCategorized, cls).eager_query()
    return query.options(
        orm.subqueryload('categorizations').joinedload('category'),
    )

  def log_json(self):
    """Log categorizations too."""
    out_json = super(ControlCategorized, self).log_json()
    out_json["categories"] = [
        c.category.log_json()
        for c in self.categorizations]  # pylint:disable=not-an-iterable
    return out_json

  @classmethod
  def indexed_query(cls):
    return super(ControlCategorized, cls).indexed_query().options(
        orm.Load(cls).subqueryload(
            "categorizations"
        ).joinedload(
            "category"
        ).load_only(
            "name",
            "type",
        ),
    )


class AssertionCategorized(Categorizable):
  """Mixin for control only. Declate assertions for controls."""

  @declared_attr
  def categorized_assertions(cls):  # pylint: disable=no-self-argument
    return cls.declare_categorizable(
        "ControlAssertion", "assertion", "_assertions",
        "categorized_assertions")

  @hybrid_property
  def assertions(self):
    return self._assertions

  @assertions.setter
  def assertions(self, values):
    """Setter function for control's assertions.

    This setter function accepts two kind of values:
      - List of assertion objects. This is used to set assertions in back-end.
      - List of dicts containing json representation of assertion values. This
        is used when setting assertions through the API and json builder.

    Args:
      values: List of assertions or dicts containing json representation
        of assertion values.
    """
    if not values:
      raise ValueError("Missing mandatory attribute: assertions")
    if isinstance(values[0], dict):
      values = self._get_assertions(values)
    self._set_assertions(values)

  @staticmethod
  def _get_assertions(values):
    """Get assertion objects from serialized values.

    Args:
        values: List of dicts representing `ControlAssertion` objects.
    """
    new_assertions_ids = [v.get(u'id', False) for v in values]
    if not (new_assertions_ids and all(new_assertions_ids)):
      # Not all items in `values` contain `id` field.
      raise ValueError("Invalid values for attribute: assertions")
    new_assertions = ControlAssertion.eager_query().filter(
        ControlAssertion.id.in_(new_assertions_ids)).all()
    if len(new_assertions) != len(new_assertions_ids):
      # Not all passed assertion ids are valid.
      raise ValueError("Invalid values for attribute: assertions")
    return new_assertions

  def _set_assertions(self, values):
    """Set control assertions.

    Args:
        values: List of `ControlAssertion` objects.
    """
    # pylint: disable=not-an-iterable
    proxied_set_map = dict([
        (a.category, a) for a in self.categorized_assertions
    ])
    # pylint: enable=not-an-iterable
    old_set, new_set = set(self.assertions), set(values)
    current_user_id = login.get_current_user_id()

    for assertion in new_set - old_set:
      new_assertion = self.assertions.creator(assertion)
      new_assertion.modified_by_id = current_user_id
      self.categorized_assertions.append(new_assertion)

    for assertion in old_set - new_set:
      self.categorized_assertions.remove(proxied_set_map[assertion])

  _update_raw = ["assertions", ]

  _fulltext_attrs = [
      attributes.MultipleSubpropertyFullTextAttr(
          "assertions",
          "categorized_assertions",
          ["category"]
      ),
  ]
  _api_attrs = reflection.ApiAttributes(
      reflection.HybridAttribute('assertions'),
      reflection.Attribute('categorized_assertions',
                           create=False,
                           update=False),
  )
  _include_links = []

  _aliases = {
      "assertions": {
          "display_name": "Assertions",
          "mandatory": True,
      }
  }

  @classmethod
  def eager_query(cls):
    """Eager Query"""
    query = super(AssertionCategorized, cls).eager_query()
    return query.options(
        orm.subqueryload('categorized_assertions').joinedload('category'),
    )

  def log_json(self):
    """Log assertions too."""
    out_json = super(AssertionCategorized, self).log_json()
    # pylint: disable=not-an-iterable
    out_json["assertions"] = [a.category.log_json()
                              for a in self.categorized_assertions]
    return out_json

  @classmethod
  def indexed_query(cls):
    return super(AssertionCategorized, cls).indexed_query().options(
        orm.Load(cls).subqueryload(
            "categorized_assertions"
        ).joinedload(
            "category"
        ).load_only(
            "name",
            "type",
        ),
    )


class Control(synchronizable.Synchronizable,
              WithLastAssessmentDate,
              review.Reviewable,
              synchronizable.RoleableSynchronizable,
              Relatable,
              mixins.CustomAttributable,
              Personable,
              ControlCategorized,
              PublicDocumentable,
              AssertionCategorized,
              mixins.LastDeprecatedTimeboxed,
              mixins.TestPlanned,
              Commentable,
              WithSimilarityScore,
              base.ContextRBAC,
              mixins.BusinessObject,
              Indexed,
              mixins.Folderable,
              proposal.Proposalable,
              db.Model):
  """Control model definition."""
  __tablename__ = 'controls'

  company_control = deferred(db.Column(db.Boolean), 'Control')
  directive_id = deferred(
      db.Column(db.Integer, db.ForeignKey('directives.id')), 'Control')
  version = deferred(db.Column(db.String), 'Control')
  fraud_related = deferred(db.Column(db.Boolean), 'Control')
  key_control = deferred(db.Column(db.Boolean), 'Control')
  active = deferred(db.Column(db.Boolean), 'Control')
  kind = deferred(db.Column(db.String), "Control")
  means = deferred(db.Column(db.String), "Control")
  verify_frequency = deferred(db.Column(db.String), "Control")

  # REST properties
  _api_attrs = reflection.ApiAttributes(
      'active',
      'company_control',
      'directive',
      'fraud_related',
      'key_control',
      'kind',
      'means',
      'verify_frequency',
      'version',
  )

  _fulltext_attrs = [
      'active',
      'company_control',
      'directive',
      attributes.BooleanFullTextAttr(
          'fraud_related',
          'fraud_related',
          true_value="yes", false_value="no"),
      attributes.BooleanFullTextAttr(
          'key_control',
          'key_control',
          true_value="key", false_value="non-key"),
      'kind',
      'means',
      'verify_frequency',
      'version',
  ]

  _sanitize_html = [
      'version',
  ]

  VALID_RECIPIENTS = frozenset([
      "Assignees",
      "Creators",
      "Verifiers",
      "Admin",
      "Control Operators",
      "Control Owners",
      "Other Contacts",
  ])

  @classmethod
  def indexed_query(cls):
    return super(Control, cls).indexed_query().options(
        orm.Load(cls).undefer_group(
            "Control_complete"
        ),
        orm.Load(cls).joinedload(
            "directive"
        ).undefer_group(
            "Directive_complete"
        ),
    )

  _include_links = []

  _aliases = {
      "kind": "Kind/Nature",
      "means": "Type/Means",
      "verify_frequency": "Frequency",
      "fraud_related": "Fraud Related",
      "key_control": {
          "display_name": "Significance",
          "description": "Allowed values are:\nkey\nnon-key\n---",
      },
      "test_plan": "Assessment Procedure",
  }

  @classmethod
  def eager_query(cls):
    query = super(Control, cls).eager_query()
    return cls.eager_inclusions(query, Control._include_links).options(
        orm.joinedload('directive'),
    )

  def log_json(self):
    out_json = super(Control, self).log_json()
    # so that event log can refer to deleted directive
    if self.directive:
      out_json["mapped_directive"] = self.directive.display_name
    return out_json
