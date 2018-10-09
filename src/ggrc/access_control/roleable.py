# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Roleable model"""
from collections import defaultdict
from sqlalchemy import and_
from sqlalchemy import orm
from sqlalchemy.orm import remote
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.hybrid import hybrid_property

from ggrc import db
from ggrc.access_control.list import AccessControlList
from ggrc.access_control import role
from ggrc.fulltext.attributes import CustomRoleAttr
from ggrc.models import reflection
from ggrc.utils.referenced_objects import get


class Roleable(object):
  """Roleable Mixin

  Mixin that adds access_control_list property to the parent object. Access
  control list includes a list of AccessControlList objects.
  """

  _update_raw = _include_links = ['access_control_list', ]
  _fulltext_attrs = [CustomRoleAttr('access_control_list'), ]
  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute('access_control_list', True, True, True))
  MAX_ASSIGNEE_NUM = 1
  MAX_VERIFIER_NUM = 1

  @declared_attr
  def _access_control_list(cls):  # pylint: disable=no-self-argument
    """access_control_list"""
    return db.relationship(
        'AccessControlList',
        primaryjoin=lambda: and_(
            remote(AccessControlList.object_id) == cls.id,
            remote(AccessControlList.object_type) == cls.__name__,
            remote(AccessControlList.parent_id_nn) == 0
        ),
        foreign_keys='AccessControlList.object_id',
        backref='{0}_object'.format(cls.__name__),
        cascade='all, delete-orphan')

  @hybrid_property
  def access_control_list(self):
    return self._access_control_list

  @access_control_list.setter
  def access_control_list(self, values):
    """Setter function for access control list.

    Args:
        values: List of access control roles or dicts containing json
        representation of custom attribute values.
    """
    if values is None:
      return

    new_values = self._parse_values(values)
    old_values = self._get_old_values()
    self._remove_values(old_values - new_values)
    self._add_values(new_values - old_values)

  def extend_access_control_list(self, values):
    """Extend access control list.

    Args:
        values: List of access control roles or dicts containing json
        representation of custom attribute values.
    """
    if values is None:
      return

    new_values = self._parse_values(values)
    old_values = self._get_old_values()
    self._add_values(new_values - old_values)

  def _get_old_values(self):
    """Return Set of tuples (Role, Person)"""
    return {(acl.ac_role, acl.person) for acl in self.access_control_list}

  @staticmethod
  def _parse_values(values):
    """ Parse list of (ac_role, user) in form of:
    e.g
    [{
        "ac_role_id": admin_role_id,
        "person": {
            "id": user_id
        }
    }]
    or
    [{
        "ac_role": AccessControlRole(),
        "person": Person()
    }]

    Return set of tuples(AccessControlRole, Person)"""

    result = set()
    for value in values:
      if ("ac_role_id" in value and
              "person" in value and "id" in value["person"]):
        result.add((get("AccessControlRole", value["ac_role_id"]),
                    get("Person", value["person"]["id"])))
      elif "ac_role" in value and "person" in value:
        result.add((value["ac_role"], value["person"]))
      else:
        raise ValueError("Unknown values format")

    return result

  def _add_values(self, values):
    """Attach new custom role values to current object."""
    for ac_role, person in values:
      AccessControlList(
          object=self,
          person=person,
          ac_role=ac_role
      )

  def _remove_values(self, values):
    """Remove custom role values from current object."""
    val_map = {(acl.ac_role, acl.person): acl
               for acl in self.access_control_list}
    for value in values:
      self._access_control_list.remove(val_map[value])

  @classmethod
  def eager_query(cls):
    """Eager Query"""
    query = super(Roleable, cls).eager_query()
    return cls.eager_inclusions(
        query,
        Roleable._include_links
    ).options(
        orm.subqueryload(
            '_access_control_list'
        ).joinedload(
            "person"
        ).undefer_group(
            'Person_complete'
        ),
        orm.subqueryload(
            '_access_control_list'
        ).joinedload(
            "person"
        ).subqueryload(
            "contexts"
        ).undefer_group(
            'Context_complete'
        ),
        orm.subqueryload(
            '_access_control_list'
        ).joinedload(
            "ac_role"
        ).undefer_group(
            'AccessControlRole_complete'
        ),
    )

  @classmethod
  def indexed_query(cls):
    """Query used by the indexer"""
    query = super(Roleable, cls).indexed_query()
    return query.options(
        orm.subqueryload(
            '_access_control_list'
        ).joinedload(
            "person"
        ).load_only(
            "id", "name", "email"
        ),
        orm.subqueryload(
            '_access_control_list'
        ).joinedload(
            "ac_role"
        ).load_only(
            "id", "name", "object_type", "internal"
        ),
    )

  def log_json(self):
    """Log custom attribute values."""
    # pylint: disable=not-an-iterable
    res = super(Roleable, self).log_json()
    res["access_control_list"] = [
        value.log_json() for value in self.access_control_list]
    return res

  def get_persons_for_rolename(self, role_name):
    """Return list of persons that are valid for send role_name."""
    for role_id, name in role.get_custom_roles_for(self.type).iteritems():
      if name != role_name:
        continue
      return [i.person for i in self.access_control_list
              if i.ac_role_id == role_id]
    return []

  def get_person_ids_for_rolename(self, role_name):
    """Return list of persons that are valid for send role_name."""
    for role_id, name in role.get_custom_roles_for(self.type).iteritems():
      if name != role_name:
        continue
      # TODO: use ac_role_id as temporary solution until GGRC-3784 implemented
      return [i.person.id for i in self.access_control_list
              if (i.ac_role and i.ac_role.id == role_id) or
              (i.ac_role_id and i.ac_role_id == role_id)]
    return []

  def validate_acl(self):
    """Check correctness of access_control_list."""
    for acl in self.access_control_list:
      if acl.object_type != acl.ac_role.object_type:
        raise ValueError(
            "Access control list has different object_type '{}' with "
            "access control role '{}'".format(
                acl.object_type,
                acl.ac_role.object_type
            )
        )
    self.validate_role_limit()

  def validate_role_limit(self, _import=False):
    """Validate the number of roles assigned to object

    Args:
      _import: if True than function return list of errors for 'add_error'
    """
    errors = []
    count_roles = defaultdict(int)
    for acl in self.access_control_list:
      count_roles[acl.ac_role.name] += 1

    for _role in count_roles.keys():
      max_attr = "MAX_{}_NUM".format(_role).upper()
      _max = getattr(self, max_attr) if hasattr(self, max_attr) else None
      if _max and count_roles[_role] > _max:
        message = "{} role must have only {} person(s) assigned".format(_role,
                                                                        _max)
        if _import:
          errors.append((_role, message))
        else:
          raise ValueError(message)
    if _import:
      return errors
