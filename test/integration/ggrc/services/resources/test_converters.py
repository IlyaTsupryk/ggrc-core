# -*- coding: utf-8 -*-
# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for import/export endpoints.

Endpoints:

  - /api/people/person_id/imports
  - /api/people/person_id/exports

"""

import json

from datetime import datetime

import ddt
import mock

from ggrc import db
from ggrc.models import all_models
from ggrc.views import converters
from ggrc.models import exceptions

from integration.ggrc import api_helper
from integration.ggrc.models import factories
from integration.ggrc.services import TestCase
from integration.ggrc.utils import helpers


class TestImportExportBase(TestCase):
  """Base class for imports/exports tests."""

  def setUp(self):
    super(TestImportExportBase, self).setUp()
    self.client.get("/login")

  def run_full_import(self, user, data):
    """Emulate full cycle of data importing.

    Args:
        user: User object under which import should be run.
        data: data that should be imported.
    """
    imp_exp = factories.ImportExportFactory(
        job_type="Import",
        status="Blocked",
        created_by=user,
        created_at=datetime.now(),
        content=data,
    )

    with mock.patch("ggrc.views.converters.check_for_previous_run"):
      return self.client.put(
          "/api/people/{}/imports/{}/start".format(user.id, imp_exp.id),
          headers=self.headers,
      )

  def run_full_export(self, user, obj):
    """Run export of test data through the /api/people/{}/exports endpoint."""
    with mock.patch("ggrc.views.converters.check_for_previous_run"):
      return self.client.post(
          "/api/people/{}/exports".format(user.id),
          data=json.dumps({
              "objects": [{
                  "object_name": obj.type,
                  "ids": [obj.id]}],
              "current_time": str(datetime.now())}),
          headers=self.headers
      )


@ddt.ddt
class TestImportExports(TestImportExportBase):
  """Tests for imports/exports endpoints."""

  def setUp(self):
    super(TestImportExports, self).setUp()
    self.headers = {
        "Content-Type": "application/json",
        "X-Requested-By": ["GGRC"],
    }
    self.api = api_helper.Api()

  @mock.patch("ggrc.gdrive.file_actions.get_gdrive_file_data",
              new=lambda x: (x, None, ''))
  def test_failed_imports_post(self):
    """Test imports post"""
    user = all_models.Person.query.first()
    data = [
        ['Object type'],
        ['invalid control', 'Title'],
        ['', 'Title'],
        [],
        [],
        ['Object type'],
        ['Control', 'Title'],
        ['', 'Title'],
        [],
        ['Object type'],
        ['Assessment', 'Title'],
        ['', 'Title'],
        [],
    ]
    response = self.client.post(
        "/api/people/{}/imports".format(user.id),
        data=json.dumps(data),
        headers=self.headers)
    self.assert200(response)
    self.assertFalse(response.json["objects"])
    self.assertEqual(response.json["import_export"]["status"],
                     "Analysis Failed")
    self.assertEqual(len(response.json["import_export"]["results"]), 3)
    for block in response.json["import_export"]["results"]:
      if block["name"] == "":
        self.assertEqual(block["rows"], 1)
        self.assertIn(u"Line 2", block["block_errors"][0])
      else:
        self.assertEqual(block["rows"], 1)
        self.assertFalse(block["block_errors"])

  @mock.patch("ggrc.gdrive.file_actions.get_gdrive_file_data",
              new=lambda x: (x, None, ''))
  def test_imports_post(self):
    """Test imports post"""
    user = all_models.Person.query.first()
    data = [
        ['Object type'],
        ['CONTROL', 'Title'],
        ['', 'Title1'],
        ['', 'Title2'],
        [],
        ['Object type'],
        ['Control', 'Title'],
        ['', 'Title3'],
        [],
        ['Object type'],
        ['Assessment', 'Title'],
        ['', 'Title3'],
        [],
        ['Object type'],
        ['Audit', 'Title'],
        ['', ''],
    ]
    response = self.client.post(
        "/api/people/{}/imports".format(user.id),
        data=json.dumps(data),
        headers=self.headers)
    self.assert200(response)
    self.assertEqual(response.json["import_export"]["status"], "Not Started")
    self.assertEqual(response.json["objects"]["Assessment"], 1)
    self.assertEqual(response.json["objects"]["Control"], 3)

  @ddt.data("Import", "Export")
  def test_get(self, job_type):
    """Test imports/exports get"""
    user = all_models.Person.query.first()
    ie1 = factories.ImportExportFactory(job_type=job_type,
                                        created_by=user,
                                        created_at=datetime.now())
    factories.ImportExportFactory(job_type=job_type,
                                  created_by=user,
                                  created_at=datetime.now())
    response = self.client.get(
        "/api/people/{}/{}s/{}".format(user.id, job_type.lower(), ie1.id),
        headers=self.headers)
    self.assert200(response)
    self.assertEqual(response.json["id"], ie1.id)

    response = self.client.get(
        "/api/people/{}/{}s".format(user.id, job_type.lower()),
        headers=self.headers)
    self.assert200(response)
    self.assertEqual(len(response.json), 2)

    response = self.client.get(
        "/api/people/{}/{}s?id__in={}".format(user.id, job_type.lower(),
                                              ie1.id),
        headers=self.headers)
    self.assert200(response)
    self.assertEqual(response.json[0]["id"], ie1.id)

  def test_imports_put(self):
    """Test imports put"""
    user = all_models.Person.query.first()
    ie1 = factories.ImportExportFactory(job_type="Import",
                                        status="Not Started",
                                        created_by=user,
                                        created_at=datetime.now())
    with mock.patch("ggrc.views.converters.run_background_import"):
      response = self.client.put(
          "/api/people/{}/imports/{}/start".format(user.id, ie1.id),
          headers=self.headers
      )
    self.assert200(response)
    self.assertEqual(response.json["id"], ie1.id)
    self.assertEqual(response.json["status"], "Analysis")

  def test_imports_get_all(self):
    """Test imports get all items"""
    user = all_models.Person.query.first()
    factories.ImportExportFactory(job_type="Import",
                                  status="Finished",
                                  created_by=user,
                                  created_at=datetime.now())
    response = self.api.client.get(
        "/api/people/{}/imports".format(user.id),
        headers=self.headers
    )
    result = json.loads(response.data)
    self.assertEqual(len(result), 1)
    self.assertEqual(set(all_models.ImportExport.DEFAULT_COLUMNS),
                     set(result[0].keys()))

  def test_imports_get_by_id(self):
    """Test imports get item by id"""
    user = all_models.Person.query.first()
    import_job = factories.ImportExportFactory(
        job_type="Import",
        status="Finished",
        created_by=user,
        created_at=datetime.now()
    )
    response = self.api.client.get(
        "/api/people/{}/imports/{}".format(user.id, import_job.id),
        headers=self.headers
    )
    result = json.loads(response.data)
    observed_columns = set(result.keys())
    expected_columns = set(
        column.name for column in all_models.ImportExport.__table__.columns
        if column.name not in ('content', 'gdrive_metadata')
    )
    self.assertEqual(observed_columns, expected_columns)

  @ddt.data("Import", "Export")
  def test_delete(self, job_type):
    """Test imports/exports delete"""
    user = all_models.Person.query.first()
    ie1 = factories.ImportExportFactory(job_type=job_type,
                                        created_by=user,
                                        created_at=datetime.now())

    response = self.client.delete(
        "/api/people/{}/{}s/{}".format(user.id, job_type.lower(), ie1.id),
        headers=self.headers)
    self.assert200(response)
    self.assertIsNone(all_models.ImportExport.query.get(ie1.id))

  def test_exports_post(self):
    """Test exports post"""
    user = all_models.Person.query.first()
    assessment = factories.AssessmentFactory()
    response = self.client.post(
        "/api/people/{}/exports".format(user.id),
        data=json.dumps({
            "objects": [{
                "object_name": "Assessment",
                "ids": [assessment.id]}],
            "current_time": str(datetime.now())}),
        headers=self.headers)
    self.assert200(response)

  @ddt.data("Import", "Export")
  def test_download(self, job_type):
    """Test imports/exports download"""
    user = all_models.Person.query.first()
    ie1 = factories.ImportExportFactory(
        job_type=job_type,
        status="Finished",
        created_at=datetime.now(),
        created_by=user,
        title="test.csv",
        content="test content")
    response = self.client.get(
        "/api/people/{}/{}s/{}/download?export_to=csv".format(
            user.id,
            job_type.lower(),
            ie1.id),
        headers=self.headers)
    self.assert200(response)
    self.assertEqual(response.data, "test content")

  @ddt.data(u'漢字.csv', u'фыв.csv', u'asd.csv')
  def test_download_unicode_filename(self, filename):
    """Test import history download unicode filename"""
    user = all_models.Person.query.first()
    import_export = factories.ImportExportFactory(
        job_type='Import',
        status='Finished',
        created_at=datetime.now(),
        created_by=user,
        title=filename,
        content='Test content'
    )
    response = self.client.get(
        "/api/people/{}/imports/{}/download?export_to=csv".format(
            user.id,
            import_export.id),
        headers=self.headers)
    self.assert200(response)
    self.assertEqual(response.data, "Test content")

  @ddt.data(r"\\\\test.csv",
            "test###.csv",
            '??test##.csv',
            '?test#.csv',
            r'\\filename?.csv',
            '??somenamea??.csv',
            r'!@##??\\.csv')
  def test_imports_with_spec_symbols(self, filename):
    """Test import with special symbols in file name"""
    with mock.patch("ggrc.gdrive.file_actions.get_gdrive_file_data",
                    new=lambda x: (x, None, filename)):
      user = all_models.Person.query.first()
      response = self.client.post(
          "/api/people/{}/imports".format(user.id),
          data=json.dumps([]),
          headers=self.headers)
      self.assert400(response)

  @ddt.data(("Import", "Analysis"),
            ("Export", "In Progress"))
  @ddt.unpack
  def test_import_stop(self, job_type, status):
    """Test import/export stop"""
    user = all_models.Person.query.first()
    ie1 = factories.ImportExportFactory(
        job_type=job_type,
        status=status,
        created_at=datetime.now(),
        created_by=user,
        title="test.csv",
        content="test content")
    response = self.client.put(
        "/api/people/{}/{}s/{}/stop".format(user.id,
                                            job_type.lower(),
                                            ie1.id),
        headers=self.headers)
    self.assert200(response)
    self.assertEqual(json.loads(response.data)["status"], "Stopped")

  def test_stop_export(self):
    """Test if exception raised when ImportExport has Stopped status."""
    with factories.single_commit():
      user = all_models.Person.query.first()
      ie_job = factories.ImportExportFactory(
          job_type="Export",
          status="Stopped",
          created_at=datetime.now(),
          created_by=user,
          title="test.csv",
          content="test content"
      )
      factories.ControlFactory()

    with self.assertRaises(exceptions.StoppedException):
      with helpers.logged_user(user):
        converters.make_export(
            [{
                "filters": {"expression": {}},
                "object_name": "Control"
            }],
            exportable_objects=[0],
            ie_job=ie_job,
        )

  @ddt.data(("Not Started", True),
            ("Blocked", True),
            ("Finished", False))
  @ddt.unpack
  @mock.patch("ggrc.gdrive.file_actions.get_gdrive_file_data",
              new=lambda x: (x, None, ''))
  def test_delete_previous_imports(self, status, should_be_none):
    """Test deletion of previous imports"""
    user = all_models.Person.query.first()
    ie_item = factories.ImportExportFactory(
        job_type="Import",
        status=status,
        created_at=datetime.now(),
        created_by=user).id

    response = self.client.post(
        "/api/people/{}/imports".format(user.id),
        data=json.dumps([]),
        headers=self.headers)

    self.assert200(response)
    if should_be_none:
      self.assertIsNone(all_models.ImportExport.query.get(ie_item))
    else:
      self.assertIsNotNone(all_models.ImportExport.query.get(ie_item))

    ie_item_in_progress = factories.ImportExportFactory(
        job_type="Import",
        status="In Progress",
        created_at=datetime.now(),
        created_by=user).id
    response = self.client.post(
        "/api/people/{}/imports".format(user.id),
        data=json.dumps([]),
        headers=self.headers)
    self.assert400(response)
    self.assertIsNotNone(all_models.ImportExport.query.get(
        ie_item_in_progress))

  @mock.patch(
      "ggrc.gdrive.file_actions.get_gdrive_file_data",
      new=lambda x: (x, None, '')
  )
  def test_import_control_revisions(self):
    """Test if new revisions created during import."""
    data = "Object type,,,\n" \
           "Control,Code*,Title*,Admin*,Assertions*\n" \
           ",,Test control,user@example.com,Privacy"

    user = all_models.Person.query.first()

    response = self.run_full_import(user, data)
    self.assert200(response)

    control = all_models.Control.query.filter_by(title="Test control").first()
    self.assertIsNotNone(control)
    revision_actions = db.session.query(all_models.Revision.action).filter(
        all_models.Revision.resource_type == "Control",
        all_models.Revision.resource_id == control.id
    )
    self.assertEqual({"created"}, {a[0] for a in revision_actions})

  @mock.patch(
      "ggrc.gdrive.file_actions.get_gdrive_file_data",
      new=lambda x: (x, None, '')
  )
  def test_import_snapshot(self):
    """Test if snapshots can be created from imported objects."""
    data = "Object type,,,\n" \
           "Control,Code*,Title*,Admin*,Assertions*\n" \
           ",,Control1,user@example.com,Privacy\n" \
           ",,Control2,user@example.com,Privacy\n" \
           ",,Control3,user@example.com,Privacy"

    user = all_models.Person.query.first()

    response = self.run_full_import(user, data)
    self.assert200(response)

    controls = all_models.Control.query
    self.assertEqual(3, controls.count())

    audit = factories.AuditFactory()
    snapshots = self._create_snapshots(audit, controls.all())
    self.assertEqual(3, len(snapshots))

  def test_import_map_objectives(self):
    """Test import can't map assessments with objectives"""
    audit = factories.AuditFactory(slug='AUDIT-9999')
    audit_id = audit.id
    objectives = [
        factories.ObjectiveFactory(
            title='obj_999{}'.format(i),
            slug='OBJECTIVE-999{}'.format(i)
        ) for i in range(10)
    ]
    for objective in objectives:
      factories.RelationshipFactory(source=audit.program,
                                    destination=objective)

    response = self._import_file(
        'assessments_map_with_objectives_in_scope_of_program.csv', True
    )

    row_errors = {
        'Line 10: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 11: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 12: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 3: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 4: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 5: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 6: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 7: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 8: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.',
        'Line 9: You can not map Objective to Assessment, because '
        'this Objective is not mapped to the related audit.'
    }

    expected_messages = {
        'Assessment': {
            'created': 0,
            'row_errors': row_errors
        }
    }

    assessments = db.session.query(all_models.Assessment).filter_by(
        audit_id=audit_id).all()

    self.assertEqual(len(assessments), 0)
    self._check_csv_response(response, expected_messages)

    # update the audit to the latest version
    self.api.put(all_models.Audit.query.get(audit_id),
                 {'snapshots': {'operation': 'upsert'}}
                 )

    response = self._import_file('assessments_map_to_obj_snapshots.csv')

    expected_messages = {
        'Assessment': {
            'created': 10,
            'row_errors': set()
        }
    }

    assessments = db.session.query(all_models.Assessment).filter_by(
        audit_id=audit_id).all()

    self.assertEqual(len(assessments), 10)
    self._check_csv_response(response, expected_messages)
