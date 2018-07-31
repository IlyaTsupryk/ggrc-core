# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Base handler for document references."""

from ggrc import db
from ggrc.converters import errors
from ggrc.converters.handlers import handlers


class ReferenceHandler(handlers.ColumnHandler):
  """Base class for document documents handlers."""

  def parse_item(self):
    """Parse reference lines.

    Returns:
        list of documents for all URLs and evidences.
    """
    references = []
    if self.raw_value:
      seen_links = set()
      duplicate_links = set()
      for line in self.raw_value.splitlines():
        link = line.strip()
        if not link:
          continue

        if link not in seen_links:
          seen_links.add(link)
          references.append(link)
        else:
          duplicate_links.add(link)

      if duplicate_links:
        # NOTE: We rely on the fact that links in duplicate_inks are all
        # instances of unicode (if that assumption breaks, unicode
        # encode/decode errors can occur for non-ascii link values)
        self.add_warning(errors.DUPLICATE_IN_MULTI_VALUE,
                         column_name=self.display_name,
                         duplicates=u", ".join(sorted(duplicate_links)))

    return references

  def set_obj_attr(self):
    """Set attribute value to object."""
    self.value = self.parse_item()

  def set_value(self):
    """This should be ignored with second class attributes."""

  def remove_relationship(self, relationships, extract_func):
    """Remove relationship if parent == counterparty, return True if removed"""
    parent = self.row_converter.obj
    for rel in relationships:
      if extract_func(rel) == parent:
        db.session.delete(rel)
        return True
    return False
