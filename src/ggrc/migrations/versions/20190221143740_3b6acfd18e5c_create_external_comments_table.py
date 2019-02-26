# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""
Create external_comments table

Create Date: 2019-02-21 14:37:40.755061
"""
# disable Invalid constant name pylint warning for mandatory Alembic variables.
# pylint: disable=invalid-name

import sqlalchemy as sa

from alembic import op

from ggrc.migrations import utils
from ggrc.migrations.utils import acr_propagation
from ggrc.migrations.utils import (
    acr_propagation_constants_external_comments as acr_constants
)

revision = '3b6acfd18e5c'
down_revision = 'da49d3baf2ec'


def create_external_comments_table():
  """Create external_comments table"""
  op.create_table(
      'external_comments',
      sa.Column('id', sa.Integer(), nullable=False),
      sa.Column('external_id', sa.Integer(), nullable=True),
      sa.Column('description', sa.Text, nullable=True),
      sa.Column('assignee_type', sa.String(length=250), nullable=False),
      sa.Column('context_id', sa.Integer(), nullable=True),
      sa.Column('created_at', sa.DateTime(), nullable=False),
      sa.Column('updated_at', sa.DateTime(), nullable=False),
      sa.Column('modified_by_id', sa.Integer(), nullable=True),
      sa.Column("external_slug", sa.String(250), nullable=True),

      sa.ForeignKeyConstraint(
          ['context_id'],
          ['contexts.id'],
          name='fk_external_comment_context_id',
      ),
      sa.ForeignKeyConstraint(
          ['modified_by_id'],
          ['people.id'],
          name='fk_external_comment_modified_by_id',
      ),
      sa.PrimaryKeyConstraint('id')
  )
  op.create_index(
      'uq_external_comments_external_id',
      'external_comments',
      ['external_id'],
      unique=True
  )

  op.create_unique_constraint(
      "uq_external_comments_external_slug",
      "external_comments",
      ["external_slug"]
  )


def move_old_comments():
  """Move comments for Control to external comments table."""
  connection = op.get_bind()
  migrator_id = utils.get_migration_user_id(connection)

  connection.execute(
      sa.text("""
          INSERT INTO external_comments(
              id, description, assignee_type, created_at, updated_at,
              modified_by_id
          )
          SELECT id, description, assignee_type, NOW(), NOW(), :migrator_id
          FROM
          (
              SELECT c.id, c.description, c.assignee_type
              FROM comments c
              JOIN relationships r ON r.source_type = 'Comment' AND
                  r.source_id = c.id AND
                  r.destination_type = 'Control'

              UNION

              SELECT c.id, c.description, c.assignee_type
              FROM comments c
              JOIN relationships r ON r.destination_type = 'Comment' AND
                  r.destination_id = c.id AND
                  r.source_type = 'Control'
          ) tmp;
      """),
      migrator_id=migrator_id
  )


def delete_control_comments():
  """Delete comments for all controls."""
  op.execute("""
      DELETE comments
      FROM comments
      JOIN relationships r ON r.source_type = 'Comment' AND
          r.source_id = comments.id AND
          r.destination_type = 'Control';
  """)
  op.execute("""
      DELETE comments
      FROM comments
      JOIN relationships r ON r.destination_type = 'Comment' AND
          r.destination_id = comments.id AND
          r.source_type = 'Control';
  """)


def update_comment_relationships():
  """Replace 'Comment' object_type with 'ExternalComment' for relationships."""
  connection = op.get_bind()
  old_rels = connection.execute("""
      SELECT id, source_type, source_id, destination_type, destination_id
      FROM relationships
      WHERE (source_type = 'Comment' AND destination_type = 'Control') OR
            (destination_type = 'Comment' AND source_type = 'Control');
    """).fetchall()
  if old_rels:
    migrator_id = utils.get_migration_user_id(connection)
    for _, s_type, s_id, d_type, d_id in old_rels:
      connection.execute(
          sa.text("""
              INSERT INTO relationships(
                source_type, source_id, destination_type, destination_id,
                modified_by_id, created_at, updated_at, is_external
              )
              VALUES(
                :source_type, :source_id, :dest_type, :dest_id,
                :modified_by_id, NOW(), NOW(), TRUE
              );
          """),
          source_type='ExternalComment' if s_type == 'Comment' else s_type,
          source_id=s_id,
          dest_type='ExternalComment' if d_type == 'Comment' else d_type,
          dest_id=d_id,
          modified_by_id=migrator_id,
      )

    new_rels = connection.execute("""
        SELECT id
        FROM relationships
        WHERE source_type = 'ExternalComment' OR
              destination_type = 'ExternalComment';
    """).fetchall()

    new_rel_ids = [rel.id for rel in new_rels]
    utils.add_to_objects_without_revisions_bulk(
        connection,
        new_rel_ids,
        "Relationship",
    )

    old_rel_ids = [rel.id for rel in old_rels]
    connection.execute(
        sa.text("""
            DELETE FROM relationships
            WHERE id IN :relationship_ids;
        """),
        relationship_ids=old_rel_ids,
    )
    utils.add_to_objects_without_revisions_bulk(
        connection,
        old_rel_ids,
        "Relationship",
        action="deleted",
    )


def create_external_comments_revisions():
  """Create revisions for external comments."""
  connection = op.get_bind()
  result = connection.execute("""
      SELECT id
      FROM external_comments;
  """).fetchall()
  if result:
    result = [i[0] for i in result]
    utils.add_to_objects_without_revisions_bulk(
        connection,
        result,
        "ExternalComment"
    )


def create_comments_revisions():
  """Create delete revisions for comments."""
  connection = op.get_bind()
  result = connection.execute("""
      SELECT id
      FROM external_comments;
  """).fetchall()
  if result:
    result = [i[0] for i in result]
    utils.add_to_objects_without_revisions_bulk(
        connection,
        result,
        "Comment",
        action="deleted",
    )


def propagate_acr():
  """Create propagation system ACRs for KeyReport model"""
  acr_propagation.propagate_roles(
      acr_constants.CONTROL_PROPAGATION_RULE,
      with_update=True
  )


def upgrade():
  """Upgrade database schema and/or data, creating a new revision."""
  create_external_comments_table()
  move_old_comments()
  delete_control_comments()
  update_comment_relationships()
  create_comments_revisions()
  create_external_comments_revisions()
  propagate_acr()


def downgrade():
  """Downgrade database schema and/or data back to the previous revision."""
  raise NotImplementedError("Downgrade is not supported")
