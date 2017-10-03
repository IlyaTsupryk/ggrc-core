# Copyright (C) 2017 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Map Regulation and Objective to Assessment

This migration should be run on production only as temporary solution

Create Date: 2017-10-03 09:55:58.059694
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name
from alembic import op

from sqlalchemy import text

revision = '8f98792ead6'
down_revision = '434683ceff87'

# This id was provided by customer. To run migration for other Audit,
# replace it to proper audit id
AUDIT_ID = 80


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  query = text("""
      CREATE TEMPORARY TABLE temp_control_snapshots (
        snapshot_id int(11),
        assessment_id int(11)
      );

      INSERT INTO temp_control_snapshots(snapshot_id, assessment_id)
      SELECT snap_id, asmnt_id
      FROM (
        SELECT r.destination_id AS snap_id, s.parent_id as asmnt_id
        FROM relationships r
        JOIN assessments a ON a.id = r.source_id
        JOIN snapshots s ON s.id = r.destination_id
        WHERE r.source_type = 'Assessment' AND
              r.destination_type = 'Snapshot' AND
              a.audit_id = :audit_id AND
              s.child_type = 'Control'
        UNION ALL
        SELECT r.source_id, s.parent_id
        FROM relationships r
        JOIN assessments a ON a.id = r.destination_id
        JOIN snapshots s ON s.id = r.source_id
        WHERE r.destination_type = 'Assessment' AND
              r.source_type = 'Snapshot' AND
              a.audit_id = :audit_id AND
              s.child_type = 'Control'
      ) tmp;

      INSERT INTO relationships(
        created_at, updated_at, source_id, source_type,
        destination_id, destination_type
      )
      SELECT now(), now(), tcs.assessment_id, 'Assessment',
        tmp.mapped_id, 'Snapshot'
      FROM
      (
        SELECT r.source_id AS control_snap_id, r.destination_id AS mapped_id
        FROM relationships r
        JOIN snapshots s ON s.id = r.destination_id
        WHERE r.source_type = 'Snapshot' AND
            r.destination_type = 'Snapshot' AND
            s.child_type IN ('Regulation', 'Objective')
        UNION
        SELECT r.destination_id, r.source_id
        FROM relationships r
        JOIN snapshots s ON s.id = r.source_id
        WHERE r.source_type = 'Snapshot' AND
            r.destination_type = 'Snapshot' AND
            s.child_type IN ('Regulation', 'Objective')
      ) tmp
      JOIN temp_control_snapshots tcs ON tcs.snapshot_id = tmp.control_snap_id;

      DROP TABLE temp_control_snapshots;
  """)

  connection = op.get_bind()
  connection.execute(query, audit_id=AUDIT_ID)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  pass
