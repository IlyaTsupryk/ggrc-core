# Copyright (C) 2017 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Contains WithAction mixin.

A mixin for processing actions on an object in the scope of put request .
"""

from collections import namedtuple, defaultdict

from ggrc import db
from ggrc.login import get_current_user
from ggrc.models import inflector
from ggrc.models.comment import Comment
from ggrc.models.document import Document
from ggrc.models.exceptions import ValidationError
from ggrc.models.reflection import ApiAttributes
from ggrc.models.reflection import Attribute
from ggrc.models.relationship import Relationship


class WithAction(object):
  """Mixin for add/remove map/unmap actions processing"""

  _api_attrs = ApiAttributes(
      Attribute("actions", create=False, update=True, read=False)
  )
  _operation_order = [
      "add_related",
      "remove_related",
  ]
  _map_allowed_models = [
      "Document",
      "Comment",
      "Snapshot",
      "Assessment",
      "Issue",
  ]
  _actions = None
  _added = None  # collect added objects for signals sending
  _deleted = None  # collect deleted objects fro signals sending
  _relationships_map = None

  def actions(self, value):
    """Save actions for further processing"""
    if value:
      self._actions = value.get("actions")

  def _validate_actions(self):
    """Validate operation types"""
    invalid_actions = ",".join(set(self._actions) - set(self._operation_order))
    if invalid_actions:
      raise ValueError("Invalid actions found: {}".format(invalid_actions))

  def _build_relationships_map(self):
    """Build relationships map"""
    self._relationships_map = {
        (rel.destination_type, rel.destination_id): rel
        for rel in self.related_destinations
    }
    self._relationships_map.update({
        (rel.source_type, rel.source_id): rel
        for rel in self.related_sources
    })

  def _process_operation(self, operation):
    """Process operation actions"""
    for action in self._actions[operation]:
      # get object class
      obj_type = action.get("type")
      if not obj_type:
        raise ValidationError('type is not defined')
      obj_class = inflector.get_model(obj_type)
      if obj_type not in self._map_allowed_models or not obj_class:
        raise ValueError('Invalid action type: {type}'.format(type=obj_type))

      # get handler class
      action_type = '{type}Action'.format(type=obj_type)
      action_class = getattr(self, action_type, None)
      if not action_class:
        raise ValueError('Invalid action type: {type}'.format(type=obj_type))

      # process action
      # pylint: disable=not-callable
      added, deleted = getattr(action_class(), operation)(self, action)

      # collect added/deleted objects
      self._added.extend(added)
      self._deleted.extend(deleted)

  def process_actions(self):
    """Process actions"""
    if not self._actions:
      return {}, []

    self._validate_actions()

    self._added = []
    self._deleted = []

    for operation in self._operation_order:
      if operation not in self._actions:
        continue

      if not self._actions[operation]:
        continue

      self._build_relationships_map()
      self._process_operation(operation)

    # collect added/deleted objects for signals sending
    added = defaultdict(list)
    for obj in self._added:
      added[obj.__class__].append(obj)

    return added, self._deleted

  class BaseAction(object):
    """Base action"""

    AddRelated = namedtuple("AddRelated", ["id", "type"])
    MapRelated = namedtuple("MapRelated", ["id", "type"])
    RemoveRelated = namedtuple("RemoveRelated", ["id", "type"])

    def add_related(self, parent, _action):
      """Add/map object to parent"""
      added = []
      if _action.get("id"):
        action = self._validate(_action, self.MapRelated)
        obj = self._get(action)
      else:
        action = self._validate(_action, self.AddRelated)
        obj = self._create(parent, action)
        added.append(obj)

      rel = Relationship(source=parent,
                         destination=obj,
                         context=parent.context)
      added.append(rel)
      return added, []

    @staticmethod
    def _validate(_action, ntuple):
      try:
        return ntuple(**_action)
      except TypeError:
        raise ValidationError("Missed action parameters")

    # pylint: disable=unused-argument,no-self-use
    def _create(self, parent, action):
      raise ValidationError("Can't create {type} object".format(
          type=action.type))

    def _get(self, action):
      """Get object specified in action"""
      if not action.id:
        raise ValueError("id is not defined")
      obj_class = None
      # pylint: disable=protected-access
      if action.type in WithAction._map_allowed_models:
        obj_class = inflector.get_model(action.type)
      obj = obj_class.query.get(action.id) if obj_class else None
      if not obj:
        raise ValueError(
            'Object not found: {type} {id}'.format(type=action.type,
                                                   id=action.id))
      return obj

    def remove_related(self, parent, _action):
      """Remove relationship"""
      action = self._validate(_action, self.RemoveRelated)
      deleted = []
      obj = self._get(action)
      # pylint: disable=protected-access
      rel = parent._relationships_map.get((obj.type, obj.id))
      if rel:
        db.session.delete(rel)
        deleted.append(rel)
      return [], deleted

  class DocumentAction(BaseAction):
    """Document action"""

    AddRelated = namedtuple("AddRelated", ["id",
                                           "type",
                                           "document_type",
                                           "link",
                                           "title"])

    def _create(self, parent, action):
      obj = Document(link=action.link,
                     title=action.title,
                     document_type=action.document_type,
                     context=parent.context)
      return obj

  class CommentAction(BaseAction):
    """Comment action"""

    AddRelated = namedtuple("AddRelated", ["id",
                                           "type",
                                           "description",
                                           "custom_attribute_definition_id"])

    def _create(self, parent, action):
      # get assignee type
      current_user = get_current_user()
      # pylint: disable=protected-access
      rel = parent._relationships_map.get((current_user.type, current_user.id))
      if rel:
        assignee_type = rel.attrs["AssigneeType"]
      else:
        assignee_type = None
      # create object
      cad_id = action.custom_attribute_definition_id
      if not cad_id:
        obj = Comment(description=action.description,
                      assignee_type=assignee_type,
                      context=parent.context)
      else:
        obj = Comment(description=action.description,
                      custom_attribute_definition_id=cad_id,
                      assignee_type=assignee_type,
                      context=parent.context)

      return obj

  class SnapshotAction(BaseAction):
    """Snapshot action"""

  class AssessmentAction(BaseAction):
    """Assessment action"""

  class IssueAction(BaseAction):
    """Issue action"""
