# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for person's profile object"""

from datetime import datetime, timedelta

from ggrc import db
from ggrc.models.mixins import base
from ggrc.models import reflection
from ggrc.access_control.roleable import Roleable

# Offset for default last seen what's new date in days
DEFAULT_LAST_SEEN_OFFSET = 60


def default_last_seen_date():
  """Function counts last_seen_whats_new date for new users"""
  now = datetime.utcnow()
  return now.replace(microsecond=0) - timedelta(DEFAULT_LAST_SEEN_OFFSET)


# pylint: disable=too-few-public-methods
class PersonProfile(Roleable, base.ContextRBAC, base.Base, db.Model):
  """Class represents person's profile.

  Profile keeps user's preferences and local user settings such as
  "last seen what's" new date"""

  __tablename__ = 'people_profiles'

  _api_attrs = reflection.ApiAttributes(
      'send_calendar_events',
      'last_seen_whats_new',
  )

  person_id = db.Column(db.Integer,
                        db.ForeignKey('people.id', ondelete='CASCADE'),
                        unique=True)

  last_seen_whats_new = db.Column(db.DateTime, default=default_last_seen_date)

  send_calendar_events = db.Column(db.Boolean, default=True)
