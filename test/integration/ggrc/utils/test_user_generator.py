# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Tests for user generator"""

from collections import OrderedDict

import json
import ddt
import mock
from freezegun import freeze_time

from ggrc.converters import errors
from ggrc.integrations.client import PersonClient
from ggrc.models import all_models
from ggrc.models import Assessment
from ggrc.models import AssessmentTemplate
from ggrc.models import Audit
from ggrc.models import Person
from ggrc_basic_permissions.models import UserRole

from integration.ggrc.services import TestCase
from integration.ggrc.models import factories

from integration.ggrc.api_helper import Api


@ddt.ddt
class TestUserGenerator(TestCase):
  """Test user generation."""

  def setUp(self):
    super(TestUserGenerator, self).setUp()
    self.clear_data()
    self.client.get("/login")
    self.api = Api()

  def _post(self, data):
    return self.client.post(
        '/api/people',
        content_type='application/json',
        data=data,
        headers=[('X-Requested-By', 'Unit Tests')],
    )

  @staticmethod
  def _mock_post(*args, **kwargs):
    """Mock of IntegrationService _post"""
    # pylint: disable=unused-argument
    payload = kwargs["payload"]
    res = []
    for name in payload["usernames"]:
      res.append({'firstName': name,
                  'lastName': name,
                  'username': name})
    return {'persons': res}

  @mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
  @mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='example.com')
  @freeze_time("2018-05-21 10:28:34")
  def test_users_generation(self):
    """Test user generation."""
    with mock.patch.multiple(PersonClient, _post=self._mock_post):
      data = json.dumps([
          {'person': {
              'name': 'Alan Turing',
              'email': 'aturing@example.com',
              'context': None,
              'external': True
          }},
          {'person': {
              'name': 'Alan Turing 2',
              'email': 'aturing2@example.com',
              'context': None,
              'external': True
          }},
          {'person': {
              'name': 'Alan Turing 3',
              'email': 'aturing_3@example.com',
              'context': None,
              'external': True
          }}
      ])
      response = self._post(data)
      self.assertStatus(response, 200)

      user = Person.query.filter_by(email='aturing@example.com').one()
      self.assertEqual(user.name, 'Alan Turing')

      roles = UserRole.query.filter_by(person_id=user.id)
      self.assertEqual(roles.count(), 1)
      self.assertEqual(response.json[0][1]['person']['id'], user.id)

    # checks person profile was created successfully
    self.assert_profiles_restrictions()
    emails = ['aturing@example.com', ]
    self.assert_person_profile_created(emails)
    self.assertEqual(all_models.Event.query.count(), 1)

  @mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
  @mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='example.com')
  @freeze_time("2018-05-21 10:28:34")
  def test_user_generation(self):
    """Test user generation."""
    with mock.patch.multiple(
        PersonClient,
        _post=self._mock_post
    ):
      data = json.dumps([{'person': {
          'name': 'Alan Turing',
          'email': 'aturing@example.com',
          'context': None,
          'external': True
      }}])
      response = self._post(data)
      self.assertStatus(response, 200)

      user = Person.query.filter_by(email='aturing@example.com').one()
      self.assertEqual(user.name, 'Alan Turing')

      roles = UserRole.query.filter_by(person_id=user.id)
      self.assertEqual(roles.count(), 1)

    # checks person profile was created successfully
    emails = ['aturing@example.com', ]
    self.assert_person_profile_created(emails)
    self.assert_profiles_restrictions()

  @mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
  @mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='example.com')
  @freeze_time("2018-05-21 10:26:34")
  def test_user_creation(self):
    """Test user creation."""
    with mock.patch.multiple(
        PersonClient,
        _post=self._mock_post
    ):
      data = json.dumps([{'person': {
          'name': 'Alan Turing',
          'email': 'aturing@example.com',
          'context': None
      }}])
      response = self._post(data)
      self.assertStatus(response, 200)

      user = Person.query.filter_by(email='aturing@example.com').one()
      self.assertEqual(user.name, 'Alan Turing')

      roles = UserRole.query.filter_by(person_id=user.id)
      self.assertEqual(roles.count(), 0)

    # checks person profile was created successfully
    emails = ['aturing@example.com', ]
    cur_user = Person.query.filter_by(email='user@example.com').one()
    acp_person_ids = [user.id, cur_user.id]

    self.assert_person_profile_created(emails)
    self.assert_profiles_restrictions()
    self.assert_acp_created(acp_person_ids)

  @mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
  @mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='example.com')
  @freeze_time("2018-05-21 10:26:34")
  def test_people_profiles_api(self):
    """Test people_profiles api after person creation."""
    with mock.patch.multiple(
        PersonClient,
        _post=self._mock_post
    ):
      data = json.dumps([{'person': {
          'name': 'Alan Turing',
          'email': 'aturing@example.com',
          'context': None
      }}])
      response = self._post(data)
      self.assertStatus(response, 200)

    api_response = self.api.client.get("/api/people_profiles")

    cur_user = Person.query.filter_by(email='user@example.com').one()
    user = Person.query.filter_by(email='aturing@example.com').one()
    acp_person_ids = [user.id, cur_user.id]
    response_ids = list(
        [
            pepson_profile['id'] for pepson_profile in
            api_response.json['people_profiles_collection']['people_profiles']
        ]
    )
    self.assertItemsEqual(acp_person_ids, response_ids)

  @mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
  @mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='example.com')
  def test_wrong_user_creation(self):
    """Test wrong user creation."""
    with mock.patch.multiple(
        PersonClient,
        _post=mock.MagicMock(return_value={'persons': []})
    ):
      data = json.dumps([{'person': {
          'name': 'Alan Turing',
          'email': 'aturing@example.com',
          'context': None,
          'external': True
      }}])
      response = self._post(data)
      self.assertStatus(response, 400)

      user = Person.query.filter_by(email='aturing@example.com').first()
      self.assertIsNone(user)

    # checks person profile restrictions
    self.assert_profiles_restrictions()

  @mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
  @mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='example.com')
  @freeze_time("2018-05-20 10:22:22")
  def test_person_import(self):
    """Test for mapped person"""
    with mock.patch.multiple(
        PersonClient,
        _post=self._mock_post
    ):
      program = factories.ProgramFactory()
      audit_slug = 'Audit1'
      self.import_data(OrderedDict([
          ("object_type", "Audit"),
          ("Code*", audit_slug),
          ("Program*", program.slug),
          ("Auditors", "cbabbage@example.com"),
          ("Title", "Title"),
          ("State", "Planned"),
          ("Audit Captains", "aturing@example.com")
      ]))
      audit = Audit.query.filter(Audit.slug == audit_slug).first()
      auditors = [person.email for person, acl in audit.access_control_list
                  if acl.ac_role.name == "Auditors"]
      captains = [person.email for person, acl in audit.access_control_list
                  if acl.ac_role.name == "Audit Captains"]
      self.assertItemsEqual(["cbabbage@example.com"], auditors)
      self.assertItemsEqual(["aturing@example.com"], captains)

      assessment_slug = "Assessment1"
      self.import_data(OrderedDict([
          ("object_type", "Assessment"),
          ("Code*", assessment_slug),
          ("Audit*", audit.slug),
          ("Creators*", "aturing@example.com"),
          ("Assignees*", "aturing@example.com"),
          ("Secondary Contacts", "cbabbage@example.com"),
          ("Title", "Title")
      ]))
      assessment = Assessment.query.filter(
          Assessment.slug == assessment_slug).first()
      creators_acl = assessment.acr_name_acl_map["Creators"]
      creators = [
          acp.person.email
          for acp in creators_acl.access_control_people
      ]
      contacts_acl = assessment.acr_name_acl_map["Secondary Contacts"]
      secondary_contacts = [
          acp.person.email
          for acp in contacts_acl.access_control_people
      ]
      self.assertIn("aturing@example.com", creators)
      self.assertEqual("cbabbage@example.com", secondary_contacts[0])

      # checks person profile was created successfully
      emails = ["aturing@example.com", "cbabbage@example.com"]
      self.assert_person_profile_created(emails)
      self.assert_profiles_restrictions()

  @mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
  @mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='example.com')
  @freeze_time("2018-05-20 08:22:22")
  def test_persons_import(self):
    """Test for mapped persons"""
    with mock.patch.multiple(
        PersonClient,
        _post=self._mock_post
    ):
      audit = factories.AuditFactory()

      slug = "AssessmentTemplate1"
      response = self.import_data(OrderedDict([
          ("object_type", "Assessment_Template"),
          ("Code*", slug),
          ("Audit*", audit.slug),
          ("Default Assignees", "aturing@example.com"),
          ("Default Verifiers", "aturing@example.com\ncbabbage@example.com"),
          ("Title", "Title"),
          ("Object Under Assessment", 'Control'),
      ]))
      self._check_csv_response(response, {})
      assessment_template = AssessmentTemplate.query.filter(
          AssessmentTemplate.slug == slug).first()

      self.assertEqual(len(assessment_template.default_people['verifiers']), 2)
      self.assertEqual(len(assessment_template.default_people['assignees']), 1)

    # checks person profile was created successfully
    emails = ["aturing@example.com", "cbabbage@example.com"]
    self.assert_person_profile_created(emails)
    self.assert_profiles_restrictions()

  @mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
  @mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='example.com')
  @freeze_time("2018-05-30 12:58:22")
  def test_import_no_assignees(self):
    """Test for import assessment template without default assignees"""
    with mock.patch.multiple(
        PersonClient,
        _post=self._mock_post
    ):
      audit = factories.AuditFactory()

      slug = "AssessmentTemplate1"
      response = self.import_data(OrderedDict([
          ("object_type", "Assessment_Template"),
          ("Code*", slug),
          ("Audit*", audit.slug),
          ("Default Verifiers", "aturing@example.com"),
          ("Title", "Title"),
          ("Object Under Assessment", 'Control'),
      ]))
      self._check_csv_response(
          response,
          {"Assessment Template": {
              "row_errors": {errors.MISSING_COLUMN.format(
                  line=3, column_names="Default Assignees", s="")}}})

    # checks person profile was created successfully
    emails = ["aturing@example.com", ]
    self.assert_person_profile_created(emails)
    self.assert_profiles_restrictions()

  @mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
  @mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='example.com')
  @freeze_time("2018-05-30 12:56:17")
  def test_import_empty_assignees(self):
    """Test for import assessment template with empty default assignees"""
    with mock.patch.multiple(
        PersonClient,
        _post=self._mock_post
    ):
      audit = factories.AuditFactory()

      slug = "AssessmentTemplate1"
      response = self.import_data(OrderedDict([
          ("object_type", "Assessment_Template"),
          ("Code*", slug),
          ("Audit*", audit.slug),
          ("Default Assignees", ""),
          ("Default Verifiers", "aturing@example.com"),
          ("Title", "Title"),
          ("Object Under Assessment", 'Control'),
      ]))
      self._check_csv_response(
          response,
          {"Assessment Template": {
              "row_errors": {errors.WRONG_REQUIRED_VALUE.format(
                  line=3, value="", column_name="Default Assignees")}}})

    # checks person profile was created successfully
    emails = ["aturing@example.com", ]
    self.assert_person_profile_created(emails)
    self.assert_profiles_restrictions()

  @mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
  @mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='example.com')
  @freeze_time("2018-05-21 01:11:11")
  def test_wrong_person_import(self):
    """Test for wrong person import"""
    with mock.patch.multiple(
        PersonClient,
        _post=mock.MagicMock(return_value={'persons': [{
            'firstName': "Alan",
            'lastName': 'Turing',
            'username': "aturing"}]})
    ):
      audit = factories.AuditFactory()
      slug = "AssessmentTemplate1"
      response = self.import_data(OrderedDict([
          ("object_type", "Assessment_Template"),
          ("Code*", slug),
          ("Audit*", audit.slug),
          ("Default Assignees", "aturing@example.com"),
          ("Default Verifiers", "aturing@example.com\ncbabbage@example.com"),
          ("Title", "Title"),
          ("Object Under Assessment", 'Control'),
      ]))
      self._check_csv_response(
          response,
          {"Assessment Template": {
              "row_warnings": {errors.UNKNOWN_USER_WARNING.format(
                  line=3, email="cbabbage@example.com")}}})

    # checks person profile was created successfully
    emails = ["aturing@example.com", ]
    self.assert_person_profile_created(emails)
    self.assert_profiles_restrictions()

  @mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
  @mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='example.com')
  @freeze_time("2018-05-30 02:22:11")
  @ddt.data(('aturing@example.com', 'aturing@example.com'),
            ('', 'aturing@example.com'),
            ('aturing@example.com', ''),
            ('aturing@example.com', '--'))
  @ddt.unpack
  def test_verifier_import(self, assignee_email, verifier_email):
    """Test for verifiers import"""
    with mock.patch.multiple(
        PersonClient,
        _post=mock.MagicMock(return_value={'persons': [{
            'firstName': 'Alan',
            'lastName': 'Turing',
            'username': 'aturing'}]})
    ):
      audit = factories.AuditFactory()
      slug = 'AssessmentTemplate1'
      response = self.import_data(OrderedDict([
          ('object_type', 'Assessment_Template'),
          ('Code*', slug),
          ('Audit*', audit.slug),
          ('Default Assignees', assignee_email),
          ('Default Verifiers', verifier_email),
          ('Title', 'Title'),
          ('Object Under Assessment', 'Control'),
      ]))
      assessment_template = AssessmentTemplate.query.filter(
          AssessmentTemplate.slug == slug).first()

      if assignee_email:
        self._check_csv_response(response, {})
        self.assertEqual(
            len(assessment_template.default_people['assignees']), 1)
        if verifier_email and verifier_email != '--':
          self.assertEqual(
              len(assessment_template.default_people['verifiers']), 1)
        else:
          self.assertEqual(
              assessment_template.default_people['verifiers'], None)
      else:
        self._check_csv_response(
            response, {
                'Assessment Template': {
                    'row_errors': {
                        errors.WRONG_REQUIRED_VALUE.format(
                            line=3, value=assignee_email,
                            column_name='Default Assignees')
                    }
                }
            }
        )
    # checks person profile was created successfully
    emails = ["aturing@example.com", ]
    self.assert_person_profile_created(emails)
    self.assert_profiles_restrictions()

  @mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
  @mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='example.com')
  @freeze_time("2018-05-30 02:22:11")
  @ddt.data('--', '')
  def test_import_template_update(self, verifier_update_email):
    """Test for template update via import."""
    with mock.patch.multiple(
        PersonClient,
        _post=self._mock_post
    ):
      audit = factories.AuditFactory()
      slug = 'AssessmentTemplate1'
      response = self.import_data(OrderedDict([
          ('object_type', 'Assessment_Template'),
          ('Code*', slug),
          ('Audit*', audit.slug),
          ('Default Assignees', 'aturing@example.com'),
          ('Default Verifiers', 'aturing@example.com'),
          ('Title', 'Title'),
          ('Object Under Assessment', 'Control'),
      ]))
      imported_template = AssessmentTemplate.query.filter(
          AssessmentTemplate.slug == slug).first()
      self._check_csv_response(response, {})
      self.assertEqual(len(imported_template.default_people['verifiers']), 1)

      response = self.import_data(OrderedDict([
          ('object_type', 'Assessment_Template'),
          ('Code*', slug),
          ('Audit*', audit.slug),
          ('Default Assignees', 'aturing2@example.com'),
          ('Default Verifiers', verifier_update_email),
          ('Title', 'Title'),
          ('Object Under Assessment', 'Control'),
      ]))
      updated_template = AssessmentTemplate.query.filter(
          AssessmentTemplate.slug == slug).first()
      self._check_csv_response(response, {})
      self.assertNotEqual(updated_template.default_people['assignees'],
                          imported_template.default_people['assignees'])
      if not verifier_update_email:
        self.assertEqual(len(updated_template.default_people['verifiers']), 1)
      if verifier_update_email == "--":
        self.assertEqual(updated_template.default_people['verifiers'], None)

  @mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
  @mock.patch('ggrc.settings.AUTHORIZED_DOMAIN', new='example.com')
  @freeze_time("2018-04-30 02:22:11")
  def test_assignee_import(self):
    """Test for verifiers import"""
    with mock.patch.multiple(
        PersonClient,
        _post=mock.MagicMock(return_value={'persons': [{
            'firstName': 'Alan',
            'lastName': 'Turing',
            'username': 'aturing'}]})
    ):
      audit = factories.AuditFactory()
      slug = 'AssessmentTemplate1'
      response = self.import_data(OrderedDict([
          ('object_type', 'Assessment_Template'),
          ('Code*', slug),
          ('Audit*', audit.slug),
          ('Default Assignees', 'aturing@example.com'),
          ('Title', 'Title'),
          ('Object Under Assessment', 'Control'),
      ]))
      assessment_template = AssessmentTemplate.query.filter(
          AssessmentTemplate.slug == slug).first()

      self._check_csv_response(response, {})
      self.assertEqual(len(assessment_template.default_people['assignees']), 1)

    # checks person profile was created successfully
    emails = ["aturing@example.com", ]
    self.assert_person_profile_created(emails)
    self.assert_profiles_restrictions()

  @mock.patch('ggrc.settings.INTEGRATION_SERVICE_URL', new='endpoint')
  @mock.patch('ggrc.utils.user_generator.search_user', return_value='user')
  def test_invalid_email_import(self, _):
    """Test import of invalid email."""
    wrong_email = "some wrong email"
    audit = factories.AuditFactory()

    response = self.import_data(OrderedDict([
        ("object_type", "Assessment"),
        ("Code*", "Test Assessment"),
        ("Audit*", audit.slug),
        ("Assignees*", wrong_email),
        ("Title", "Some title"),
    ]))
    expected_errors = {
        "Assessment": {
            "row_errors": {
                errors.VALIDATION_ERROR.format(
                    line=3,
                    column_name="Assignees",
                    message="Email address '{}' is invalid."
                            " Valid email must be provided".format(wrong_email)
                )
            },
            "row_warnings": {
                errors.UNKNOWN_USER_WARNING.format(
                    line=3, email=wrong_email
                ),
                errors.OWNER_MISSING.format(
                    line=3, column_name="Assignees"
                ),
            }
        }
    }
    self._check_csv_response(response, expected_errors)

    # checks person profile restrictions
    self.assert_profiles_restrictions()
