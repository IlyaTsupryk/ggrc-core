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

from ggrc.models import all_models

from integration.ggrc import api_helper
from integration.ggrc.models import factories
from integration.ggrc.services import TestCase


@ddt.ddt
class TestImportExports(TestCase):
  """Tests for imports/exports endpoints."""

  def setUp(self):
    super(TestImportExports, self).setUp()
    self.client.get("/login")
    self.headers = {
        "Content-Type": "application/json",
        "X-Requested-By": ["GGRC"],
    }
    self.api = api_helper.Api()
    self.init_taskqueue()

  @mock.patch("ggrc.gdrive.file_actions.get_gdrive_file_data",
              new=lambda x: (x, None, None))
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
              new=lambda x: (x, None, None))
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
    response = self.client.put(
        "/api/people/{}/imports/{}/start".format(user.id, ie1.id),
        headers=self.headers)
    self.assert200(response)
    self.assertEqual(response.json["id"], ie1.id)
    self.assertEqual(response.json["status"], "Analysis")

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
        status='Finished',
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
