# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Mixins for issue tracker integration functionality."""

# pylint: disable=unsubscriptable-object
# pylint: disable=using-constant-test

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.ext.declarative import declared_attr

from ggrc.models import reflection
from ggrc.models.issuetracker_issue import IssuetrackerIssue

from ggrc.builder import simple_property


class IssueTracked(object):
  """IssueTracked mixin.

  Defines a backref in IssueTrackerIssue model named ModelName_issue_tracked.
  """
  # pylint: disable=too-few-public-methods

  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute("issue_tracker", create=False, update=False),
  )

  def __init__(self, *args, **kwargs):
    super(IssueTracked, self).__init__(*args, **kwargs)
    self._warnings = []

  @orm.reconstructor
  def init_on_load(self):
    self._warnings = []

  @declared_attr
  def issuetracker_issue(cls):  # pylint: disable=no-self-argument
    """Relationship with the corresponding issue for cls."""

    def join_function():
      """Object and Notification join function."""
      object_id = sa.orm.foreign(IssuetrackerIssue.object_id)
      object_type = sa.orm.foreign(IssuetrackerIssue.object_type)
      return sa.and_(object_type == cls.__name__,
                     object_id == cls.id)

    return sa.orm.relationship(
        IssuetrackerIssue,
        primaryjoin=join_function,
        backref="{}_issue_tracked".format(cls.__name__),
        cascade="all, delete-orphan",
        uselist=False,
    )

  @simple_property
  def issue_tracker(self):
    """Returns representation of issue tracker related info as a dict."""
    issue_info = self.issuetracker_issue
    if issue_info:
      issue_tracker_attrs = issue_info.to_dict(include_issue=True)
    else:
      issue_tracker_attrs = IssuetrackerIssue.get_issuetracker_issue_stub()

    issue_tracker_attrs["_warnings"] = self._warnings
    return issue_tracker_attrs

  def add_warning(self, message):
    self._warnings.append(message)


class IssueTrackedWithUrl(IssueTracked):
  """Class that identifies IssueTracked models that have url."""
  pass


class IssueTrackedWithConfig(IssueTracked):
  """Class that identifies IssueTracked models that have no url."""
  pass
