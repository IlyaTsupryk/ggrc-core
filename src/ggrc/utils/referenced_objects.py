# Copyright (C) 2017 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Util to get objects from flask.g.referenced_objects or DB if not present."""

import flask

from ggrc import db
from ggrc.models import inflector


def get(type_, id_):
  """Check flask.g.referenced_objects for the object or get it from the DB."""
  if not id_:
    return None

  ref_objects = getattr(flask.g, "referenced_objects", {})

  if not (isinstance(type_, type) and issubclass(type_, db.Model)):
    type_ = inflector.get_model(type_)

  result = ref_objects.get(type_, {}).get(id_, None)

  if not result:
    result = type_.query.get(id_)

  return result
