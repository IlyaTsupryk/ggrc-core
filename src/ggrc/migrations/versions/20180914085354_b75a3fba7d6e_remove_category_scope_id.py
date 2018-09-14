# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Remove category scope_id

Create Date: 2018-09-14 08:53:54.623933
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from alembic import op

# revision identifiers, used by Alembic.
revision = 'b75a3fba7d6e'
down_revision = 'a55fc79683d2'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  op.drop_column('categories', 'scope_id')


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  op.add_column(
      'categories',
      sa.Column(
          'scope_id',
          mysql.INTEGER(display_width=11),
          autoincrement=False,
          nullable=True
      )
  )
