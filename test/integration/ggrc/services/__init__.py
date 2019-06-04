# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

import random

from sqlalchemy.orm import validates

import ggrc
import ggrc.builder
import ggrc.services
from ggrc import db
from ggrc.models import all_models
from ggrc.models.mixins import base
from ggrc.models.mixins import Base
from ggrc.models import reflection
from ggrc.models.exceptions import ValidationError
from ggrc.models.person import Person
from ggrc.models.person_profile import PersonProfile, default_last_seen_date
from ggrc.services.common import Resource
from integration.ggrc import TestCase as BaseTestCase


def reset_first_request_flag():
  """Reset GGRC app _got_first_request flag to allow endpoint registering.

  This function is required for the case where another test suite runs before
  this module gets imported.
  """
  # pylint: disable=protected-access
  ggrc.app.app._got_first_request = False


class ServicesTestMockModel(base.ContextRBAC, Base, db.Model):
  __tablename__ = 'test_model'
  foo = db.Column(db.String)
  code = db.Column(db.String, unique=True)
  validated = db.Column(db.String, nullable=True)

  @validates('validated')
  def validate_status(self, key, value):
    if value == "Value Error":
      raise ValueError("raised Value Error")
    elif value == "Validation Error":
      raise ValidationError("raised Validation Error")
    return value

  # REST properties
  _api_attrs = reflection.ApiAttributes(
      reflection.Attribute('modified_by_id', create=False, update=False),
      'foo',
      'code',
      'validated',
  )


URL_MOCK_COLLECTION = '/api/mock_resources'
URL_MOCK_RESOURCE = '/api/mock_resources/{0}'

reset_first_request_flag()
Resource.add_to(
    ggrc.app.app, URL_MOCK_COLLECTION, model_class=ServicesTestMockModel)


all_models.all_models.append(ServicesTestMockModel)


class TestCase(BaseTestCase):

  def setUp(self):
    super(TestCase, self).setUp()
    # Explicitly create test tables
    if not ServicesTestMockModel.__table__.exists(db.engine):
      ServicesTestMockModel.__table__.create(db.engine)
    with self.client.session_transaction() as session:
      session['permissions'] = {
          "__GGRC_ADMIN__": {"__GGRC_ALL__": {"contexts": [0]}}
      }

  def tearDown(self):
    super(TestCase, self).tearDown()
    # Explicitly destroy test tables
    # Note: This must be after the 'super()', because the session is
    #   closed there.  (And otherwise it might stall due to locks).
    if ServicesTestMockModel.__table__.exists(db.engine):
      ServicesTestMockModel.__table__.drop(db.engine)

  def mock_url(self, resource=None):
    if resource is not None:
      return URL_MOCK_RESOURCE.format(resource)
    return URL_MOCK_COLLECTION

  def mock_json(self, model):
    format = '%Y-%m-%dT%H:%M:%S'
    updated_at = unicode(model.updated_at.strftime(format))
    created_at = unicode(model.created_at.strftime(format))
    return {
        u'id': int(model.id),
        u'selfLink': unicode(URL_MOCK_RESOURCE.format(model.id)),
        u'type': unicode(model.__class__.__name__),
        u'modified_by': {
            u'href': u'/api/people/1',
            u'id': model.modified_by_id,
            u'type': 'Person',
            u'context_id': None
        } if model.modified_by_id is not None else None,
        u'modified_by_id': int(model.modified_by_id),
        u'updated_at': updated_at,
        u'created_at': created_at,
        u'context':
            {u'id': model.context_id}
            if model.context_id is not None else None,
        u'foo': (unicode(model.foo) if model.foo else None),
    }

  def mock_model(self, id=None, modified_by_id=1, **kwarg):
    if 'id' not in kwarg:
      kwarg['id'] = random.randint(0, 999999999)
    if 'modified_by_id' not in kwarg:
      kwarg['modified_by_id'] = 1
    mock = ServicesTestMockModel(**kwarg)
    ggrc.db.session.add(mock)
    ggrc.db.session.commit()
    return mock

  def assert_acp_created(self, acp_person_ids):
    ac_people = all_models.AccessControlPerson.query.filter(
        all_models.AccessControlPerson.person_id.in_((acp_person_ids))
    ).all()
    self.assertEqual(len(ac_people), len(acp_person_ids))

  def assert_person_profile_created(self, emails):
    """Checks profile was created successfully for listed users"""
    for email in emails:
      profile = PersonProfile.query.join(PersonProfile.person).filter_by(
          email=email).one()
      self.assertEqual(profile.last_seen_whats_new, default_last_seen_date())

  def assert_profiles_restrictions(self):
    """Checks restrictions imposed on people and people_profiles tables

    We have 0 or 1 to 1 relationship, and people_profiles should be equal to
    people inner join people_profiles (all existing profiles should be
    attached to appropriate person)
    """
    profiles_count = PersonProfile.query.count()
    join_count = Person.query.join(Person.profile).count()
    self.assertEqual(profiles_count, join_count)
