# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""This module provides endpoints to add/remove folder for Folderable models"""

import flask.views
from flask import request
from werkzeug import exceptions

from ggrc import login
from ggrc import utils
from ggrc import db
from ggrc.models import inflector
from ggrc.models import mixins
from ggrc.models.mixins.with_readonly_access import WithReadOnlyAccess
from ggrc.rbac import permissions
from ggrc.utils.log_event import log_event


class AddRemoveFolderView(flask.views.MethodView):
  """View to add/remove folder for regular GGRC users"""

  decorators = [login.login_required,
                utils.validate_mimetype("application/json")]

  def post(self):
    """handler of POST method"""

    if login.is_external_app_user():
      raise exceptions.Forbidden()

    is_modified = self._perform_request()

    if is_modified:
      # create revision and commit changes
      log_event(db.session)
      db.session.commit()

    return "Success", 200

  def _perform_request(self):
    """Parse request and modify corresponding object

    :return True if object modified, else False
    """

    request_json = request.json

    folder_id = self._get_folder(request_json)
    obj = self._get_object(request_json=request_json)

    endpoint_name = request.endpoint
    if endpoint_name == 'add_folder':
      return self._add_folder(obj, folder_id)
    elif endpoint_name == 'remove_folder':
      return self._remove_folder(obj, folder_id)

    raise NotImplementedError()

  @staticmethod
  def _add_folder(obj, folder_id):
    """Perform add_folder specific logic

    :return True if object was modified, else False
    """

    if obj.folder != folder_id:
      obj.folder = folder_id
      return True

    return False

  @staticmethod
  def _remove_folder(obj, folder_id):
    """Perform remove_folder specific logic

    :return True if object was modified, else False
    """

    if obj.folder != folder_id:
      raise exceptions.BadRequest(
          "'folder' value is not equal to the current value in the object")

    obj.folder = ""

    return True

  @staticmethod
  def _get_folder(request_json):
    """Return folder_id or raise HTTP error"""

    ret = request_json.get('folder')
    if ret is None or not ret.strip():
      raise exceptions.BadRequest("'folder' must be specified")

    return ret.strip()

  def _get_object(self, request_json):
    """Return existing object or raise HTTP error"""

    object_type = request_json.get('object_type')
    object_id = request_json.get('object_id')

    if None in (object_type, object_id):
      raise exceptions.BadRequest(
          "'object_id' and 'object_type' must be specified")

    model = inflector.get_model(object_type)
    if model is None or not issubclass(model, mixins.Folderable):
      raise exceptions.BadRequest("Model {} not found".format(object_type))

    obj = model.query.get(object_id)
    if obj is None:
      raise exceptions.NotFound(
          "{} with id {} not found".format(model.__name__, object_id))

    self._ensure_has_permissions(obj)
    self._validate_readonly_access(obj)

    return obj

  @staticmethod
  def _ensure_has_permissions(obj):
    """Ensure user has permissions, otherwise raise error"""

    model_name = obj.__class__.__name__

    if permissions.is_allowed_update(model_name, obj.id, obj.context_id):
      return

    if permissions.has_conditions('update', model_name):
      return

    if permissions.is_allowed_update_for(obj):
      return

    raise exceptions.Forbidden()

  @staticmethod
  def _validate_readonly_access(obj):
    """Return 405 MethodNotAllowed if object is marked as read-only"""

    if not isinstance(obj, WithReadOnlyAccess):
      return

    if obj.readonly:
      raise exceptions.MethodNotAllowed(
          "The object is in a read-only mode and is dedicated for SOX needs")


def init_folder_views(app):
  """Initializer for folder views"""

  app.add_url_rule(
      '/api/add_folder',
      view_func=AddRemoveFolderView.as_view('add_folder')
  )

  app.add_url_rule(
      '/api/remove_folder',
      view_func=AddRemoveFolderView.as_view('remove_folder')
  )
