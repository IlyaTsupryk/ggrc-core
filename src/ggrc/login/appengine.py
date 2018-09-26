# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Login handler for using App Engine authentication with Flask-Login

Assumes app.yaml is configured with:

..
  handlers:
    - url: /login
      script: <wsgi_app path>
      login: required

E.g., ``login: required`` must be specified *at least* for the '/login' route.
"""

import logging

from google.appengine.api import users
import flask
import flask_login
from werkzeug import exceptions

from ggrc.login import common
from ggrc.models import all_models
from ggrc import settings
from ggrc.utils.user_generator import find_or_create_ext_app_user
from ggrc.utils.user_generator import find_or_create_user_by_email
from ggrc.utils.user_generator import is_external_app_user_email
from ggrc.utils.user_generator import parse_user_email


logger = logging.getLogger(__name__)


def get_user():
  """Get current user using appengine authentication."""
  ae_user = users.get_current_user()
  email = ae_user.email()
  nickname = ae_user.nickname()
  user = find_or_create_user_by_email(email, name=nickname)
  return user


def login():
  """Log in current user."""
  user = get_user()
  if user.system_wide_role != 'No Access':
    flask_login.login_user(user)
    return flask.redirect(common.get_next_url(
        flask.request, default_url=flask.url_for('dashboard')))

  flask.flash(u'You do not have access. Please contact your administrator.',
              'alert alert-info')
  return flask.redirect('/')


def logout():
  flask_login.logout_user()
  return flask.redirect(users.create_logout_url(common.get_next_url(
      flask.request, default_url=flask.url_for('index'))))


def request_loader(request):
  """Get the user provided in X-GGRC-user if whitelisted Appid provided."""

  whitelist = settings.ALLOWED_QUERYAPI_APP_IDS
  inbound_appid = request.headers.get("X-Appengine-Inbound-Appid")
  if not inbound_appid:
    # don't check X-GGRC-user if the request doesn't come from another app
    return None

  if inbound_appid not in whitelist:
    # by default, we don't allow incoming app2app connections from
    # non-whitelisted apps
    raise exceptions.BadRequest("X-Appengine-Inbound-Appid header contains "
                                "untrusted application id: {}"
                                .format(inbound_appid))

  email = parse_user_email(request, "X-GGRC-user", mandatory=True)

  # External Application User should be created if doesn't exist.
  if is_external_app_user_email(email):
    db_user = find_or_create_ext_app_user()
    try:
      # Create in the DB external app user provided in X-external-user header.
      parse_user_email(request, "X-external-user", mandatory=False)
    except exceptions.BadRequest as exp:
      logger.error("Creation of external user has failed. %s", exp.message)
      raise
  else:
    db_user = all_models.Person.query.filter_by(email=email).first()
  if not db_user:
    raise exceptions.BadRequest("No user with such email: {}"
                                .format(email))
  return db_user
