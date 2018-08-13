# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Unit test suite for reindex functionality."""

import ddt

from mock import patch

from ggrc import db
from ggrc import fulltext
from ggrc.models import all_models
from integration.ggrc import TestCase
from integration.ggrc.models import factories


@ddt.ddt
class TestFulltext(TestCase):
  """Tests for basic functionality of reindex."""

  def setUp(self):
    """Setup method."""
    super(TestFulltext, self).setUp()

  @ddt.data(
      (0, 1),
      (1, 3),
      (3, 1),
      (3, 5),
  )
  @ddt.unpack
  def test_bulk_record_update(self, obj_count, chunk_size):
    """Test correctness of bulk reindex update."""
    with factories.single_commit():
      control_ids = [factories.ControlFactory().id for _ in range(obj_count)]

    with patch("ggrc.fulltext.mixin.Indexed.INSERT_CHUNK_SIZE", chunk_size):
      all_models.Control.bulk_record_update_for(control_ids)
    db.session.plain_commit()

    indexer = fulltext.get_indexer()
    indexed_titles = indexer.record_type.query.filter(
        fulltext.mysql.MysqlRecordProperty.type == "Control",
        fulltext.mysql.MysqlRecordProperty.property == "title",
    )
    self.assertEqual(indexed_titles.count(), obj_count)
