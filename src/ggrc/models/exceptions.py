# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Model-related exceptions and related logic."""

import re
from logging import getLogger

from sqlalchemy.exc import IntegrityError

logger = getLogger(__name__)


def field_lookup(field_string):
  """Find relevant error field for UNIQUE violation in SQL error message."""
  bad_field = 'code'  # assumes this field as a default
  if field_string.startswith('uq_t_'):
    bad_field = 'title'
  elif field_string.endswith('email'):
    bad_field = 'email'
  elif field_string.endswith('title'):
    bad_field = 'title'
  return bad_field


def translate_message(exception):
  """
  Translates db exceptions to something a user can understand.
  """
  message = exception.message

  if isinstance(exception, IntegrityError):
    # TODO: Handle not null, foreign key, uniqueness errors with compound keys
    code, _ = exception.orig.args
    if code == 1062:  # duplicate entry ... for key ...
      pattern = re.compile(r"Duplicate entry ('.*') for key '(.*)'")
      matches = pattern.search(message)
      if matches:
        logger.exception(exception)
        return (u"The value {value} is already used for another {key}. "
                u"{key} values must be unique."
                .format(value=matches.group(1),
                        key=field_lookup(matches.group(2))))
    elif code == 1452:  # cannod set child row: a foreign key constraint fails
      pattern = re.compile(
          r"foreign key constraint fails \(`.+`.`(.+)`, CONSTRAINT `.+` "
          r"FOREIGN KEY \(`.+`\) REFERENCES `(.+)` \(`.+`\)\)"
      )
      matches = pattern.search(message)
      if matches:
        from_, to_ = matches.groups()
        return (u"This request will break a mandatory relationship "
                u"from {from_} to {to_}."
                .format(from_=from_, to_=to_))

  return message


class ValidationError(ValueError):
  pass


class StatusValidationError(ValidationError):
  pass


class ReservedNameError(ValueError):
  pass


class StoppedException(RuntimeError):
  pass
