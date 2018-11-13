# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Remove deprecated CT notifications

Create Date: 2018-11-13 11:54:32.612420
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

from alembic import op

import sqlalchemy as sa

from ggrc.migrations import utils

revision = '12feca8f6b1f'
down_revision = '9beabcd92f34'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()

  notification_ids = connection.execute("""
      SELECT id
      FROM notifications
      WHERE object_type = 'CycleTaskGroupObjectTask'
        AND (sent_at IS NULL OR repeating IS true)
        AND object_id IN (
          SELECT id
          FROM cycle_task_group_object_tasks
          WHERE status = 'Deprecated'
        );
  """).fetchall()

  # Convert list of tuples to list of integers
  notification_ids = [i[0] for i in notification_ids]
  if not notification_ids:
    return
  connection.execute(
      sa.text("""
          DELETE FROM notifications
          WHERE id IN :notification_ids
      """),
      notification_ids=notification_ids
  )

  utils.add_to_objects_without_revisions_bulk(
      connection,
      notification_ids,
      "Notification",
      action="deleted"
  )


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise Exception("Downgrade is not supported.")
