# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Collection of utils for login and user generation.
"""
import datetime
import json
from email.utils import parseaddr
import flask
from werkzeug import exceptions

from sqlalchemy import orm

from ggrc import db, settings, login
from ggrc.integrations import client
from ggrc.login import get_current_user_id
from ggrc.models.person import Person
from ggrc.rbac import SystemWideRoles
from ggrc.utils import errors
from ggrc.utils.log_event import log_event
from ggrc_basic_permissions import basic_roles
from ggrc_basic_permissions.models import UserRole


def _base_user_query():
  return Person.query.options(
      orm.undefer_group('Person_complete'))


def find_user_by_id(user_id):
  """Find Person object by some ``id``.

  Note that ``id`` need not be Person().id, but should match the value
  returned by ``Person().get_id()``.
  """
  return _base_user_query().get(int(user_id))


def find_user_by_email(email):
  return _base_user_query().filter(Person.email == email).first()


def add_creator_role(user, **kwargs):
  """Add creator role for sent user."""
  if not hasattr(flask.g, "user_creator_roles_cache"):
    flask.g.user_creator_roles_cache = {}

  if user.email in flask.g.user_creator_roles_cache:
    # we have this role in the cache so no need to create it
    return

  user_creator_role = UserRole(
      person=user,
      role=basic_roles.creator(),
      **kwargs
  )
  flask.g.user_creator_roles_cache[user.email] = user_creator_role
  db.session.add(user_creator_role)


def create_user(email, **kwargs):
  """Creates a user.

  Args:
    email: (string) mandatory user email
  """
  if not hasattr(flask.g, "user_cache"):
    flask.g.user_cache = {}

  if email in flask.g.user_cache:
    return flask.g.user_cache[email]

  user = Person(email=email, **kwargs)
  flask.g.user_cache[email] = user
  db.session.add(user)
  return user


def create_users_with_role(email_names, role_name="Creator"):
  """Create Person objects.

  Args:
      email_names(dict): Dictionary containing email and name of users.
        Format: {<email>:<name>}

  Returns:
      Set with created Person objects.
  """
  if not email_names:
    return {}

  now = datetime.datetime.now()
  current_user = login.get_current_user()
  from ggrc.models import all_models
  person_inserter = all_models.Person.__table__.insert().prefix_with("IGNORE")
  db.session.execute(
      person_inserter.values([
          {
              "modified_by_id": current_user.id,
              "created_at": now,
              "updated_at": now,
              "email": email,
              "name": name,
          }
          for email, name in email_names.items()
      ])
  )

  created_people = set(load_people_with_emails(email_names.keys()))

  role_id = basic_roles._find_basic(role_name).id
  ur_inserter = all_models.UserRole.__table__.insert().prefix_with("IGNORE")
  db.session.execute(
      ur_inserter.values([
          {
              "modified_by_id": current_user.id,
              "created_at": now,
              "updated_at": now,
              "role_id": role_id,
              "person_id": person.id,
          }
          for person in created_people
      ])
  )
  return created_people


def load_people_with_emails(emails):
  """Load people with provided emails from db.

  Args:
      emails(list): Collection of user emails.

  Returns:
      Set of Person objects.
  """
  if not emails:
    return {}

  from ggrc.models import all_models
  result = db.session.query(
      all_models.Person
  ).filter(
      all_models.Person.email.in_(emails)
  ).options(orm.load_only("id", "name", "email"))
  return set(result.all())


def is_authorized_domain(email):
  """Check whether user's email belongs to authorized domain"""
  # Email can have multiple @, but last one separates local and domain part
  user_domain = email.split("@")[-1]
  return user_domain.lower() == settings.AUTHORIZED_DOMAIN.lower()


def find_or_create_user_by_email(email, name, modifier=None):
  """Generates or find user for selected email."""
  user = find_user_by_email(email)
  if not user:
    _, app_email = parseaddr(settings.EXTERNAL_APP_USER)

    if not modifier and email != app_email:
      modifier = get_current_user_id()
    user = create_user(email, name=name, modified_by_id=modifier)
  if is_authorized_domain(email) and \
     user.system_wide_role == SystemWideRoles.NO_ACCESS:
    add_creator_role(user, modified_by_id=modifier)
  return user


def search_user(email):
  """Search user by Integration Service

  Returns:
    string: user name for success, None otherwise
  """
  service = client.PersonClient()
  if is_authorized_domain(email):
    username = email.split("@")[0]
    ldaps = service.search_persons([username])
    if ldaps and ldaps[0]["username"] == username:
      return "%s %s" % (ldaps[0]["firstName"], ldaps[0]["lastName"])
  return None


def find_or_create_external_user(email, name):
  """Find or generate user after verification"""
  if is_external_app_user_email(email):
    return find_or_create_ext_app_user()

  if settings.INTEGRATION_SERVICE_URL == 'mock':
    return find_or_create_user_by_email(email, name)

  if settings.INTEGRATION_SERVICE_URL and search_user(email):
    return find_or_create_user_by_email(email, name)
  return None


def find_or_create_ext_app_user():
  """Find or generate external application user."""
  name, email = parseaddr(settings.EXTERNAL_APP_USER)
  user = find_user_by_email(email)
  if not user:
    user = create_user(email, name=name)
  return user


def parse_user_email(request, header, mandatory):
  """Parses a user email from the request header.

  Retrieves user email from the request header and
  validates it based on being mandatory or not.

  Args:
      request: the original request.
      header: a header name with a person email.
      mandatory: flag that header value is mandatory or not.

  Returns:
      A parsed user email.

  Raises:
     BadRequest: Raised when validation on email has failed.
  """
  user = request.headers.get(header)
  if mandatory and not user:
    raise exceptions.BadRequest(
        errors.MANDATORY_HEADER.format(header, user))
  if not user:
    return None
  try:
    user = json.loads(user)
    email = str(user["email"])
  except (TypeError, ValueError, KeyError):
    raise exceptions.BadRequest(
        errors.WRONG_PERSON_HEADER_FORMAT.format(header, user))
  if '@' not in parseaddr(email)[1]:
    raise exceptions.BadRequest(
        errors.WRONG_PERSON_HEADER_FORMAT.format(header, user))
  return email


def find_user(email, modifier=None):
  """Find or generate user.

  If Integration Server is specified not found in DB user is generated
  with Creator role.
  """
  if is_external_app_user_email(email):
    return find_or_create_ext_app_user()

  if settings.INTEGRATION_SERVICE_URL == 'mock':
    return find_or_create_user_by_email(email, email, modifier)

  if settings.INTEGRATION_SERVICE_URL:
    name = search_user(email)
    if not name:
      return None
    return find_or_create_user_by_email(email, name, modifier)
  return find_user_by_email(email)


def find_users(emails):
  """Find or generate user.

  If Integration Server is specified not found in DB user is generated
  with Creator role.
  """
  # pylint: disable=too-many-locals
  if not settings.INTEGRATION_SERVICE_URL:
    return Person.query.filter(Person.email.in_(emails)).options(
        orm.undefer_group('Person_complete')).all()

  # Verify emails
  usernames = [email.split('@')[0] for email in emails
               if is_authorized_domain(email) and
               not is_external_app_user_email(email)]

  service = client.PersonClient()
  ldaps = service.search_persons(usernames)

  authorized_domain = getattr(settings, "AUTHORIZED_DOMAIN", "")
  verified_emails = {'%s@%s' % (ldap['username'], authorized_domain)
                     for ldap in ldaps}

  # Find users in db
  users = Person.query.filter(Person.email.in_(emails)).all()
  found_emails = {user.email for user in users}

  # Create new users
  new_emails = verified_emails - found_emails
  new_usernames = [email.split('@')[0] for email in new_emails]
  new_users = [('%s@%s' % (ldap['username'], authorized_domain),
                '%s %s' % (ldap['firstName'], ldap['lastName']))
               for ldap in ldaps if ldap['username'] in new_usernames]

  for email, name in new_users:
    user = create_user(email,
                       name=name,
                       modified_by_id=get_current_user_id())
    users.append(user)

  # bulk create people
  if new_users:
    log_event(db.session)
    db.session.commit()

  creator_role_granted = False
  # Grant Creator role to all users
  for user in users:
    if user.system_wide_role == SystemWideRoles.NO_ACCESS:
      add_creator_role(user)
      creator_role_granted = True

  # bulk create people roles
  if creator_role_granted:
    log_event(db.session)
    db.session.commit()

  return users


def is_external_app_user_email(email):
  """Checks if given user email belongs to external application.

  Args:
    email: A string email address of the user.
  """
  if not settings.EXTERNAL_APP_USER:
    return False

  _, external_app_user_email = parseaddr(settings.EXTERNAL_APP_USER)
  if not external_app_user_email:
    return False

  return external_app_user_email == email
