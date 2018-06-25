# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Handlers for access control roles."""

from ggrc import models, db
from ggrc.converters.handlers import handlers


class AccessControlRoleColumnHandler(handlers.UsersColumnHandler):
  """Handler for access control roles."""

  def __init__(self, row_converter, key, **options):
    super(AccessControlRoleColumnHandler, self).__init__(
        row_converter, key, **options)
    self.role = models.AccessControlRole.query.filter_by(
        name=(options.get("attr_name") or self.display_name),
        object_type=self.row_converter.obj.type
    ).one()

  def _add_people(self, people_list):
    """Add people to AC list with the current role."""
    for person in people_list:
      models.AccessControlList(
          object=self.row_converter.obj,
          person=person,
          ac_role=self.role
      )

  def _remove_people(self, people_list):
    """Remove people from AC list with the current role."""
    acl_email_map = {
        acl.person.email: acl
        for acl in self.row_converter.obj.access_control_list
        if acl.ac_role == self.role
    }
    for person in people_list:
      acl = acl_email_map[person.email]
      self.row_converter.obj.access_control_list.remove(acl)
      db.session.delete(acl)

  def set_obj_attr(self):
    """Update current AC list with correct people values."""
    value_is_correct = self.value or self.set_empty
    if not value_is_correct:
      return
    list_old = {
        acl.person
        for acl in self.row_converter.obj.access_control_list
        if acl.ac_role == self.role
    }
    if self.set_empty:
      self._remove_people(list_old)
      return
    list_new = set(self.value)
    self._add_people(list_new - list_old)
    self._remove_people(list_old - list_new)

  def get_value(self):
    """Get list of emails for people with the current AC role."""
    people = sorted(
        acl.person.email
        for acl in self.row_converter.obj.access_control_list
        if acl.ac_role == self.role
    )
    return "\n".join(people)
