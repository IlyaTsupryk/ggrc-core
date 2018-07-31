# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Handlers document entries."""

from logging import getLogger
from ggrc import db
from ggrc.models import all_models
from ggrc.converters import errors
from ggrc.converters.handlers import handlers
from ggrc.login import get_current_user_id
from ggrc.converters.handlers.file_handler import FileHandler

logger = getLogger(__name__)


class DocumentReferenceUrlHandler(handlers.ColumnHandler):
  """Base class for document documents handlers."""

  KIND = all_models.Document.REFERENCE_URL

  def get_value(self):
    """Generate a new line separated string for all document links.

    Returns:
      string containing all URLs
    """
    return "\n".join(doc.link for doc in
                     self.row_converter.obj.documents_reference_url)

  def build_document(self, link, user_id):
    """Build document object"""
    document = all_models.Document(
        link=link,
        title=link,
        modified_by_id=user_id,
        context=self.row_converter.obj.context,
        kind=self.KIND,
    )
    document.add_admin_role()
    return document

  def parse_item(self):
    """Parse document link lines.

    Returns:
      list of documents for all URLs and evidences.
    """
    document_links = []
    if self.raw_value:
      seen_links = set()
      duplicate_links = set()
      for line in self.raw_value.splitlines():
        link = line.strip()
        if not link:
          continue

        if link not in seen_links:
          seen_links.add(link)
          document_links.append(link)
        else:
          duplicate_links.add(link)

      if duplicate_links:
        # NOTE: We rely on the fact that links in duplicate_inks are all
        # instances of unicode (if that assumption breaks, unicode
        # encode/decode errors can occur for non-ascii link values)
        self.add_warning(errors.DUPLICATE_IN_MULTI_VALUE,
                         column_name=self.display_name,
                         duplicates=u", ".join(sorted(duplicate_links)))

    return document_links

  def set_obj_attr(self):
    """Set attribute value to object."""
    self.value = self.parse_item()

  def set_value(self):
    """This should be ignored with second class attributes."""

  def _get_old_map(self):
    return {d.link: d for d in self.row_converter.obj.documents_reference_url}

  def remove_relationship(self, relationships, extract_func):
    """Remove relationship if parent == counterparty, return True if removed"""
    parent = self.row_converter.obj
    for rel in relationships:
      if extract_func(rel) == parent:
        db.session.delete(rel)
        return True
    return False

  def insert_object(self):
    """Update document Reference URL values

    This function adds missing URLs and remove existing ones from Documents.
    """
    if self.row_converter.ignore:
      return

    old_link_map = self._get_old_map()

    parent = self.row_converter.obj
    for new_link in self.value:
      if new_link not in old_link_map:
        new_doc = self.build_document(new_link, get_current_user_id())
        db.session.add(new_doc)
        all_models.Relationship(
            source=parent,
            destination=new_doc
        )

    for old_link, old_doc in old_link_map.iteritems():
      if old_link in self.value:
        continue

      if not (self.remove_relationship(old_doc.related_destinations,
                                       lambda x: x.destination) or
              self.remove_relationship(old_doc.related_sources,
                                       lambda x: x.source)):
        logger.warning("Invalid relationship state for document URLs.")


class DocumentFileHandler(FileHandler, handlers.ColumnHandler):
  """Handler for Document File field on document imports."""

  files_object = "documents_file"
  file_error = errors.DISALLOW_DOCUMENT_FILE
