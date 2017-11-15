# Copyright (C) 2017 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Cleanup unused tables and columns

Create Date: 2017-11-15 13:10:05.443564
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from alembic import op

# revision identifiers, used by Alembic.
revision = '3e667570f21f'
down_revision = '1be0dd01f559'


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  op.drop_column('risk_objects', 'secondary_contact_id')

  op.drop_column('risks', 'url')
  op.drop_column('risks', 'secondary_contact_id')
  op.drop_column('risks', 'reference_url')
  op.drop_column('risks', 'contact_id')

  op.drop_column('threats', 'url')
  op.drop_column('threats', 'secondary_contact_id')
  op.drop_column('threats', 'reference_url')
  op.drop_column('threats', 'contact_id')


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  op.add_column('threats', sa.Column('contact_id', mysql.INTEGER(
      display_width=11), autoincrement=False, nullable=True))
  op.add_column('threats', sa.Column('reference_url', mysql.VARCHAR(
      length=250), nullable=True))
  op.add_column('threats', sa.Column('secondary_contact_id', mysql.INTEGER(
      display_width=11), autoincrement=False, nullable=True))
  op.add_column('threats', sa.Column('url', mysql.VARCHAR(
      length=250), nullable=True))

  op.add_column('risks', sa.Column('contact_id', mysql.INTEGER(
      display_width=11), autoincrement=False, nullable=True))
  op.add_column('risks', sa.Column('reference_url', mysql.VARCHAR(
      length=250), nullable=True))
  op.add_column('risks', sa.Column('secondary_contact_id', mysql.INTEGER(
      display_width=11), autoincrement=False, nullable=True))
  op.add_column('risks', sa.Column('url', mysql.VARCHAR(
      length=250), nullable=True))

  op.add_column('risk_objects', sa.Column(
      'secondary_contact_id', mysql.INTEGER(
          display_width=11), autoincrement=False, nullable=True))
