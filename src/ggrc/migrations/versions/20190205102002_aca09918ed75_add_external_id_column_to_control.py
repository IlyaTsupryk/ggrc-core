# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Add external_id column to Control

Create Date: 2019-02-05 10:20:02.219497
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision = 'aca09918ed75'
down_revision = '0472c1760a69'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  op.add_column(
      'controls',
      sa.Column('external_id', sa.Integer, autoincrement=False, nullable=True),
  )
  op.create_index('uq_external_id', 'controls', ['external_id'], unique=True)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError()
