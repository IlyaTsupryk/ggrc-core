# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Helper methods."""

from flask import _app_ctx_stack

from ggrc.utils import structures


def without_sqlalchemy_cache(func):
  """Switch off SQLAlchemy queries cache filling.

  SQLAlchemy cache all executed queries in
  _app_ctx_stack.top.sqlalchemy_queries variable if DEBUG or
  SQLALCHEMY_RECORD_QUERIES config variable is set to True.
  This decorator make the cache empty everywhere in wrapped function.
  """
  def wrapper(*args, **kwargs):
    """Wrapper function."""
    # Running migration can trigger this decorator, but in such case
    # no top will be there as flask-sqlalchemy haven't created it.
    # For such case just run the function without patching
    # _app_ctx_stack.top.sqlalchemy_queries.
    if not getattr(_app_ctx_stack, "top"):
      return func(*args, **kwargs)

    queries = None
    has_queries = False
    if hasattr(_app_ctx_stack.top, "sqlalchemy_queries"):
      queries = _app_ctx_stack.top.sqlalchemy_queries
      has_queries = True

    _app_ctx_stack.top.sqlalchemy_queries = structures.EmptyList()

    try:
      res = func(*args, **kwargs)
    finally:
      if has_queries:
        _app_ctx_stack.top.sqlalchemy_queries = queries
      else:
        del _app_ctx_stack.top.sqlalchemy_queries
    return res
  return wrapper


def assert_type(obj, expected_type):
  """Check if provided object has proper type."""
  if not isinstance(obj, expected_type):
    raise ValueError(
        "Object of incorrect type '{}' provided. "
        "Should be '{}'".format(type(obj), expected_type)
    )
