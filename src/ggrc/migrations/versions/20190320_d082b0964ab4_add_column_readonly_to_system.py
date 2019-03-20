# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Add column readonly to System

Create Date: 2019-03-20 12:50:22.304396
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision = 'd082b0964ab4'
down_revision = '53e115488aec'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  op.add_column(
      "systems",
      sa.Column("readonly", sa.Boolean, nullable=False, default=False)
  )


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
