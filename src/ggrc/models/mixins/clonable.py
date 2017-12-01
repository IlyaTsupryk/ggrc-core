# Copyright (C) 2017 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""A mixin for objects that can be cloned"""

import itertools

import datetime

import sqlalchemy as sa
from collections import defaultdict
from werkzeug.exceptions import BadRequest

from ggrc import db
from ggrc.models import relationship, inflector
from ggrc.services import signals


class SingleClonable(object):
  """Clonable mixin"""

  __lazy_init__ = True

  CLONEABLE_CHILDREN = {}

  _operation_data = {}

  @classmethod
  def init(cls, model):
    cls.set_handlers(model)

  @classmethod
  def set_handlers(cls, model):
    """Set up handlers for cloning"""
    # pylint: disable=unused-argument, unused-variable
    @signals.Restful.collection_posted.connect_via(model)
    def handle_model_clone(sender, objects=None, sources=None):
      for obj, src in itertools.izip(objects, sources):
        if src.get("operation") == "clone":
          options = src.get("cloneOptions")
          mapped_objects = options.get("mappedObjects", [])
          source_id = int(options.get("sourceObjectId"))
          obj.clone(
              source_id=source_id,
              mapped_objects={obj for obj in mapped_objects
                              if obj in model.CLONEABLE_CHILDREN})

    @signals.Restful.model_posted_after_commit.connect_via(model)
    def handle_scope_clone(sender, obj=None, src=None, service=None,
                           event=None):
      if src.get("operation") == "clone":
        from ggrc.snapshotter import clone_scope

        options = src.get("cloneOptions")
        source_id = int(options.get("sourceObjectId"))
        base_object = model.query.get(source_id)
        clone_scope(base_object, obj, event)

  def generate_attribute(self, attribute):
    """Generate a new unique attribute as a copy of original"""
    attr = getattr(self, attribute)

    def count_values(key, value):
      return self.query.filter_by(**{key: value}).count()

    i = 1
    generated_attr_value = "{0} - copy {1}".format(attr, i)
    while count_values(attribute, generated_attr_value):
      i += 1
      generated_attr_value = "{0} - copy {1}".format(attr, i)
    return generated_attr_value

  def clone_custom_attribute_values(self, obj):
    """Copy object's custom attribute values"""
    ca_values = obj.custom_attribute_values

    for value in ca_values:
      value._clone(self)  # pylint: disable=protected-access

  def update_attrs(self, values):
    for key, value in values.items():
      setattr(self, key, value)


class MultiClonable(object):

  CLONEABLE_CHILDREN = {}

  @classmethod
  def handle_model_clone(cls, query):
    from ggrc.query import views

    if not query:
      return BadRequest()
    import ipdb;ipdb.set_trace()

    source_ids = query.get("sourceObjectIds", [])
    if not source_ids:
      return BadRequest("sourceObjectIds parameter wasn't provided")

    dest_query = query.get("destination", {})
    destination = None
    if dest_query and dest_query.get("type") and dest_query.get("id"):
      destination_cls = inflector.get_model(dest_query.get("type"))
      destination = destination_cls.query.filter_by(
          id=dest_query.get("id")
      ).first()

    mapped_types = {
        type_ for type_ in query.get("mappedObjects", [])
        if type_ in cls.CLONEABLE_CHILDREN
    }

    source_objs = cls.query.options(
        sa.orm.subqueryload('custom_attribute_definitions'),
        sa.orm.subqueryload('custom_attribute_values'),
    ).filter(cls.id.in_(source_ids)).all()

    clonned_objs = {}
    for source_obj in source_objs:
      clonned_objs[source_obj] = cls._clone_obj(source_obj, destination)

    for target, mapped_obj in cls._collect_mapped(source_objs, mapped_types):
      clonned_objs[mapped_obj] = cls._clone_obj(mapped_obj, target)

    db.session.flush()

    for source, clonned in clonned_objs.items():
      cls._clone_cads(source, clonned)

    db.session.commit()

    collections = []
    for obj in clonned_objs:
      collections.append(
          views.build_collection_representation(cls, obj.log_json())
      )
    return views.json_success_response(collections, datetime.datetime.now())

  @classmethod
  def _clone_obj(cls, source, target=None):
    clonned_object = source._clone()
    if target:
      db.session.add(relationship.Relationship(
          source=target,
          destination=clonned_object,
      ))
    return clonned_object

  @classmethod
  def _clone_cads(cls, source, target):
    for cad in source.custom_attribute_definitions:
      # Copy only local CADs
      if cad.definition_id:
        # pylint: disable=protected-access
        cad._clone(target)

  @classmethod
  def _collect_mapped(cls, source_objs, mapped_types):
    if not mapped_types:
      return []

    source_ids = {obj.id: obj for obj in source_objs}
    related_data = db.session.query(
        relationship.Relationship.source_id,
        relationship.Relationship.destination_type,
        relationship.Relationship.destination_id,
    ).filter(
        relationship.Relationship.source_type == cls.__name__,
        relationship.Relationship.source_id.in_(source_ids),
        relationship.Relationship.destination_type.in_(mapped_types)
    ).union_all(
        db.session.query(
            relationship.Relationship.destination_id,
            relationship.Relationship.source_type,
            relationship.Relationship.source_id,
        ).filter(
            relationship.Relationship.destination_type == cls.__name__,
            relationship.Relationship.destination_id.in_(source_ids),
            relationship.Relationship.source_type.in_(mapped_types)
        )
    ).all()

    related_type_ids = defaultdict(set)
    for _, related_type, related_id in related_data:
      related_type_ids[related_type].add(related_id)

    related_objs = defaultdict(dict)
    # Make related object loading for each type
    for type_, ids in related_type_ids.items():
      related_model = inflector.get_model(type_)
      related_query = related_model.query.options(
          sa.orm.subqueryload('custom_attribute_definitions'),
      ).filter(related_model.id.in_(ids))
      for related in related_query:
        related_objs[type_][related.id] = related

    source_related_objs = []
    for src_id, rel_type, rel_id in related_data:
      source_related_objs.append(
          (source_ids[src_id], related_objs[rel_type][rel_id])
      )

    return source_related_objs

