# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""ggrc.login.noop

Login as example user for development mode.
"""

import flask_login
import json
from flask import url_for, redirect, request, session, g, flash

default_user_name = 'Example User'
default_user_email = 'user@example.com'


def get_user():
  if 'X-ggrc-user' in request.headers:
    json_user = json.loads(request.headers['X-ggrc-user'])
    email = json_user.get('email', default_user_email)
    name = json_user.get('name', default_user_name)
    permissions = json_user.get('permissions', None)
    session['permissions'] = permissions
  else:
    email = default_user_email
    name = default_user_name
    permissions = None
  from ggrc.utils.user_generator import find_or_create_user_by_email
  user = find_or_create_user_by_email(email=email, name=name)
  permissions = session['permissions'] if 'permissions' in session else None
  setattr(g, '_request_permissions', permissions)
  return user


def before_request(*args, **kwargs):
  permissions = session['permissions'] if 'permissions' in session else None
  setattr(g, '_request_permissions', permissions)


def login():
  from ggrc.login.common import get_next_url
  user = get_user()
  if user.system_wide_role != 'No Access':
    flask_login.login_user(user)
    return redirect(get_next_url(request, default_url=url_for('dashboard')))
  else:
    flash(u'You do not have access. Please contact your administrator.',
          'alert alert-info')
    return redirect('/')


def logout():
  from ggrc.login.common import get_next_url
  if 'permissions' in session:
    del session['permissions']
  flask_login.logout_user()
  return redirect(get_next_url(request, default_url=url_for('index')))
