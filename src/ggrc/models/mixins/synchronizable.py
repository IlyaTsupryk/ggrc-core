# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""A mixin for models that can be synchronized using SyncService."""

from datetime import datetime

from sqlalchemy import orm
from sqlalchemy.orm import validates
from werkzeug import exceptions

from ggrc import db, login
from ggrc.access_control import roleable, role
from ggrc.models import reflection
from ggrc.models.exceptions import ValidationError


class ChangesSynchronized(object):  # pylint: disable=too-few-public-methods
  """Mixin override "updated_at" attribute by removing "onupdate" handler."""
  updated_at = db.Column(
      db.DateTime,
      nullable=False,
      default=lambda: datetime.utcnow().replace(microsecond=0).isoformat()
  )

  @validates('updated_at')
  def validate_updated_at(self, _, value):  # pylint: disable=no-self-use
    """Add explicit non-nullable validation."""
    if not value:
      return datetime.utcnow().replace(microsecond=0).isoformat()

    return value


class AttributesSynchronized(object):  # pylint: disable=too-few-public-methods
  """Mixin that extand "_api_attrs" with additional attributes."""
  _sync_attrs = {
      'id',
      'created_at',
      'updated_at',
  }

  def get_sync_attrs(self):
    """Extend "_api_attrs" with additional attributes."""
    return self._sync_attrs


class Synchronizable(ChangesSynchronized,
                     AttributesSynchronized):
  """Mixin that identifies models that will be used by SyncService."""

  external_id = db.Column(db.Integer, nullable=True, unique=True)

  _api_attrs = reflection.ApiAttributes(
      'external_id',
  )

  @staticmethod
  def _extra_table_args(_):
    return (
        db.UniqueConstraint('external_id', name='uq_external_id'),
    )

  @validates('external_id')
  def validate_external_id(self, _, value):  # pylint: disable=no-self-use
    """Add explicit non-nullable validation."""
    if value is None:
      raise ValidationError("External ID for the object is not specified")

    return value


class RoleableSynchronizable(roleable.Roleable):
  """Overrided Roleable mixin for Synchronizable models.

  It replace access_control_list setter to allow set ACL data in sync
  service format.
  """
  INVALID_ACL_ERROR = "Provided access_control_list data isn't valid."

  @roleable.Roleable.access_control_list.setter
  def access_control_list(self, values):
    """Setter function for access control list.

    Args:
        values: List of access control roles or dicts containing json
          representation of custom attribute values.
    """
    # pylint: disable=not-an-iterable
    if isinstance(values, dict):
      self.validate_acl_data(values)
      email_names = self.parse_sync_service_acl(values)
      from ggrc.utils import user_generator as ug
      existing_people = {
          p.email: p for p in ug.load_people_with_emails(email_names)
      }

      absent_emails = set(email_names) - set(existing_people)
      absent_users = {email: email_names[email] for email in absent_emails}
      new_people = {
          p.email: p for p in ug.create_users_with_role(absent_users)
      }
      all_acl_people = dict(existing_people, **new_people)

      for acl in self._access_control_list:
        users = values.get(acl.ac_role.name, [])
        people = {all_acl_people[user["email"]] for user in users}
        acl.update_people(people)
    else:
      roleable.Roleable.access_control_list.fset(self, values)

  @staticmethod
  def is_sync_service_data(values):
    """Check if received data is in sync service format.

    It should be {<role name>:[{"name": <user name>, "email": <user email>}]}
    """
    if not isinstance(values, dict):
      return False

    for acr, users in values.items():
      if not isinstance(acr, (str, unicode)) or not isinstance(users, list):
        return False

    return True

  @staticmethod
  def parse_sync_service_acl(values):
    """Parse input data and convert it into {<user email>:<user name>} dict.

    Args:
        values(dict): Request data in format
          {<role name>:[{"name": <user name>, "email": <user email>}]}.

    Returns:
        {<user email>:<user name>} dict.
    """
    email_names = {}
    for users in values.values():
      for user in users:
        email_names[user.get("email")] = user.get("name")
    return email_names

  def validate_acl_data(self, acl_request_data):
    """Check correctness of ACL data."""
    if not isinstance(acl_request_data, dict):
      raise exceptions.BadRequest(self.INVALID_ACL_ERROR)

    if acl_request_data:
      obj_roles = role.get_ac_roles_data_for(self.type)
      for acr, users in acl_request_data.items():
        if not isinstance(acr, (str, unicode)) or not isinstance(users, list):
          raise exceptions.BadRequest(self.INVALID_ACL_ERROR)
        if acr not in obj_roles:
          raise exceptions.BadRequest("Role '{}' does not exist".format(acr))
