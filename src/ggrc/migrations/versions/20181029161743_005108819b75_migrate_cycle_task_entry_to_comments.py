# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Migrate cycle_task_entry to comments

Create Date: 2018-10-29 16:17:43.979116
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name


from alembic import op
from sqlalchemy import text
from ggrc.migrations import utils
from ggrc.migrations.utils import migrator

revision = '005108819b75'
down_revision = '871aaab0de41'


def load_data(conn):
  """Load all necessary data for migration"""
  sql = """
      SELECT
        cte.id AS cte_id,
        cte.description AS cte_description,
        cte.created_at AS cte_created_at,
        cte.modified_by_id AS cte_modified_by_id,
        cte.updated_at AS cte_updated_at,
        cte.cycle_task_group_object_task_id AS cgot_id,
        IFNULL(GROUP_CONCAT(acl_acr.name SEPARATOR ','),'') AS assignee_type,
        rel_union.id as old_rel_id
      FROM
        cycle_task_entries cte
      JOIN(
        SELECT id, source_id as cgot_id, destination_id as cte_id
        FROM relationships
        WHERE
          source_type='CycleTaskGroupObjectTask' AND
          destination_type='CycleTaskEntry'
        UNION ALL
        SELECT id, source_id as cte_id, destination_id as cgot_id
        FROM relationships
        WHERE
          source_type='CycleTaskEntry' AND
          destination_type = 'CycleTaskGroupObjectTask'
      ) as rel_union
      ON
        rel_union.cgot_id=cte.cycle_task_group_object_task_id AND
        rel_union.cte_id=cte.id
      LEFT OUTER JOIN(
        SELECT
          acl.id,
          acr.name,
          acl.object_type,
          acl.object_id,
          acp.person_id
        FROM
          access_control_list acl
        JOIN access_control_roles acr ON acr.id = acl.ac_role_id
        JOIN access_control_people acp ON acl.id = acp.ac_list_id
        WHERE
        acl.parent_id IS NULL AND
        acl.object_type = 'CycleTaskGroupObjectTask'
      )AS acl_acr
      ON
        acl_acr.object_id = cte.cycle_task_group_object_task_id AND
        acl_acr.person_id = cte.modified_by_id
      GROUP BY cte.id
  """
  return conn.execute(text(sql)).fetchall()


def create_comment(conn, data):
  """Create new comment"""
  sql = """
  INSERT INTO comments(
      description,
      created_at,
      modified_by_id,
      updated_at,
      assignee_type
  )
  VALUES (
      :description, :created_at, :modified_by_id,
      :updated_at, :assignee_type
  )
  """
  conn.execute(
      text(sql),
      description=data.cte_description,
      created_at=data.cte_created_at,
      modified_by_id=data.cte_modified_by_id,
      updated_at=data.cte_updated_at,
      assignee_type=data.assignee_type
  )
  comment_id = utils.last_insert_id(conn)
  utils.add_to_objects_without_revisions(conn, comment_id, "Comment")
  return comment_id


def add_admin_acl(conn, comment_id, user_id, comment_admin_acr_id):
  """Create Comment Admin ACL user_id -> CycleTaskEntry.modified_by_id"""
  sql = """
    INSERT INTO access_control_list(
      ac_role_id,
      object_id,
      object_type,
      created_at,
      updated_at,
      modified_by_id,
      parent_id_nn
    )VALUES(
      :ac_role_id,
      :object_id,
      "Comment",
      NOW(),
      NOW(),
      :modified_by_id,
      0
    )
  """
  conn.execute(
      text(sql),
      ac_role_id=comment_admin_acr_id,
      object_id=comment_id,
      modified_by_id=user_id,
  )
  acl_id = utils.last_insert_id(conn)
  utils.add_to_objects_without_revisions(conn, acl_id, "AccessControlList")
  create_acp(conn, user_id, acl_id)


def create_acp(conn, person_id, ac_list_id):
  """Create acp entry"""
  sql = """
    INSERT INTO access_control_people(
      person_id,
      ac_list_id,
      updated_at,
      created_at
    )VALUES(
      :person_id,
      :ac_list_id,
      NOW(),
      NOW()
    )
  """
  conn.execute(
      text(sql),
      person_id=person_id,
      ac_list_id=ac_list_id
  )


def create_relationship(conn, comment_id, cgot_id, migrator_id):
  """Create relationship between new Comment and CycleTaskGroupObjectTask"""
  sql = """
      INSERT INTO relationships(
          modified_by_id,
          created_at,
          updated_at,
          source_id,
          source_type,
          destination_id,
          destination_type
      ) VALUES (
          :modified_by_id,
          NOW(),
          NOW(),
          :source_id,
          :source_type,
          :destination_id,
          :destination_type
      )
  """
  conn.execute(
      text(sql),
      modified_by_id=migrator_id,
      source_id=comment_id,
      source_type="Comment",
      destination_id=cgot_id,
      destination_type="CycleTaskGroupObjectTask"
  )
  rel_id = utils.last_insert_id(conn)
  utils.add_to_objects_without_revisions(conn, rel_id, "Relationship")


def remove_old_relationship(conn, old_comment_data):
  """Remove old relationships"""
  old_rel_ids = [d.old_rel_id for d in old_comment_data]
  if old_rel_ids:
    conn.execute(
        text("DELETE FROM relationships WHERE id IN :rel_ids"),
        rel_ids=old_rel_ids
    )
    utils.add_to_objects_without_revisions_bulk(
        conn, old_rel_ids, "Relationship", "deleted"
    )


def remove_cycle_task_entries(conn, old_comment_data):
  """Remove CycleTaskEntry data"""
  cte_ids = [d.cte_id for d in old_comment_data]
  if cte_ids:
    conn.execute(
        text("DELETE FROM cycle_task_entries WHERE id IN :cte_ids"),
        cte_ids=cte_ids
    )
    utils.add_to_objects_without_revisions_bulk(
        conn, cte_ids, "CycleTaskEntry", "deleted"
    )


def get_comment_admin_role_id(conn):
  """Return Comment Admin role id"""
  sql = """
      SELECT id FROM access_control_roles
      WHERE object_type='Comment' AND name='Admin'
  """
  return conn.execute(text(sql)).fetchone().id


def run_data_migration():
  """Migration runner"""
  conn = op.get_bind()
  migrator_id = migrator.get_migration_user_id(conn)
  old_comment_data = load_data(conn)
  comment_admin_role_id = get_comment_admin_role_id(conn)
  for data in old_comment_data:
    comment_id = create_comment(conn, data)
    add_admin_acl(
        conn, comment_id, data.cte_modified_by_id, comment_admin_role_id
    )
    create_relationship(conn, comment_id, data.cgot_id, migrator_id)
  remove_old_relationship(conn, old_comment_data)
  remove_cycle_task_entries(conn, old_comment_data)


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  run_data_migration()


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise Exception("Downgrade is not supported.")
