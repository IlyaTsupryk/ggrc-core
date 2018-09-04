# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module provides various utils for Issue tracker integration service."""

import logging
import time

from sqlalchemy.sql import expression

from ggrc import models
from ggrc.integrations import integrations_errors
from ggrc.integrations import issues

logger = logging.getLogger(__name__)


_BATCH_SIZE = 100


def collect_issue_tracker_info(model_name, include_object=False):
  """Returns issue tracker info associated with GGRC object."""
  issue_params = {}
  issue_objects = get_active_issue_info(model_name=model_name)
  for iti in issue_objects:
    sync_object = iti.issue_tracked_obj
    if not sync_object:
      logger.error(
          "The %s corresponding to the Issue Tracker Issue ID=%s "
          "does not exist.", model_name, iti.issue_id)
      continue

    status_value = sync_object.status
    if not status_value:
      logger.error(
          'Inexistent Issue Tracker status for %s ID=%d '
          'with status: %s.', model_name, sync_object.id, status_value)
      continue

    issue_params[iti.issue_id] = {
        "object_id": sync_object.id,
        "state": {
            "status": status_value,
            "type": iti.issue_type,
            "priority": iti.issue_priority,
            "severity": iti.issue_severity,
        },
    }

    if include_object:
      issue_params[iti.issue_id]["object"] = sync_object

  return issue_params


def get_active_issue_info(model_name):
  """Returns stored in GGRC issue tracker info associated with model."""
  issuetracker_cls = models.IssuetrackerIssue
  return issuetracker_cls.query.filter(
      issuetracker_cls.object_type == model_name,
      issuetracker_cls.enabled == expression.true(),
      issuetracker_cls.issue_id.isnot(None),
  ).order_by(issuetracker_cls.object_id).all()


def iter_issue_batches(ids, include_emails=False):
  """Generates a sequence of batches of issues from Issue Tracker by IDs."""
  cli = issues.Client()

  for i in xrange(0, len(ids), _BATCH_SIZE):
    chunk = ids[i:i + _BATCH_SIZE]
    logger.debug('Issue ids to process: %s', chunk)
    try:
      response = cli.search({
          'issue_ids': chunk,
          'page_size': _BATCH_SIZE,
      })
    except integrations_errors.HttpError as error:
      logger.error(
          'Unable to fetch Issue Tracker issues by IDs: %r', error)
      return

    issue_infos = {}
    response_issues = response.get('issues') or []
    for info in response_issues:
      state = info['issueState'] or {}
      issue_info = {
          'status': state.get('status'),
          'type': state.get('type'),
          'priority': state.get('priority'),
          'severity': state.get('severity'),
      }

      if include_emails:
        issue_info.update({
            'assignee': state.get('assignee'),
            'reporter': state.get('reporter'),
            'verifier': state.get('verifier'),
        })

      issue_infos[info['issueId']] = issue_info

    if issue_infos:
      yield issue_infos


def update_issue(cli, issue_id, params, max_attempts=5, interval=1):
  """Performs issue update request."""
  last_error = integrations_errors.Error
  for _ in range(max_attempts):
    try:
      cli.update_issue(issue_id, params)
    except integrations_errors.HttpError as error:
      last_error = error
      if error.status == 429:
        logger.warning(
            'The request updating ticket ID=%s was '
            'rate limited and will be re-tried: %s', issue_id, error)
        time.sleep(interval)
        continue
    break
  else:
    logger.warning("Attempts limit(%s) was reached.", max_attempts)
    raise last_error


def create_issue(cli, params, max_attempts=5, interval=1):
  """Performs issue create request."""
  last_error = integrations_errors.Error
  for _ in range(max_attempts):
    try:
      return cli.create_issue(params)
    except integrations_errors.HttpError as error:
      last_error = error
      if error.status == 429:
        logger.warning(
            'The request creating ticket was rate limited and '
            'will be re-tried: %s', error)
        time.sleep(interval)
        continue
    break
  else:
    logger.warning("Attempts limit(%s) was reached.", max_attempts)
  raise last_error
