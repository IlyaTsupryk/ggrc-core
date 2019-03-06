# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Base objects for csv file converters."""

from collections import defaultdict

from flask import g
from google.appengine.ext import deferred

from ggrc import login
from ggrc import settings
from ggrc.utils import benchmark
from ggrc.utils import structures
from ggrc.cache.utils import clear_memcache
from ggrc.converters import get_exportables
from ggrc.converters import import_helper
from ggrc.converters import base_block
from ggrc.converters.snapshot_block import SnapshotBlockConverter
from ggrc.converters.import_helper import extract_relevant_data
from ggrc.converters.import_helper import split_blocks
from ggrc.converters.import_helper import CsvStringBuilder
from ggrc.fulltext import get_indexer


class BaseConverter(object):
  """Base class for csv converters."""
  # pylint: disable=too-few-public-methods
  def __init__(self):
    self.new_objects = defaultdict(structures.CaseInsensitiveDict)
    self.shared_state = {}
    self.response_data = []
    self.exportable = get_exportables()

  def get_info(self):
    raise NotImplementedError()


class ImportConverter(BaseConverter):
  """Import Converter.

  This class contains and handles all block converters and makes sure that
  blocks and columns are handled in the correct order.
  """

  priority_columns = [
      "email",
      "slug",
      "delete",
      "task_type",
      "audit",
      "assessment_template",
      "title",
      "status",
  ]

  def __init__(self, ie_job, dry_run=True, csv_data=None):
    self.user = getattr(g, '_current_user', None)
    self.ie_job = ie_job
    self.dry_run = dry_run
    self.csv_data = csv_data or []
    self.indexer = get_indexer()
    super(ImportConverter, self).__init__()

  def get_info(self):
    return self.response_data

  def initialize_block_converters(self):
    """Initialize block converters."""
    offsets_and_data_blocks = split_blocks(self.csv_data)
    for offset, data, csv_lines in offsets_and_data_blocks:
      class_name = data[1][0].strip().lower()
      object_class = self.exportable.get(class_name)
      raw_headers, rows = extract_relevant_data(data)
      block_converter = base_block.ImportBlockConverter(
          self,
          object_class=object_class,
          rows=rows,
          raw_headers=raw_headers,
          offset=offset,
          class_name=class_name,
          csv_lines=csv_lines[2:],  # Skip 2 header lines
      )
      block_converter.check_block_restrictions()
      yield block_converter

  def import_csv_data(self):
    """Process import and post import jobs."""

    revision_ids = []
    for converter in self.initialize_block_converters():
      if not converter.ignore:
        converter.import_csv_data()
        revision_ids.extend(converter.revision_ids)
      self.response_data.append(converter.get_info())
    self._start_compute_attributes_job(revision_ids)
    if not self.dry_run and settings.ISSUE_TRACKER_ENABLED:
      self._start_issuetracker_update(revision_ids)
    self.drop_cache()

  def _start_issuetracker_update(self, revision_ids):
    """Create or update issuetracker tickets for all imported instances."""

    arg_list = {"revision_ids": revision_ids}

    filename = getattr(self.ie_job, "title", '')
    user_email = getattr(self.user, "email", '')
    mail_data = {
        "filename": filename,
        "user_email": user_email,
    }

    arg_list["mail_data"] = mail_data

    from ggrc import views
    views.background_update_issues(parameters=arg_list)

  def _start_compute_attributes_job(self, revision_ids):
    if revision_ids:
      cur_user = login.get_current_user()
      deferred.defer(
          import_helper.calculate_computed_attributes,
          revision_ids,
          cur_user.id
      )

  @classmethod
  def drop_cache(cls):
    clear_memcache()


class ExportConverter(BaseConverter):
  """Export Converter.

  This class contains and handles all block converters and makes sure that
  blocks and columns are handled in the correct order.
  """

  def __init__(self, ids_by_type, exportable_queries=None):
    super(ExportConverter, self).__init__()
    self.dry_run = True  # TODO: fix ColumnHandler to not use it for exports
    self.block_converters = []
    self.ids_by_type = ids_by_type
    self.exportable_queries = exportable_queries or []

  def get_object_names(self):
    return [c.name for c in self.block_converters]

  def get_info(self):
    for converter in self.block_converters:
      self.response_data.append(converter.get_info())
    return self.response_data

  def initialize_block_converters(self):
    """Generate block converters.

    Generate block converters from a list of tuples with an object name and
    ids and store it to an instance variable.
    """
    object_map = {o.__name__: o for o in self.exportable.values()}
    exportable_queries = self._get_exportable_queries()
    for object_data in exportable_queries:
      class_name = object_data["object_name"]
      object_class = object_map[class_name]
      object_ids = object_data.get("ids", [])
      fields = object_data.get("fields", "all")
      if class_name == "Snapshot":
        self.block_converters.append(
            SnapshotBlockConverter(self, object_ids, fields=fields)
        )
      else:
        block_converter = base_block.ExportBlockConverter(
            self,
            object_class=object_class,
            fields=fields,
            object_ids=object_ids,
            class_name=class_name,
        )
        self.block_converters.append(block_converter)

  def export_csv_data(self):
    """Export csv data."""
    with benchmark("Initialize block converters."):
      self.initialize_block_converters()
    with benchmark("Build csv data."):
      try:
        return self.build_csv_from_row_data()
      except ValueError:
        return ""

  def build_csv_from_row_data(self):
    """Export each block separated by empty lines."""
    table_width = max([converter.block_width
                       for converter in self.block_converters])
    table_width += 1  # One line for 'Object line' column

    csv_string_builder = CsvStringBuilder(table_width)
    for block_converter in self.block_converters:
      with benchmark("Generate export file header"):
        csv_header = block_converter.generate_csv_header()
        csv_header[0].insert(0, "Object type")
        csv_header[1].insert(0, block_converter.name)

        csv_string_builder.append_line(csv_header[0])
        csv_string_builder.append_line(csv_header[1])

      for line in block_converter.generate_row_data():
        line.insert(0, "")
        csv_string_builder.append_line(line)

      csv_string_builder.append_line([])
      csv_string_builder.append_line([])

    return csv_string_builder.get_csv_string()

  def _get_exportable_queries(self):
    """Get a list of filtered object queries regarding exportable items.

    self.ids_by_type should contain a list of object queries.

    self.exportable_queries should contain indexes of exportable queries
    regarding self.ids_by_type

    Returns:
      list of dicts: filtered object queries regarding self.exportable_queries
    """
    if self.exportable_queries:
      queries = [
          object_query
          for index, object_query in enumerate(self.ids_by_type)
          if index in self.exportable_queries
      ]
    else:
      queries = self.ids_by_type
    return queries
