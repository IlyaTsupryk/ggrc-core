# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for user notifying in case of import/export crash."""
import mock
import json
from datetime import datetime

from ggrc.models import all_models
from ggrc.notifications import import_export, job_emails
from integration.ggrc import TestCase
from integration.ggrc.models import factories


class TestImportExportNotify(TestCase):
  """Test class for user notifying in case of import/export crash."""

  def setUp(self):
    super(TestImportExportNotify, self).setUp()
    self.client.get("/login")

    self.cloud_tasks = {
        "tasks": [
            {
                "name": "projects/instance/locations/us-central1/queues/"
                        "ggrcImport/tasks/some_import",
            },
            {
                "name": "projects/instance/locations/us-central1/queues/"
                        "ggrcImport/tasks/some_export",
            },
        ]
    }

  def run_real_import(self, user):
    """Run import of test data through the /api/people/{}/imports endpoint."""
    data = "Object type,,,\n" \
           "Control,Code*,Title*,Admin*,Assertions*\n" \
           ",,Test control,user@example.com,Privacy"

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

  def run_real_export(self, user):
    """Run export of test data through the /api/people/{}/exports endpoint."""
    assessment = factories.AssessmentFactory()
    with mock.patch("ggrc.views.converters.check_for_previous_run"):
      return self.client.post(
          "/api/people/{}/exports".format(user.id),
          data=json.dumps({
              "objects": [{
                  "object_name": "Assessment",
                  "ids": [assessment.id]}],
              "current_time": str(datetime.now())}),
          headers=self.headers
      )

  def test_export_notifications(self):
    """Test if proper notification is sent when export crashed."""
    user = all_models.Person.query.filter_by(email="user@example.com").first()
    user_email = user.email
    with mock.patch(
        "ggrc.views.converters.make_export",
        side_effect=SystemExit("Some unexpected issue")
    ):
      self.run_real_export(user)

    imp_exp = all_models.ImportExport.query.one()
    self.assertEqual(
        imp_exp.status,
        all_models.ImportExport.IN_PROGRESS_STATUS
    )

    with mock.patch(
        "ggrc.cloud_api.task_queue.request_taskqueue_data",
        return_value=self.cloud_tasks
    ):
      with mock.patch("ggrc.notifications.common.send_email") as send_mock:
        import_export.check_import_export_jobs()

    self.assertEqual(send_mock.call_count, 1)
    (receiver, subject, body), _ = send_mock.call_args_list[0]
    self.assertEqual(receiver, user_email)
    self.assertEqual(job_emails.EXPORT_CRASHED["title"], subject)
    self.assertIn(job_emails.EXPORT_CRASHED["body"], body)

    imp_exp = all_models.ImportExport.query.one()
    self.assertEqual(
        imp_exp.status,
        all_models.ImportExport.FAILED_STATUS
    )

  def test_import_notifications(self):
    """Test if proper notification is sent when import crashed."""
    user = all_models.Person.query.filter_by(email="user@example.com").first()
    user_email = user.email
    with mock.patch(
        "ggrc.views.converters.make_import",
        side_effect=SystemExit("Some unexpected issue")
    ):
      self.run_real_import(user)

    imp_exp = all_models.ImportExport.query.one()
    self.assertEqual(
        imp_exp.status,
        all_models.ImportExport.IN_PROGRESS_STATUS
    )

    with mock.patch(
        "ggrc.cloud_api.task_queue.request_taskqueue_data",
        return_value=self.cloud_tasks
    ):
      with mock.patch("ggrc.notifications.common.send_email") as send_mock:
        import_export.check_import_export_jobs()

    self.assertEqual(send_mock.call_count, 1)
    (receiver, subject, body), _ = send_mock.call_args_list[0]
    self.assertEqual(receiver, user_email)

    imp_exp = all_models.ImportExport.query.one()
    expected_subject = job_emails.IMPORT_FAILED["title"].format(
        filename=imp_exp.title
    )
    self.assertEqual(expected_subject, subject)
    self.assertIn(job_emails.IMPORT_FAILED["body"], body)
    self.assertEqual(
        imp_exp.status,
        all_models.ImportExport.FAILED_STATUS
    )
