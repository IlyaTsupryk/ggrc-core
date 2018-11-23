# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Add import/export bg operation types

Create Date: 2018-11-26 13:57:01.178922
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op

from ggrc.migrations.utils import migrator

revision = '8737b9b51407'
down_revision = 'd9c56989ac07'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  connection = op.get_bind()
  migrator_id = migrator.get_migration_user_id(connection)
  connection.execute(
      sa.text("""
            INSERT INTO background_operation_types(
              `name`, modified_by_id, created_at, updated_at
            )
            VALUES('import', :migrator_id, now(), now()),
                  ('export', :migrator_id, now(), now());
        """),
      migrator_id=migrator_id,
  )


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise Exception("Downgrade is not supported.")
