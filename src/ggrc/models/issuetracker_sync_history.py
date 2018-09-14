# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for ggrc background operations."""
from ggrc import db
from ggrc.models import mixins
from ggrc.models.deferred import deferred


class IssuetrackerSyncHistory(mixins.Base, db.Model):
  """Background operation model."""
  __tablename__ = 'issuetracker_sync_history'

  result = db.Column(db.Boolean)
  error = db.Column(db.String)
  bg_task_id = deferred(
      db.Column(db.Integer, db.ForeignKey('background_tasks.id')),
      'IssuetrackerSyncHistory'
  )
  object_type = db.Column(db.String)
  object_id = db.Column(db.Integer)
