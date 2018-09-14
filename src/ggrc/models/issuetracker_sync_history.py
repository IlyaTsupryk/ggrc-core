# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for ggrc background operations."""
from ggrc import db
from ggrc.models import mixins


class IssuetrackerSyncHistory(mixins.Base, db.Model):
  """Background operation model."""
  __tablename__ = 'issuetracker_sync_history'

  result = db.Column(db.Boolean, nullable=False)
  error = db.Column(db.String, nullable=True)
  bg_task_id = db.Column(
      db.Integer,
      db.ForeignKey('background_tasks.id'),
      nullable=False
  )
  object_type = db.Column(db.String, nullable=False)
  object_id = db.Column(db.Integer, nullable=False)

  bg_task = db.relationship("BackgroundTask")
