# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for ggrc background operations."""
from ggrc import db
from ggrc.models import mixins


class BackgroundOperation(mixins.Base, db.Model):
  """Background operation model."""
  __tablename__ = 'background_operations'

  name = db.Column(db.String)

