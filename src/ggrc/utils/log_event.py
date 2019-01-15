# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Utils for event logging"""

import itertools

from logging import getLogger
from flask import request

from ggrc.models.cache import Cache
from ggrc.models.event import Event
from ggrc.models.revision import Revision
from ggrc.models.mixins.synchronizable import Synchronizable
from ggrc.login import get_current_user_id

logger = getLogger(__name__)


def _revision_generator(user_id, action, objects):
  """Geberate and return revisions for objects."""
  for obj in objects:
    revision = Revision(obj, user_id, action, obj.log_json())

    if isinstance(obj, Synchronizable):
      revision.created_at = obj.updated_at
      revision.updated_at = obj.updated_at

    yield revision


def _get_log_revisions(current_user_id, obj=None, force_obj=False):
  """Generate and return revisions for all cached objects."""
  revisions = []
  cache = Cache.get_cache()
  if not cache:
    return revisions
  modified_objects = set(cache.dirty)
  new_objects = set(cache.new)
  delete_objects = set(cache.deleted)
  all_edited_objects = itertools.chain(cache.new, cache.dirty, cache.deleted)
  relationships_changes = (o for o in all_edited_objects
                           if o.type == "Relationship")
  for rel in relationships_changes:
    documentable = rel.get_related_for("Document")
    if documentable and documentable.type != "Comment":
      document = rel.get_related_for(documentable.type)
      if rel in new_objects and document not in documentable.documents:
        documentable.documents.append(document)
      if rel in delete_objects and document in documentable.documents:
        documentable.documents.remove(document)
      if (documentable not in new_objects and
              documentable not in delete_objects):
        modified_objects.add(documentable)

  revisions.extend(_revision_generator(
      current_user_id, "created", cache.new
  ))
  revisions.extend(_revision_generator(
      current_user_id, "modified", modified_objects
  ))
  if force_obj and obj is not None and obj not in cache.dirty:
    # If the ``obj`` has been updated, but only its custom attributes have
    # been changed, then this object will not be added into
    # ``cache.dirty set``. So that its revision will not be created.
    # The ``force_obj`` flag solves the issue, but in a bit dirty way.
    revision = Revision(obj, current_user_id, 'modified', obj.log_json())
    revisions.append(revision)
  revisions.extend(_revision_generator(
      current_user_id, "deleted", cache.deleted
  ))
  return revisions


# pylint: disable-msg=too-many-arguments
def log_event(session, obj=None, current_user_id=None, flush=True,
              force_obj=False, event=None):
  """Logs an event on object `obj`.

  Args:
    session: Current SQLAlchemy session (db.session)
    obj: object on which some operation took place
    current_user_id: ID of the user performing operation
    flush: If set to true, flush the session at the start
    force_obj: Used in case of custom attribute changes to force revision write
    event: event object to log
  Returns:
    Uncommitted models.Event instance
  """
  if flush:
    session.flush()
  if current_user_id is None:
    current_user_id = get_current_user_id()
  revisions = _get_log_revisions(current_user_id, obj=obj, force_obj=force_obj)
  if obj is None:
    resource_id = 0
    resource_type = None
    action = "BULK"
  else:
    resource_id = obj.id
    resource_type = str(obj.__class__.__name__)
    try:
      action = request.method
    except RuntimeError as exp:
      # Exception should affect the import request.
      action = "BULK"
      logger.warning("Request retrieval has failed: %s", exp.message)

  if not revisions:
    return event
  if event is None:
    event = Event(
        modified_by_id=current_user_id,
        action=action,
        resource_id=resource_id,
        resource_type=resource_type,
    )
    session.add(event)
  event.revisions.extend(revisions)
  return event
