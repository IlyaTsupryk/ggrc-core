# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Add info about object and operation to BG task

Create Date: 2018-09-06 08:51:24.838989
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
from ggrc.migrations.utils import migrator

revision = 'b2cdde0ea7b5'
down_revision = '82db77ebdf55'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  op.create_table(
      "background_operations",
      sa.Column("id", sa.Integer(), primary_key=True),
      sa.Column("name", sa.String(length=250), nullable=False),
      sa.Column('modified_by_id', sa.Integer(), nullable=True),
      sa.Column('created_at', sa.DateTime()),
      sa.Column('updated_at', sa.DateTime()),
  )
  op.add_column(
      "background_tasks",
      sa.Column("object_type", sa.String(length=250), nullable=True),
  )
  op.add_column(
      "background_tasks",
      sa.Column("object_id", sa.Integer(), nullable=True),
  )
  op.add_column(
      "background_tasks",
      sa.Column("background_operation_id", sa.Integer(), nullable=True),
  )
  op.create_foreign_key(
      "fk_background_operation_id",
      "background_tasks", "background_operations",
      ["background_operation_id"], ["id"],
  )

  connection = op.get_bind()
  migrator_id = migrator.get_migration_user_id(connection)
  connection.execute(
      sa.text("""
          INSERT INTO background_operations(
            `name`, modified_by_id, created_at, updated_at
          )
          SELECT 'generate_children_issues', :migrator_id, now(), now();
      """),
      migrator_id=migrator_id,
  )


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  op.drop_constraint(
      "fk_background_operation_id",
      "background_tasks",
      "foreignkey",
  )
  op.drop_table("background_operations")
  op.drop_column("background_tasks", "object_type")
  op.drop_column("background_tasks", "object_id")
  op.drop_column("background_tasks", "background_operation_id")
