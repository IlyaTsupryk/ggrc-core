# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Add Option fields as strings to Control

Create Date: 2019-01-31 12:36:15.627087
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op

from ggrc.migrations import utils


# revision identifiers, used by Alembic.
revision = '49e1b804c32f'
down_revision = 'aca09918ed75'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  op.add_column("controls", sa.Column("kind", sa.String(250), nullable=True))
  op.add_column("controls", sa.Column("means", sa.String(250), nullable=True))
  op.add_column(
      "controls",
      sa.Column("verify_frequency", sa.String(250), nullable=True)
  )

  op.execute("""
      UPDATE controls c
      JOIN options o ON o.id = c.kind_id AND o.role = 'control_kind'
      SET c.kind = o.title;
  """)
  op.execute("""
      UPDATE controls c
      JOIN options o ON o.id = c.means_id AND o.role = 'control_means'
      SET c.means = o.title;
  """)
  op.execute("""
      UPDATE controls c
      JOIN options o ON o.id = c.verify_frequency_id AND
          o.role = 'verify_frequency'
      SET c.verify_frequency = o.title;
  """)

  op.drop_column("controls", "kind_id")
  op.drop_column("controls", "means_id")
  op.drop_column("controls", "verify_frequency_id")

  connection = op.get_bind()
  result = connection.execute("""
      SELECT id
      FROM options
      WHERE role IN ('control_kind', 'control_means', 'verify_frequency');
  """)
  objects = result.fetchall()
  objects_ids = [o.id for o in objects]
  if objects_ids:
    utils.add_to_objects_without_revisions_bulk(
        connection,
        objects_ids,
        "Option",
        action='deleted',
    )

    op.execute("""
        DELETE FROM options
        WHERE role IN ('control_kind', 'control_means', 'verify_frequency');
    """)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
