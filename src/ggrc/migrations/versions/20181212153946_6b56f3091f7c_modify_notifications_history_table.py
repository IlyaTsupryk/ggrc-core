# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Modify notifications_history table

Create Date: 2018-12-12 15:39:46.379333
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

from alembic import op


# revision identifiers, used by Alembic.
revision = '6b56f3091f7c'
down_revision = '44f601715634'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  op.execute("""
      ALTER TABLE notifications_history
        ADD notification_id INT(11) NOT NULL AFTER id;
  """)
  op.execute("""
      UPDATE notifications_history
        SET notification_id=id;
  """)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  op.execute("""
      ALTER TABLE notifications_history
        DROP COLUMN notification_id;
  """)
