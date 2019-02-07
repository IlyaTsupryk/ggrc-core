# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""A mixin for models that can be synchronized using SyncService."""

from datetime import datetime

from sqlalchemy.orm import validates

from ggrc import db
from ggrc.models import reflection
from ggrc.models.exceptions import ValidationError


class ChangesSynchronized(object):  # pylint: disable=too-few-public-methods
  """Mixin override "updated_at" attribute by removing "onupdate" handler."""
  updated_at = db.Column(
      db.DateTime,
      nullable=False,
      default=lambda: datetime.utcnow().replace(microsecond=0).isoformat()
  )

  @validates('updated_at')
  def validate_updated_at(self, _, value):  # pylint: disable=no-self-use
    """Add explicit non-nullable validation."""
    if not value:
      return datetime.utcnow().replace(microsecond=0).isoformat()

    return value


class AttributesSynchronized(object):  # pylint: disable=too-few-public-methods
  """Mixin that extand "_api_attrs" with additional attributes."""
  _sync_attrs = {
      'id',
      'created_at',
      'updated_at',
  }

  def get_sync_attrs(self):
    """Extend "_api_attrs" with additional attributes."""
    return self._sync_attrs


class Synchronizable(ChangesSynchronized,
                     AttributesSynchronized):
  """Mixin that identifies models that will be used by SyncService."""

  external_id = db.Column(db.Integer, nullable=True, unique=True)

  _api_attrs = reflection.ApiAttributes(
      'external_id',
  )

  @staticmethod
  def _extra_table_args(_):
    return (
        db.UniqueConstraint('external_id', name='uq_external_id'),
    )

  @validates('external_id')
  def validate_external_id(self, _, value):  # pylint: disable=no-self-use
    """Add explicit non-nullable validation."""
    if value is None:
      raise ValidationError("External ID for the object is not specified")

    return value
