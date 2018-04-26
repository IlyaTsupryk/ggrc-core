# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

import logging
from flask import g, has_app_context

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Cache:
  """
  Tracks modified objects in the session distinguished by
  type of modification: new, dirty and deleted.
  """
  def __init__(self):
    self.clear()

  def update_before_flush(self, session, flush_context):
    """
    Before the flush happens, we can still access to-be-deleted objects, so
    record JSON for log here
    """
    for o in session.new:
      if hasattr(o, 'log_json'):
        self.new[o] = o.log_json()
    for o in session.deleted:
      if hasattr(o, 'log_json'):
        self.deleted[o] = o.log_json()
    dirty = set(o for o in session.dirty if session.is_modified(o))
    for o in dirty - set(self.new) - set(self.deleted):
      if hasattr(o, 'log_json'):
        self.dirty[o] = o.log_json()

  def update_after_flush(self, session, flush_context):
    """
    After the flush, we know which objects were actually deleted, not just
    modified (deletes due to cascades are not known pre-flush), so fix up
    cache.
    """
    for o in self.dirty.keys():
      # SQLAlchemy magic to determine whether object was actually deleted due
      #   to `cascade="all,delete-orphan"`
      # If an object was actually deleted, move it into `deleted`
      if flush_context.is_deleted(o._sa_instance_state):
        self.deleted[o] = self.dirty[o]
        del self.dirty[o]

  def clear(self):
    self.new = {}
    self.dirty = {}
    self.deleted = {}

  def copy(self):
    copied_cache = Cache()
    copied_cache.new = dict(self.new)
    copied_cache.dirty = dict(self.dirty)
    copied_cache.deleted = dict(self.deleted)
    return copied_cache

  @staticmethod
  def get_cache(create=False):
    """
    Retrieves the cache from the Flask global object. The create arg
    indicates if a new cache should be created if none exists. If we
    are not in a request context, no cache is created (return None).
    """
    if has_app_context():
      cache = getattr(g, 'cache', None)
      if cache is None and create:
        cache = g.cache = Cache()
      return cache
    else:
      logger.warning("No app context - no cache created")
      return None
