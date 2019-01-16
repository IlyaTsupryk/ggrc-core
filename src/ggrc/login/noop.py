# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""ggrc.login.noop

Login as example user for development mode.
"""

import json
import flask_login
from flask import url_for, redirect, request, session, g, flash

from ggrc.login import common

DEFAULT_USER_NAME = 'Example User'
DEFAULT_USER_EMAIL = 'user@example.com'


def get_user():
  """Gets current user from the request headers."""
  if 'X-ggrc-user' in request.headers:
    json_user = json.loads(request.headers['X-ggrc-user'])
    email = json_user.get('email', DEFAULT_USER_EMAIL)
    name = json_user.get('name', DEFAULT_USER_NAME)
    permissions = json_user.get('permissions', None)
    session['permissions'] = permissions
  else:
    email = DEFAULT_USER_EMAIL
    name = DEFAULT_USER_NAME
    permissions = None
  from ggrc.utils.user_generator import find_or_create_user_by_email
  user = find_or_create_user_by_email(email=email, name=name)
  permissions = session['permissions'] if 'permissions' in session else None
  setattr(g, '_request_permissions', permissions)
  return user


def before_request(*args, **kwargs):  # pylint:disable=unused-argument
  permissions = session['permissions'] if 'permissions' in session else None
  setattr(g, '_request_permissions', permissions)


def login():
  """Logs in current user."""
  from ggrc.login.common import get_next_url
  db_user = get_user()
  common.commit_user_and_role(db_user)
  if db_user.system_wide_role != 'No Access':
    flask_login.login_user(db_user)
    return redirect(get_next_url(request, default_url=url_for('dashboard')))
  flash(u'You do not have access. Please contact your administrator.',
        'alert alert-info')
  return redirect('/')


def logout():
  """Logs out current user."""
  from ggrc.login.common import get_next_url
  if 'permissions' in session:
    del session['permissions']
  flask_login.logout_user()
  return redirect(get_next_url(request, default_url=url_for('index')))


def request_loader(request_):
  """Get the user provided in X-GGRC-user if whitelisted Appid provided."""
  return common.get_ggrc_user(request_, False)
