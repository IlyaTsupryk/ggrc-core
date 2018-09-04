# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for ggrc background tasks."""

import json
import traceback
import uuid
from logging import getLogger
from functools import wraps
from time import time

from flask import request
from flask.wrappers import Response
from werkzeug.datastructures import Headers

from ggrc import db
from ggrc import settings
from ggrc.login import get_current_user
from ggrc.access_control import role
from ggrc.access_control import list as acl
from ggrc.access_control import roleable
from ggrc.models.mixins import base
from ggrc.models.mixins import Base
from ggrc.models.deferred import deferred
from ggrc.models.mixins import Stateful
from ggrc.models.types import CompressedType
from ggrc.models import reflection


logger = getLogger(__name__)

BANNED_HEADERS = {
    "X-Appengine-Country",
    "X-Appengine-Queuename",
    "X-Appengine-Current-Namespace",
    "X-Appengine-Taskname",
    "X-Appengine-Tasketa",
    "X-Appengine-Taskexecutioncount",
    "X-Appengine-Taskretrycount",
    "X-Task-Id",
}


class BackgroundTask(roleable.Roleable, base.ContextRBAC, Base, Stateful,
                     db.Model):
  """Background task model."""
  __tablename__ = 'background_tasks'

  VALID_STATES = [
      "Pending",
      "Running",
      "Success",
      "Failure"
  ]
  name = deferred(db.Column(db.String), 'BackgroundTask')
  parameters = deferred(db.Column(CompressedType), 'BackgroundTask')
  result = deferred(db.Column(CompressedType), 'BackgroundTask')

  _api_attrs = reflection.ApiAttributes('name', 'result')

  _aliases = {
      "status": {
          "display_name": "State",
          "mandatory": False,
          "description": "Options are: \n{}".format('\n'.join(VALID_STATES))
      }
  }

  def start(self):
    """Mark the current task as running."""
    self.status = "Running"
    db.session.add(self)
    db.session.commit()

  def finish(self, status, result):
    """Finish the current bg task."""
    # Ensure to not commit any not-yet-committed changes
    db.session.rollback()

    if isinstance(result, Response):
      self.result = {'content': result.response[0],
                     'status_code': result.status_code,
                     'headers': result.headers.items()}
    else:
      self.result = {'content': result,
                     'status_code': 200,
                     'headers': [('Content-Type', 'text/html')]}
    self.status = status
    db.session.add(self)
    db.session.commit()

  def make_response(self, default=None):
    """Create task status response."""
    if self.result is None:
      return default
    from ggrc.app import app
    return app.make_response((self.result['content'],
                              self.result['status_code'],
                              self.result['headers']))

  def task_scheduled_response(self):
    """Create success response with info about scheduled task."""
    from ggrc.app import app
    return self.make_response(
        app.make_response((
            json.dumps("scheduled %s" % self.name),
            200,
            [("Content-Type", "application/json")]
        ))
    )


def _add_task_acl(task):
  """Add ACL entry for the current users background task."""
  roles = role.get_ac_roles_for(task.type)
  admin_role = roles.get("Admin", None)
  if admin_role:
    acl.AccessControlList(
        person=get_current_user(),
        ac_role=admin_role,
        object=task,
    )
  db.session.add(task)
  db.session.commit()
  if admin_role:
    from ggrc.cache.utils import clear_users_permission_cache
    clear_users_permission_cache([get_current_user().id])


def collect_task_headers():
  """Get headers required for appengine background task run."""
  return Headers({k: v for k, v in request.headers if k not in BANNED_HEADERS})


def create_task(name, url, queued_callback=None, parameters=None, method=None):
  """Create a enqueue a bacground task."""
  if not method:
    method = request.method

  # task name must be unique
  if not parameters:
    parameters = {}

  task = BackgroundTask(name=name + str(int(time())))
  task.parameters = parameters
  task.modified_by = get_current_user()
  _add_task_acl(task)

  # schedule a task queue
  if getattr(settings, 'APP_ENGINE', False):
    from google.appengine.api import taskqueue
    headers = collect_task_headers()
    headers.add('X-Task-Id', task.id)
    taskqueue.add(
        queue_name="ggrc",
        url=url,
        name="{}_{}".format(task.name, task.id),
        params={'task_id': task.id},
        method=method,
        headers=headers
    )
  elif queued_callback:
    queued_callback(task)
  return task


def create_lightweight_task(name, url, queued_callback=None, parameters=None,
                            method=None):
  """Create background task.

  This function create an app engine background task without handling
  related BackgroundTask object.
  """
  if not method:
    method = request.method

  if not parameters:
    parameters = {}

  if getattr(settings, 'APP_ENGINE', False):
    from google.appengine.api import taskqueue
    taskqueue.add(
        queue_name="ggrc",
        url=url,
        name="{}_{}".format(name + str(int(time())), uuid.uuid4()),
        payload=json.dumps(parameters),
        method=method,
        headers=collect_task_headers()
    )
  elif queued_callback:
    queued_callback(**parameters)
  else:
    raise ValueError(
        "Either queued_callback should be provided or APP_ENGINE set to true."
    )


def make_task_response(id_):
  """Make a response for a task with the given id."""
  task = BackgroundTask.query.get(id_)
  return task.make_response()


def queued_task(func):
  """Decorator for task queues."""
  from ggrc.app import app

  @wraps(func)
  def decorated_view(*args, **_):
    """Background task runner.

    This runner makes sure that the task is called with the task model as
    the parameter.
    """
    if args and isinstance(args[0], BackgroundTask):
      task = args[0]
    else:
      task_id = request.headers.get("X-Task-Id", request.values.get("task_id"))
      task = BackgroundTask.query.get(task_id)
    task.start()
    try:
      result = func(task)
    except:  # pylint: disable=bare-except
      # Bare except is allowed here so that we can respond with the correct
      # message to all exceptions.
      logger.exception("Task failed")
      task.finish("Failure", app.make_response((
          traceback.format_exc(), 200, [('Content-Type', 'text/html')])))

      # Return 200 so that the task is not retried
      return app.make_response((
          'failure', 200, [('Content-Type', 'text/html')]))
    task.finish("Success", result)
    return result
  return decorated_view
