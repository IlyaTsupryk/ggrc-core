# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Handlers for boolean attributes."""

from logging import getLogger

from ggrc import rbac, login
from ggrc.converters import errors
from ggrc.converters.handlers import handlers


logger = getLogger(__name__)


class CheckboxColumnHandler(handlers.ColumnHandler):
  """Generic checkbox handler.

  This handles all possible boolean values that are in the database None, True
  and False.
  """

  _true = "yes"
  _false = "no"
  TRUE_VALUES = {_true, "true"}
  FALSE_VALUES = {_false, "false"}
  NONE_VALUES = {"--", "---"}
  IGNORED_VALUES = {"", }

  @property
  def raw_column_value(self):
    return self.raw_value.lower()

  def parse_item(self):
    """ mandatory checkboxes will get evelauted to false on empty value """
    raw_value = self.raw_column_value
    if raw_value in self.TRUE_VALUES:
      return True
    if raw_value in self.FALSE_VALUES:
      return False
    if raw_value in self.NONE_VALUES:
      return None
    if raw_value in self.IGNORED_VALUES:
      # if obj exists or column can be empty than set_empty = True
      self.set_empty = bool(self.row_converter.obj.id or not self.mandatory)
    if self.set_empty:
      return
    if not self.mandatory:
      self.add_warning(errors.WRONG_VALUE, column_name=self.display_name)
      self.set_empty = True
      return
    if raw_value in self.IGNORED_VALUES:
      error_msg = errors.MISSING_VALUE_ERROR
    else:
      error_msg = errors.WRONG_VALUE_ERROR
    self.add_error(error_msg, column_name=self.display_name)
    self.row_converter.set_ignore()

  def get_value(self):
    val = getattr(self.row_converter.obj, self.key, False)
    if val is None:
      return "--"
    return self._true if val else self._false

  def set_obj_attr(self):
    """ handle set object for boolean values

    This is the only handler that will allow setting a None value"""
    if self.set_empty:
      return
    try:
      setattr(self.row_converter.obj, self.key, self.value)
    except ValueError:
      self.row_converter.add_error(errors.WRONG_VALUE_ERROR,
                                   column_name=self.display_name)
      logger.exception(
          "Import failed with setattr(%r, %r, %r)",
          self.row_converter.obj, self.key, self.value
      )
    except:  # pylint: disable=bare-except
      self.row_converter.add_error(errors.UNKNOWN_ERROR)
      logger.exception(
          "Import failed with setattr(%r, %r, %r)",
          self.row_converter.obj, self.key, self.value
      )


class AdminCheckboxColumnHandler(CheckboxColumnHandler):
  """Checkbox handler.

  This handles all possible boolean values that are in the database None, True
  and False. Only global Admin can setup such value.
  """

  def set_obj_attr(self):
    """Handle set object for boolean values by global Admin."""
    user = login.get_current_user(use_external_user=False)
    role = getattr(user, 'system_wide_role', None)
    if role in rbac.SystemWideRoles.admins:
      super(AdminCheckboxColumnHandler, self).set_obj_attr()
    else:
      self.add_warning(
          errors.NON_ADMIN_ACCESS_ERROR,
          object_type=self.row_converter.obj.type,
          column_name=self.display_name,
      )


class KeyControlColumnHandler(CheckboxColumnHandler):
  """Handler for key-control column.

  key-control attribute or (Significance on frontend) is a boolean field with a
  dropdown menu that contains key, non-key and --- as values.
  """

  _true = "key"
  _false = "non-key"
  TRUE_VALUES = {_true, }
  FALSE_VALUES = {_false, }


class StrictBooleanColumnHandler(CheckboxColumnHandler):
  """Handler for strict boolean values.

  You can sent only true, false, and empty string values.
  If you send true in model will send boolean True.
  If you send false in model will send boolean Flase.
  If you send empty string, and model already exists column will be skipped.
  If you send empty string and not existing instance and column is mandatory,
  Will be raised exception.

  """
  _true = "true"
  _false = "false"
  TRUE_VALUES = {_true, }
  FALSE_VALUES = {_false, }
  NONE_VALUES = set()  # Radical, only true or false
