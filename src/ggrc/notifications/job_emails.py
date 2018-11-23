# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>


"""  Import/Export notifications """

from urlparse import urljoin

from ggrc import settings
from ggrc import utils
from ggrc.notifications import common

IMPORT_COMPLETED = {
    "title": u"{filename} was imported successfully",
    "body": u"Go to import page to check details or submit new import "
            u"request.",
    "url": u"import"
}

IMPORT_BLOCKED = {
    "title": u"Could not import {filename} due to warnings",
    "body": u"Go to import page to check details or submit new import "
            u"request.",
    "url": u"import"
}

IMPORT_FAILED = {
    "title": u"[WARNING] Could not import {filename} due to errors",
    "body": u"Go to import page to check details or submit new import "
            u"request.",
    "url": u"import"
}

EXPORT_COMPLETED = {
    "title": u"{filename} was exported successfully",
    "body": u"Go to export page to download the result. "
            u"If the file generated for this export request "
            u"has been downloaded, you can ignore the email.",
    "url": u"export"
}

EXPORT_FAILED = {
    "title": (u"[WARNING] Your GGRC export request did not finish due "
              u"to errors"),
    "body": u"Please follow the link to write to sheets or download .csv",
    "url": u"export"
}

EXPORT_CRASHED = {
    "title": (u"[WARNING] Your GGRC export request did not finish due "
              u"to errors"),
    "body": u"Your Export job failed due to a server error. Please "
            u"restart the export again. Sorry for the inconveniences.",
    "url": u"export"
}


def send_email(template, send_to, filename="", ie_id=None):
  """ Send email """
  subject = template["title"].format(filename=filename)

  url = urljoin(utils.get_url_root(), template["url"])
  if ie_id is not None:
    url = "{}#!&job_id={}".format(url, str(ie_id))

  data = {
      "body": template["body"],
      "url": url,
      "title": subject
  }
  body = settings.EMAIL_IMPORT_EXPORT.render(import_export=data)
  common.send_email(send_to, subject, body)
