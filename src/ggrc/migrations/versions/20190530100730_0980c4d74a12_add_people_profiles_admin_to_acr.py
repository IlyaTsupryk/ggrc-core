# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Add people profiles admin to ACR

Create Date: 2019-05-30 10:07:30.365687
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

from alembic import op
from ggrc.migrations import utils
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '0980c4d74a12'
down_revision = '6d7a0c2baba1'


def add_person_profile_admin_acr():
  op.execute("""
    INSERT INTO access_control_roles (
      name, object_type, `read`, `update`, `delete`, created_at, updated_at,
      mandatory, default_to_current_user, non_editable
    )
    VALUES (
      'Admin', 'PersonProfile', '1', '1', '0', NOW(), NOW(),
      '1', '1', '1'
    )
  """)


def get_person_profile_admin_role_id(conn):
  """Return Comment Admin role id"""
  sql = """
      SELECT id FROM access_control_roles
      WHERE object_type='PersonProfile' AND name='Admin'
  """
  return conn.execute(text(sql)).fetchone().id


def load_persons_data(conn):
  """Load all necessary data for migration"""
  sql = """
      SELECT
        people.id AS people_id,
        people_profiles.id AS profile_id
      FROM
        people
      INNER JOIN
          people_profiles
      ON
        people.id=people_profiles.person_id;
      """

  return conn.execute(text(sql)).fetchall()


def create_people_profile_acl(conn, profile_id, ac_role_id):
  """Create new people_profile_acl"""
  sql = """
  INSERT INTO access_control_list(
      object_id, object_type, base_id, ac_role_id, created_at, updated_at
  )
  VALUES (
      :object_id, :object_type, :base_id, :ac_role_id, NOW(), NOW()
  )
  """
  conn.execute(
      text(sql),
      object_id=profile_id,
      object_type='PersonProfile',
      base_id=profile_id,
      ac_role_id=ac_role_id
  )

  acl_id = utils.last_insert_id(conn)
  utils.add_to_objects_without_revisions(conn, acl_id, "AccessControlList")
  return acl_id


def create_people_profile_acp(conn, people_id, ac_list_id):
  """Create new people_profile_acl"""
  sql = """
  INSERT INTO access_control_people(
      person_id, ac_list_id, created_at, updated_at
  )
  VALUES (
      :person_id, :ac_list_id, NOW(), NOW()
  )
  """
  conn.execute(
      text(sql),
      person_id=people_id,
      ac_list_id=ac_list_id
  )


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  conn = op.get_bind()
  add_person_profile_admin_acr()
  admin_role_id = get_person_profile_admin_role_id(conn)
  persons_data = load_persons_data(conn)

  for data in persons_data:
    acl_id = create_people_profile_acl(conn, data.profile_id, admin_role_id)
    create_people_profile_acp(conn, data.people_id, acl_id)


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
