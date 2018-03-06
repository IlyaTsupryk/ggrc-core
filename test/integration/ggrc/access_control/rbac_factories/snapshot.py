# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Snapshot RBAC Factory."""

import sqlalchemy as sa

from ggrc import db
from ggrc.models import all_models, get_model

from integration.ggrc import Api, generator, TestCase
from integration.ggrc.access_control.rbac_factories import base
from integration.ggrc.models import factories


class SnapshotRBACFactory(base.BaseRBACFactory):
  """Snapshot RBAC factory class."""

  def __init__(self, user_id, acr, parent=None):
    """Set up objects for Snapshot permission tests.

    Args:
        user_id: Id of user under which all operations will be run.
        acr: Instance of ACR that should be assigned for tested user.
        parent: Model name in scope of which objects should be set up.
    """
    self.setup_program_scope(user_id, acr)

    control = factories.ControlFactory()
    # pylint: disable=protected-access
    snapshot = TestCase._create_snapshots(self.audit, [control])[0]
    factories.RelationshipFactory(source=control, destination=self.program)
    if parent == "Assessment":
      factories.RelationshipFactory(
          source=snapshot, destination=self.assessment
      )

    self.control_id = control.id
    self.snapshot_id = snapshot.id
    self.user_id = user_id

    self.api = Api()
    self.objgen = generator.ObjectGenerator()
    self.objgen.api = self.api

    if user_id:
      user = all_models.Person.query.get(user_id)
      self.api.set_user(user)

  def _update_orig_obj(self):
    """Update title of original object of Snapshot."""
    snapshot = all_models.Snapshot.query.get(self.snapshot_id)
    original = get_model(snapshot.child_type).query.get(snapshot.child_id)
    # Assume that Admin is first in people table
    admin = all_models.Person.query.get(1)
    self.api.set_user(admin)
    self.api.put(original, {"title": factories.random_str()})
    user = all_models.Person.query.get(self.user_id)
    self.api.set_user(user)

  def read(self):
    """Read Snapshot object."""
    return self.api.get(all_models.Snapshot, self.snapshot_id)

  def read_original(self):
    """Read original object of Snapshot."""
    snapshot = all_models.Snapshot.query.get(self.snapshot_id)
    original = get_model(snapshot.child_type).query.get(snapshot.child_id)
    return self.api.get(original, original.id)

  def get_latest_version(self):
    """Get latest revisions for original object of Snapshot"""
    self._update_orig_obj()
    snapshot = all_models.Snapshot.query.get(self.snapshot_id)
    last_revision = db.session.query(
        sa.sql.func.max(all_models.Revision.id)
    ).filter(
        all_models.Revision.resource_type == snapshot.child_type,
        all_models.Revision.resource_id == snapshot.child_id,
    ).first()[0]
    return self.api.client.get(
        "api/revisions?id__in={}%2C{}".format(
            snapshot.revision.id, last_revision
        )
    )

  def update(self):
    """Update snapshot to the latest version."""
    self._update_orig_obj()
    snapshot = all_models.Snapshot.query.get(self.snapshot_id)
    return self.api.put(snapshot, {"update_revision": "latest"})
