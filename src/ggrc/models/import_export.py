# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

""" ImportExport model."""

import json
from datetime import datetime, timedelta
from logging import getLogger

from sqlalchemy.dialects import mysql

from ggrc import db
from ggrc.models.mixins.base import Identifiable
from ggrc.login import get_current_user
from werkzeug.exceptions import BadRequest, Forbidden, NotFound


logger = getLogger(__name__)


class ImportExport(Identifiable, db.Model):
  """ImportExport Model."""

  __tablename__ = 'import_exports'

  IMPORT_JOB_TYPE = 'Import'
  EXPORT_JOB_TYPE = 'Export'

  ANALYSIS_STATUS = 'Analysis'
  BLOCKED_STATUS = 'Blocked'
  FAILED_STATUS = 'Failed'
  IN_PROGRESS_STATUS = 'In Progress'
  NOT_STARTED_STATUS = 'Not Started'

  IMPORT_EXPORT_STATUSES = [
      NOT_STARTED_STATUS,
      ANALYSIS_STATUS,
      IN_PROGRESS_STATUS,
      BLOCKED_STATUS,
      'Analysis Failed',
      'Stopped',
      FAILED_STATUS,
      'Finished',
  ]

  DEFAULT_COLUMNS = ['id', 'title', 'created_at', 'status']

  job_type = db.Column(db.Enum(IMPORT_JOB_TYPE, EXPORT_JOB_TYPE),
                       nullable=False)
  status = db.Column(db.Enum(*IMPORT_EXPORT_STATUSES), nullable=False,
                     default=NOT_STARTED_STATUS)
  description = db.Column(db.Text)
  created_at = db.Column(db.DateTime, nullable=False)
  start_at = db.Column(db.DateTime)
  end_at = db.Column(db.DateTime)
  created_by_id = db.Column(db.Integer,
                            db.ForeignKey('people.id'), nullable=False)
  created_by = db.relationship('Person',
                               foreign_keys='ImportExport.created_by_id',
                               uselist=False)
  results = db.Column(mysql.LONGTEXT)
  title = db.Column(db.Text)
  content = db.Column(mysql.LONGTEXT)
  gdrive_metadata = db.Column('gdrive_metadata', db.Text)

  def log_json(self, is_default=False):
    """JSON representation"""
    if is_default:
      columns = self.DEFAULT_COLUMNS
    else:
      columns = (column.name for column in self.__table__.columns
                 if column.name not in ('content', 'gdrive_metadata'))

    res = {}
    for column in columns:
      if column == "results":
        res[column] = json.loads(self.results) if self.results \
            else self.results
      elif column == "created_at":
        res[column] = self.created_at.isoformat()
      else:
        res[column] = getattr(self, column)

    return res


def create_import_export_entry(**kwargs):
  """Create ImportExport entry"""
  meta = json.dumps(kwargs['gdrive_metadata']) if 'gdrive_metadata' in kwargs \
      else None
  results = json.dumps(kwargs['results']) if 'results' in kwargs else None
  ie_job = ImportExport(job_type=kwargs.get('job_type', 'Import'),
                        status=kwargs.get('status', 'Not Started'),
                        created_at=datetime.utcnow(),
                        created_by=get_current_user(),
                        title=kwargs.get('title'),
                        content=kwargs.get('content'),
                        gdrive_metadata=meta,
                        results=results,
                        start_at=kwargs.get('start_at', None))

  db.session.add(ie_job)
  db.session.commit()
  return ie_job


def get_jobs(job_type, ids=None):
  """Get list of jobs by type and/or ids"""
  conditions = [ImportExport.created_by == get_current_user(),
                ImportExport.job_type == job_type]
  if ids:
    conditions.append(ImportExport.id.in_(ids))
  return [ie.log_json(is_default=True)
          for ie in ImportExport.query.filter(*conditions)]


def delete_previous_imports():
  """Delete not finished imports"""

  imported_jobs = ImportExport.query.filter(
      ImportExport.created_by == get_current_user(),
      ImportExport.job_type == ImportExport.IMPORT_JOB_TYPE)

  active_jobs = db.session.query(imported_jobs.filter(
      ImportExport.status.in_([ImportExport.ANALYSIS_STATUS,
                               ImportExport.IN_PROGRESS_STATUS])
  ).exists()).scalar()
  if active_jobs:
    raise BadRequest('Import in progress')

  imported_jobs.filter(
      ImportExport.status.in_([ImportExport.NOT_STARTED_STATUS,
                               ImportExport.BLOCKED_STATUS])
  ).delete(synchronize_session=False)
  db.session.commit()


def get(ie_id):
  """Get import_exports entry by id if entry belongs to current user"""
  ie_job = ImportExport.query.get(ie_id)
  if not ie_job:
    raise NotFound()
  if ie_job.created_by == get_current_user():
    return ie_job
  raise Forbidden()


def clear_overtimed_tasks():
  """
  Clear ImportExport jobs not finished normally

  TaskQueue task can run in background no more than 24 hours,
  if ImportExport task did not change status to Finished or Failed
  during this time, task considered as dead.
  """
  active_jobs = ImportExport.query.filter(
      ImportExport.status.in_([ImportExport.ANALYSIS_STATUS,
                               ImportExport.IN_PROGRESS_STATUS])
  )
  for ie_job in active_jobs:
    now = datetime.utcnow()
    if not ie_job.start_at:
      ie_job.start_at = datetime.utcnow()
      continue
    deadline = ie_job.start_at + timedelta(hours=24)
    if now > deadline:
      ie_job.status = 'Failed'
      ie_job.end_at = datetime.utcnow()
      logger.warning("%s job ID:%d working >24 hours. "
                     "Background task is dead. "
                     "Status changed to Failed",
                     ie_job.job_type,
                     ie_job.id)
  db.session.commit()
