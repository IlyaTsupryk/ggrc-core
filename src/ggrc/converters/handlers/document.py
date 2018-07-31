# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Handlers document entries."""

from logging import getLogger
from ggrc import db
from ggrc.converters.handlers import reference
from ggrc.models import all_models
from ggrc.converters import errors
from ggrc.converters.handlers import handlers
from ggrc.login import get_current_user_id
from ggrc.converters.handlers.file_handler import FileHandler

logger = getLogger(__name__)


class DocumentReferenceUrlHandler(reference.ReferenceHandler):
  """Base class for document documents handlers."""

  KIND = all_models.Document.REFERENCE_URL

  def get_value(self):
    """Generate a new line separated string for all document links.

    Returns:
      string containing all URLs
    """
    return "\n".join(doc.link for doc in
                     self.row_converter.obj.documents_reference_url)

  def _get_old_map(self):
    return {d.link: d for d in self.row_converter.obj.documents_reference_url}

  def build_document(self, link, user_id):
    """Build document object."""
    document = all_models.Document(
        link=link,
        title=link,
        modified_by_id=user_id,
        context=self.row_converter.obj.context,
        kind=self.KIND,
    )
    document.add_admin_role()
    return document

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
