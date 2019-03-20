# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Contains a WithReadOnlyAccess mixin.

It allows to mark objects as read-only
"""

from ggrc import db
from ggrc.models import reflection


class WithReadOnlyAccess(object):
  """Mixin for models which can be marked as read-only"""
  # pylint: disable=too-few-public-methods

  readonly = db.Column(db.Boolean, nullable=False, default=False)

  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute("readonly", create=False, update=False),
  )

  _aliases = {
      "readonly": {
          "display_name": "Read-only",
          "mandatory": False,
      },
  }
