# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for appengine login model."""
from werkzeug import exceptions

from ggrc import settings
from ggrc.login.appengine import request_loader
from integration.ggrc import TestCase
from integration.ggrc.models.factories import PersonFactory


class TestRequestLoader(TestCase):
  """Tests for "request_loader"."""

  ALLOWED_APPID = "allowed"

  loaded_email = None
  raised_exception = None

  def setUp(self):
    """setUp, nothing else to add."""
    super(TestRequestLoader, self).setUp()

    settings.ALLOWED_QUERYAPI_APP_IDS.append(self.ALLOWED_APPID)
    self._custom_headers["X-appengine-inbound-appid"] = self.ALLOWED_APPID

    self.app.login_manager.request_loader(self.handle_loaded_user)
    self.loaded_email = None
    self.raised_exception = None

  def handle_loaded_user(self, request):
    """Wrapper for request_loader that handles result/exceptions."""
    try:
      user = request_loader(request)
    except Exception as exc:
      self.raised_exception = exc
      raise

    if user:
      self.loaded_email = user.email

    return user

  def test_ggrc_user(self):
    """Test request_loader with correct headers."""
    user = PersonFactory()
    custom_headers = {"X-ggrc-user": "{\"email\": \"%s\"}" % user.email}

    with self.custom_headers(custom_headers):
      self.client.get("/", headers=self.headers)

    self.assertEqual(self.raised_exception, None)
    self.assertEqual(self.loaded_email, user.email)

  def test_no_appid_header(self):
    """Test request_loader without app ID header."""
    with self.custom_headers():
      del self._custom_headers["X-appengine-inbound-appid"]
      self.client.get("/", headers=self.headers)

    self.assertEqual(self.raised_exception, None)
    self.assertEqual(self.loaded_email, None)

  def test_wrong_appid_header(self):
    """Test request_loader with wrong app ID header."""
    custom_headers = {"X-appengine-inbound-appid": "not-allowed"}

    with self.custom_headers(custom_headers):
      self.client.get("/", headers=self.headers)

    self.assertEqual(self.loaded_email, None)
    self.assertIsInstance(self.raised_exception, exceptions.BadRequest)
