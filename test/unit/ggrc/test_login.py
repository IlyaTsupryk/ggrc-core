# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Unit test suite for login __init__."""

import unittest
import mock

from ggrc import login


class TestIsExternalAppUser(unittest.TestCase):
  """Unittests for is_external_app_user function."""

  @mock.patch('ggrc.login.get_current_user')
  def test_no_logged_in_user(self, current_user_mock):
    """No logged in user presented."""
    current_user_mock.return_value = None
    self.assertFalse(login.is_external_app_user())
    current_user_mock.assert_called_once_with(permission_check=True)

  @mock.patch('ggrc.login.get_current_user')
  def test_anonymous_user(self, current_user_mock):
    """Currently logged in user is anonymous."""
    user_mock = mock.MagicMock()
    user_mock.is_anonymous.return_value = True
    current_user_mock.return_value = user_mock
    self.assertFalse(login.is_external_app_user())
    current_user_mock.assert_called_once_with(permission_check=True)
    user_mock.is_anonymous.assert_called_once_with()

  @mock.patch('ggrc.utils.user_generator.is_external_app_user_email')
  @mock.patch('ggrc.login.get_current_user')
  def test_not_external_user(self, current_user_mock, is_external_email_mock):
    """Currently logged in user is not external app."""
    user_mock = mock.MagicMock()
    user_mock.email = 'user@example.com'
    user_mock.is_anonymous.return_value = False
    current_user_mock.return_value = user_mock
    is_external_email_mock.return_value = False
    self.assertFalse(login.is_external_app_user())
    current_user_mock.assert_called_once_with(permission_check=True)
    user_mock.is_anonymous.assert_called_once_with()
    is_external_email_mock.assert_called_once_with('user@example.com')

  @mock.patch('ggrc.utils.user_generator.is_external_app_user_email')
  @mock.patch('ggrc.login.get_current_user')
  def test_external_user(self, current_user_mock, is_external_email_mock):
    """Currently logged in user is external app."""
    user_mock = mock.MagicMock()
    user_mock.email = 'user@example.com'
    user_mock.is_anonymous.return_value = False
    current_user_mock.return_value = user_mock
    is_external_email_mock.return_value = True
    self.assertTrue(login.is_external_app_user())
    current_user_mock.assert_called_once_with(permission_check=True)
    user_mock.is_anonymous.assert_called_once_with()
    is_external_email_mock.assert_called_once_with('user@example.com')
