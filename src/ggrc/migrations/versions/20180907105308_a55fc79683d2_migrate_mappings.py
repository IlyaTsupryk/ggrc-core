# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Migrate mappings 'scoping object - regulation', 'scoping object - standards' as created by GGRCQ system

Create Date: 2018-09-07 10:53:08.027454
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op


# revision identifiers, used by Alembic.
revision = 'a55fc79683d2'
down_revision = '82db77ebdf55'

SCOPING_TABLES = (
  'AccessGroup',
  'DataAsset',
  'Facility',
  'Market',
  'Metric',
  'OrgGroup',
  'Product',
  'ProductGroup',
  'Project',
  'TechnologyEnvironment',
  'Vendor',
)

MAPPING_OBJECTS = ('Regulation', 'Standards')


def upgrade():
    """Upgrade database schema and/or data, creating a new revision."""

    sql = """
      UPDATE relationships 
      SET is_external = 1 
      WHERE (source_type IN {} AND destination_type IN {})
      OR (source_type IN {} AND destination_type IN {})
    """.format(
      MAPPING_OBJECTS,
      SCOPING_TABLES,
      SCOPING_TABLES,
      MAPPING_OBJECTS
    )
    op.execute(text(sql))
    

def downgrade():
    """Downgrade database schema and/or data back to the previous revision."""
    pass
    
