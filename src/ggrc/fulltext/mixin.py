# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Module contains Indexed mixin class"""
import itertools
from collections import namedtuple

from sqlalchemy import orm

from ggrc import db, utils

from ggrc import fulltext


class ReindexRule(namedtuple("ReindexRule", ["model", "rule", "fields"])):
  """Class for keeping reindex rules"""
  __slots__ = ()

  def __new__(cls, model, rule, fields=None):
    return super(ReindexRule, cls).__new__(cls, model, rule, fields)


# pylint: disable=too-few-public-methods
class Indexed(object):
  """Mixin for Index And auto reindex current model instance.

  It should be last mixin in the scope if mixin that generate indexed query.
  """

  AUTO_REINDEX_RULES = [
      # Usage: ReindexRule("ModelName", lambda x: x.value)
  ]
  REQUIRED_GLOBAL_REINDEX = True

  PROPERTY_TEMPLATE = u"{}"

  INSERT_CHUNK_SIZE = 3000

  def get_reindex_pair(self):
    return (self.__class__.__name__, self.id)

  @classmethod
  def get_insert_values(cls, ids):
    """Return values that should be inserted into fulltext table."""
    if not ids:
      return None
    instances = cls.indexed_query().filter(cls.id.in_(ids))
    indexer = fulltext.get_indexer()
    rows = itertools.chain(*[indexer.records_generator(i) for i in instances])
    return list(rows) or None

  @classmethod
  def get_delete_query_for(cls, ids):
    """Return delete class record query. If ids are empty, will return None."""
    if not ids:
      return None
    indexer = fulltext.get_indexer()
    return indexer.record_type.__table__.delete().where(
        indexer.record_type.type == cls.__name__
    ).where(
        indexer.record_type.key.in_(ids),
    )

  @classmethod
  def insert_index_data(cls, values):
    """Insert provided values into fulltext table."""
    if not values:
      return

    inserter = fulltext.get_indexer().record_type.__table__.insert()
    for val in utils.list_chunks(list(values), cls.INSERT_CHUNK_SIZE):
      db.session.execute(inserter.values(val))

  @classmethod
  def bulk_record_update_for(cls, ids):
    """Bulky update index records for current class"""
    delete_query = cls.get_delete_query_for(ids)
    if delete_query:
      db.session.execute(delete_query)

    insert_values = cls.get_insert_values(ids)
    cls.insert_index_data(insert_values)

  @classmethod
  def indexed_query(cls):
    return cls.query.options(orm.Load(cls).load_only("id"),)
