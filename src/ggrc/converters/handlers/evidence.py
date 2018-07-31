# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Handlers evidence entries."""

from logging import getLogger
from ggrc import db
from ggrc.models import all_models
from ggrc.converters import errors
from ggrc.converters.handlers import handlers
from ggrc.login import get_current_user_id
from ggrc.converters.handlers.file_handler import FileHandler


logger = getLogger(__name__)


class EvidenceUrlHandler(handlers.ColumnHandler):
  """Handler for Evidence URL field on evidence imports."""

  KIND = all_models.Evidence.URL

  def _get_old_map(self):
    return {d.link: d for d in self.row_converter.obj.evidences_url}

  def get_value(self):
    """Generate a new line separated string for all document links.

    Returns:
      string containing all URLs
    """
    return "\n".join(doc.link for doc in self.row_converter.obj.evidences_url)

  def build_evidence(self, link, user_id):
    """Build evidence object"""
    evidence = all_models.Evidence(
        link=link,
        title=link,
        modified_by_id=user_id,
        context=self.row_converter.obj.context,
        kind=self.KIND,
    )
    evidence.add_admin_role()
    return evidence

  def parse_item(self):
    """Parse evidence link lines.

    Returns:
      list of evidences for all URLs and evidences.
    """
    evidence_links = []
    if self.raw_value:
      seen_links = set()
      duplicate_links = set()

      for line in self.raw_value.splitlines():
        link = line.strip()
        if not link:
          continue

        if link not in seen_links:
          seen_links.add(link)
          evidence_links.append(link)
        else:
          duplicate_links.add(link)

      if duplicate_links:
        # NOTE: We rely on the fact that links in duplicate_links are all
        # instances of unicode (if that assumption breaks,
        # unicode encode/decode errors can occur for non-ascii link values)
        self.add_warning(errors.DUPLICATE_IN_MULTI_VALUE,
                         column_name=self.display_name,
                         duplicates=u", ".join(sorted(duplicate_links)))

    return evidence_links

  def set_obj_attr(self):
    """Set attribute value to object."""
    self.value = self.parse_item()

  def set_value(self):
    """This should be ignored with second class attributes."""

  def insert_object(self):
    """Update document URL values

    This function adds missing URLs and remove existing ones from Documents.
    The existing URLs with new titles just change the title.
    """
    if self.row_converter.ignore:
      return
    old_link_map = self._get_old_map()

    for new_link in self.value:
      if new_link not in old_link_map:
        new_evidence = self.build_evidence(new_link, get_current_user_id())
        db.session.add(new_evidence)
        all_models.Relationship(source=self.row_converter.obj,
                                destination=new_evidence)

    for old_link, old_evidence in old_link_map.iteritems():
      if old_link in self.value:
        continue
      if old_evidence.related_destinations:
        old_evidence.related_destinations.pop()
      elif old_evidence.related_sources:
        old_evidence.related_sources.pop()
      else:
        logger.warning("Invalid relationship state for document URLs.")


class EvidenceFileHandler(FileHandler, handlers.ColumnHandler):
  """Handler for evidence of type file on evidence imports."""

  files_object = "evidences_file"
  file_error = errors.DISALLOW_EVIDENCE_FILE
