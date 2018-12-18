# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""A mixin for models that can be synchronized using SyncService."""

from datetime import datetime

from sqlalchemy.orm import validates

from ggrc import db


class Synchronizable(object):
  """Mixin that identification of models that will be used by SyncService."""

  # We are overriding "update_at" attribute by removing "onupdate" handler.
  updated_at = db.Column(
      db.DateTime,
      nullable=False,
      default=lambda: datetime.utcnow().replace(microsecond=0).isoformat()
  )

  _sync_attrs = {
      'id',
      'created_at',
      'updated_at'
  }

  @validates('updated_at')
  def validate_updated_at(self, _, value):  # pylint: disable=no-self-use
    """Add explicit non-nullable validation."""
    if not value:
      return datetime.utcnow().replace(microsecond=0).isoformat()

    return value

  def get_sync_attrs(self):
    """Extend "_api_attrs" with additional attributes."""
    return self._sync_attrs
