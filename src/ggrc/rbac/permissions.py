# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Basic RBAC permissions module."""

from flask import g
from flask.ext.login import current_user

from ggrc import login
from ggrc.extensions import get_extension_instance
from ggrc.rbac import SystemWideRoles


def get_permissions_provider():
  return get_extension_instance(
      'USER_PERMISSIONS_PROVIDER',
      'ggrc.rbac.permissions_provider.DefaultUserPermissionsProvider')


def permissions_for(user=None):
  """Get full permissions for user."""
  if user is None:
    user = get_user()
  return get_permissions_provider().permissions_for(user)


def get_user():
  """Get selected user."""
  if hasattr(g, 'user'):
    return g.user
  return current_user


def is_allowed_create(resource_type, resource_id, context_id):
  """Whether or not the user is allowed to create a resource of the specified
  type in the context.
  """
  return permissions_for(get_user()).is_allowed_create(
      resource_type, resource_id, context_id)


def is_allowed_create_for(instance):
  """Whether or not the user is allowed to create this particular resource
  instance.
  """
  return permissions_for(get_user()).is_allowed_create_for(instance)


def has_system_wide_update():
  """Check if user has system wide update access to all objects."""
  user = login.get_current_user(use_external_user=False)
  system_wide_role = getattr(user, "system_wide_role",
                             SystemWideRoles.NO_ACCESS)
  return system_wide_role in SystemWideRoles.update_roles


def has_system_wide_read():
  """Check if user has system wide read access to all objects."""
  user = login.get_current_user(use_external_user=False)
  system_wide_role = getattr(user, "system_wide_role",
                             SystemWideRoles.NO_ACCESS)
  return system_wide_role in SystemWideRoles.read_roles


def is_allowed_read(resource_type, resource_id, context_id):
  """Whether or not the user is allowed to read a resource of the specified
  type in the context.
  """
  if has_system_wide_read():
    return True
  return permissions_for(get_user()).is_allowed_read(
      resource_type, resource_id, context_id)


def is_allowed_read_for(instance):
  """Whether or not the user is allowed to read this particular resource
  instance.
  """
  if has_system_wide_read():
    return True
  return permissions_for(get_user()).is_allowed_read_for(instance)


def is_allowed_update(resource_type, resource_id, context_id):
  """Whether or not the user is allowed to update a resource of the specified
  type in the context.
  """
  return permissions_for(get_user()).is_allowed_update(
      resource_type, resource_id, context_id)


def is_allowed_update_for(instance):
  """Whether or not the user is allowed to update this particular resource
  instance.
  """
  return permissions_for(get_user()).is_allowed_update_for(instance)


def is_allowed_delete(resource_type, resource_id, context_id):
  """Whether or not the user is allowed to delete a resource of the specified
  type in the context.
  """
  return permissions_for(get_user()).is_allowed_delete(
      resource_type, resource_id, context_id)


def is_allowed_delete_for(instance):
  return permissions_for(get_user()).is_allowed_delete_for(instance)


def create_contexts_for(resource_type):
  """All contexts in which the user has create permission."""
  return permissions_for(get_user()).create_contexts_for(resource_type)


def read_contexts_for(resource_type):
  """All contexts in which the user has read permission."""
  return permissions_for(get_user()).read_contexts_for(resource_type)


def update_contexts_for(resource_type):
  """All contexts in which the user has update permission."""
  return permissions_for(get_user()).update_contexts_for(resource_type)


def delete_contexts_for(resource_type):
  """All contexts in which the user has delete permission."""
  return permissions_for(get_user()).delete_contexts_for(resource_type)


def create_resources_for(resource_type):
  """All resources in which the user has create permission."""
  return permissions_for(get_user()).create_resources_for(resource_type)


def read_resources_for(resource_type):
  """All resources in which the user has read permission."""
  return permissions_for(get_user()).read_resources_for(resource_type)


def update_resources_for(resource_type):
  """All resources in which the user has update permission."""
  return permissions_for(get_user()).update_resources_for(resource_type)


def delete_resources_for(resource_type):
  """All resources in which the user has delete permission."""
  return permissions_for(get_user()).delete_resources_for(resource_type)


def is_admin():
  """Whether the current user has ADMIN permission."""
  return permissions_for(get_user()).is_admin()


def has_conditions(action, resource):
  """Check permission conditions.

  Checks if the resource has a condition that needs to be checked with
  is_allowed_for.
  """
  # pylint disable=protected-access
  _permissions = permissions_for()._permissions()
  return bool(_permissions.get(action, {})
              .get(resource, {})
              .get('conditions', {}))


def get_context_resource(model_name, permission_type='read'):
  """Get allowed contexts and resources."""
  permissions_map = {
      "create": (create_contexts_for, create_resources_for),
      "read": (read_contexts_for, read_resources_for),
      "update": (update_contexts_for, update_resources_for),
      "delete": (delete_contexts_for, delete_resources_for),
  }

  contexts = permissions_map[permission_type][0](model_name)
  resources = permissions_map[permission_type][1](model_name)

  return contexts, resources
