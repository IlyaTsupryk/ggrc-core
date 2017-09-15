# Copyright (C) 2017 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Common logic for hooks."""

import sqlalchemy as sa

from ggrc import db
from ggrc.models import all_models
from ggrc.utils import referenced_objects


def ensure_field_not_changed(obj, field_name):
  field_history = sa.inspect(obj).attrs[field_name].history
  if field_history.added or field_history.deleted:
    raise ValueError("{} field should not be changed".format(field_name))


def map_objects(src, dst):
  """Creates a relationship between an src and dst. This also
  generates automappings. Fails silently if dst dict does not have id and type
  keys.

  Args:
    src (model): The src model
    dst (dict): A dict with `id` and `type`.
  Returns:
    None
  """
  if not dst:
    return
  if 'id' not in dst or 'type' not in dst:
    return

  destination = referenced_objects.get(dst["type"], dst["id"])
  if not destination:
    raise ValueError("No {} with id {} found."
                     .format(dst["type"], dst["id"]))
  db.session.add(all_models.Relationship(
      source=src,
      destination=destination,
      context_id=src.context_id,
  ))
