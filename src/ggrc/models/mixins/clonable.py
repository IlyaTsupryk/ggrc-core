# Copyright (C) 2017 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""A mixin for objects that can be cloned"""

import itertools

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
    source_ids = query.get("sourceObjectIds", [])
    if not source_ids:
      return # TODO: Return some response with error

    destination = query.get("destination", {})
    destination_type = destination.get("type")
    destination_id = destination.get("id")
    destination_obj = None
    if destination_type and destination_id:
      destination_obj = inflector.get_model(destination_type).query.filter_by(
          id=destination_id
      ).first()
      if not destination_obj:
        return # TODO: Return some response with error

    mapped_objects = {
        obj for obj in query.get("mappedObjects", [])
        if obj in cls.CLONEABLE_CHILDREN
    }
    for source_id in source_ids:
      cls.clone(
          source=source_id,
          destination=destination_obj,
          mapped_objects=mapped_objects,
      )

  @classmethod
  def clone(cls, source, destination=None, mapped_objects=None):
    # TODO: don't grab objects by one, provide source_obj into function
    # TODO: check if such object exist in db
    source_object = cls.query.get(source_id)
    clonned_object = source_object._clone()
    cls._clone_cads(clonned_object)

    if any(mapped_objects):
      cls._clone_related_objects(source_object, clonned_object, mapped_objects)

  @classmethod
  def _clone_related_objects(cls, source_obj, clonned_obj, mapped_objects):
    for obj in source_obj.related_objects(mapped_objects):
      related_obj_copy = obj._clone(clonned_obj)
      db.session.add(relationship.Relationship(
          source=clonned_obj,
          destination=related_obj_copy
      ))
      cls._clone_cads(related_obj_copy)

  @classmethod
  def _clone_cads(cls, obj):
    for cad in obj.custom_attribute_definitions:
      # pylint: disable=protected-access
      cad._clone(obj)
