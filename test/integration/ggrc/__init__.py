# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Base test case for all ggrc integration tests."""
from collections import defaultdict
import contextlib
import json
import logging
import os
import tempfile
import csv
import itertools
from StringIO import StringIO
from mock import patch

from flask_testing import TestCase as BaseTestCase
import sqlalchemy as sa
from sqlalchemy import exc
from sqlalchemy import func
from sqlalchemy.sql.expression import tuple_
from google.appengine.ext import testbed

from ggrc import db
from ggrc.app import app
from ggrc import settings
from ggrc.converters.import_helper import read_csv_file
from ggrc.views.converters import check_import_file
from ggrc.models import Revision, all_models
from integration.ggrc import api_helper
from integration.ggrc.api_helper import Api
from integration.ggrc.models import factories

# Hide errors during testing. Errors are still displayed after all tests are
# done. This is for the bad request error messages while testing the api calls.
logging.disable(logging.CRITICAL)


THIS_ABS_PATH = os.path.abspath(os.path.dirname(__file__))

# Test relationship between Standard/Regulation and scope objects
_SCOPING_MODELS = all_models.get_scope_models()
READONLY_MAPPING_PAIRS = list(
    # make a list of object combinations from 1st and 2nd iterables
    # itertools.product("AB", "CD") is ["AC", "AD", "BC", "BD"]
    itertools.product(_SCOPING_MODELS, (all_models.Standard,
                                        all_models.Regulation))
)
# Test relationship for Control and Scope objects, Standard and Regulation
READONLY_MAPPING_PAIRS.extend(
    (all_models.Control, m) for m in itertools.chain(_SCOPING_MODELS,
                                                     (all_models.Standard,
                                                      all_models.Regulation))
)


def read_imported_file(file_data):  # pylint: disable=unused-argument
  csv_file = check_import_file()
  return read_csv_file(csv_file)


class SetEncoder(json.JSONEncoder):
  """Custom json encoder that supports sets."""
  # pylint: disable=method-hidden
  # false positive: https://github.com/PyCQA/pylint/issues/414

  def default(self, obj):  # pylint: disable=arguments-differ
    if isinstance(obj, set):
      return sorted(obj)
    return super(SetEncoder, self).default(obj)


class TestCase(BaseTestCase, object):
  # because it's required by unittests.

  """Base test case for all ggrc integration tests."""
  # pylint: disable=too-many-public-methods

  CSV_DIR = os.path.join(THIS_ABS_PATH, "test_csvs/")

  model = None
  testbed = None

  DEFAULT_DATETIME_FORMATS = [
      "{year}",
      "{year}-{month}",
      "{month}/{year}",
      "{year}-{month}-{day}",
      "{month}/{day}/{year}",
      "{year}-{month}-{day} {hour}",
      "{month}/{day}/{year} {hour}",
      "{year}-{month}-{day} {hour}:{minute}",
      "{month}/{day}/{year} {hour}:{minute}",
      # skip seconds filter (microseconds problem in mysql5.5)
      # "{year}-{month}-{day} {hour}:{minute}:{second}",
      # "{month}/{day}/{year} {hour}:{minute}:{second}",
  ]

  maxDiff = None

  def __init__(self, *args, **kwargs):
    super(TestCase, self).__init__(*args, **kwargs)
    self._headers = {}

  @staticmethod
  def get_role_id_for_obj(obj, role_name):
    """Return role id for ent instance and role_name."""
    from ggrc.access_control import role as ac_role
    for role_id, name in ac_role.get_custom_roles_for(obj.type).iteritems():
      if name == role_name:
        return role_id
    return None

  def get_persons_for_role_name(self, obj, role_name):
    """Generator. Return persons releated to sent instance and role_name."""
    role_id = self.get_role_id_for_obj(obj, role_name)
    for person, acl in obj.access_control_list:
      if acl.ac_role_id == role_id:
        yield person

  @contextlib.contextmanager
  def custom_headers(self, headers=None):
    """Context manager that allowed to add some custom headers in request."""
    tmp_headers = self._custom_headers.copy()
    self._custom_headers.update(headers or {})
    try:
      yield
    finally:
      self._custom_headers = tmp_headers

  @classmethod
  def clear_data(cls):
    """Remove data from ggrc tables.

    This is a helper function to remove any data that might have been generated
    during a test. The ignored tables are the ones that don't exist or have
    constant data in them, that was populated with migrations.

    This function is used to speed up resetting of the database for each test.
    the proper way would be to run all migrations on a fresh database, but that
    would take too much time. This function should act as if the database was
    just created, with the exception of autoincrement indexes.

    Note:
      The deletion is a hack because db.metadata.sorted_tables does not sort by
      dependencies. The events table is given before Person table and reversed
      order in then incorrect.
    """
    ignore_tables = (
        "notification_types",
        "object_types",
        "options",
        "relationship_test_mock_model",
        "roles",
        "test_model",
        "contexts",
        "people",
        "people_profiles",
        # data platform models that are currently populated with a migration
        "namespaces",
        "attribute_definitions",
        "attribute_types",
        "object_types",
        "attribute_templates",
        "object_templates",
        "access_control_roles",
        "background_operation_types",
    )
    tables = set(db.metadata.tables).difference(ignore_tables)
    for _ in range(len(tables)):
      if not tables:
        break  # stop the loop once all tables have been deleted
      for table in reversed(db.metadata.sorted_tables):
        if table.name in tables:
          try:
            db.engine.execute(table.delete())
            tables.remove(table.name)
          except exc.IntegrityError:
            pass
    contexts = db.metadata.tables["contexts"]
    db.engine.execute(contexts.delete(contexts.c.id > 1))
    people = db.metadata.tables["people"]
    db.engine.execute(people.delete(people.c.email != "user@example.com"))
    acr = db.metadata.tables["access_control_roles"]
    db.engine.execute(acr.delete(~acr.c.non_editable))
    if hasattr(db.session, "reindex_set"):
      delattr(db.session, "reindex_set")
    db.session.commit()

  def setUp(self):
    """Setup method."""
    from ggrc.fulltext import listeners

    self.clear_data()
    self._custom_headers = {}
    self.headers = {}
    api_helper.wrap_client_calls(self.client)
    listeners.reindex_on_commit = lambda: True  # Turn off background indexing

  def tearDown(self):  # pylint: disable=no-self-use
    db.session.remove()
    self.del_taskueue()

  @staticmethod
  def create_app():
    """Flask specific function for running an app instance."""
    app.config["SERVER_NAME"] = "localhost"
    app.testing = True
    app.debug = False
    return app

  @property
  def headers(self):
    """HTTP headers property"""
    if not self._headers:
      self._headers = {
          'Content-Type': 'application/json',
          "X-requested-by": "GGRC",
          "X-export-view": "blocks",
      }
    if hasattr(self, "_custom_headers"):
      self._headers.update(self._custom_headers)
    return self._headers

  @headers.setter
  def headers(self, value):
    self._headers = value

  def _check_csv_response(self, response, expected_messages):
    """Test that response contains all expected errors and warnigs.

    Args:
      response: api response object.
      expected_messages: dict of all expected errors by object type.

    Raises:
      AssertionError if an expected error or warning is not found in the
        proper response block.
    """

    messages = ("block_errors", "block_warnings", "row_errors", "row_warnings")
    counts = ("created", "updated", "rows")

    responses = defaultdict(lambda: defaultdict(set))

    # Set default empty sets for non existing error messages in blocks
    self.assertNotIn("message", response, str(response))
    for block in response:
      for message in messages:
        error_block = expected_messages.get(block["name"], {})
        error_block[message] = error_block.get(message, set())
        expected_messages[block["name"]] = error_block

    for block in response:
      for message in messages:
        if message in expected_messages.get(block["name"], {}):
          responses[block["name"]][message] = \
              responses[block["name"]][message].union(set(block[message]))
      for count in counts:
        if count in expected_messages.get(block["name"], {}):
          responses[block["name"]][count] = \
              responses[block["name"]].get(count, 0) + int(block[count])

    response_str = json.dumps(responses, indent=4, sort_keys=True,
                              cls=SetEncoder)
    expected_str = json.dumps(expected_messages, indent=4, sort_keys=True,
                              cls=SetEncoder)

    self.assertEqual(responses, expected_messages,
                     "Expected response does not match received response:\n\n"
                     "EXPECTED:\n{}\n\nRECEIVED:\n{}".format(
                         expected_str, response_str))

  def check_import_errors(self, response):
    """Check if import response doesn't contain any errors"""
    messages = ("block_errors", "row_errors")
    for block in response:
      for message in messages:
        errors = block.get(message, [])
        self.assertEqual(errors, [], str(errors))

  @classmethod
  def import_data(cls, *import_data, **kwargs):
    """generate tmp file in csv directory and import it after that remove file

    import data is dict with required key object_type, other keys are optional

    kwargs:
        dry_run (optional) default False - is import only for dry run
        person (optional) default None - who makes the import
    """
    dry_run = kwargs.get("dry_run", False)
    person = kwargs.get("person")
    with tempfile.NamedTemporaryFile(dir=cls.CSV_DIR, suffix=".csv") as tmp:
      writer = csv.writer(tmp)
      object_type = None
      for data in import_data:
        data = data.copy()
        data_object_type = data.pop("object_type")
        keys = data.keys()
        if data_object_type != object_type:
          if object_type is not None:
            writer.writerow([])
          object_type = data_object_type
          writer.writerow(["Object type"])
          writer.writerow([data_object_type] + keys)
        writer.writerow([""] + [data[k] for k in keys])
      tmp.seek(0)
      return cls._import_file(os.path.basename(tmp.name), dry_run, person)

  @classmethod
  def init_taskqueue(cls):
    """Init test environment for working with appengine."""
    cls.testbed = cls.testbed or testbed.Testbed()
    if not cls.testbed._activated:  # pylint: disable=protected-access
      cls.testbed.activate()

    # root_path must be set the the location of queue.yaml.
    # Otherwise, only the 'default' queue will be available.
    cls.testbed.init_taskqueue_stub(root_path=settings.BASE_DIR)
    cls.taskqueue_stub = cls.testbed.get_stub(testbed.TASKQUEUE_SERVICE_NAME)

  @classmethod
  def del_taskueue(cls):
    """Remove current testbed."""
    # pylint: disable=protected-access
    if cls.testbed and cls.testbed._activated:
      cls.testbed.deactivate()

  @classmethod
  def send_import_request(cls, data, dry_run=False, person=None):
    """Sending import post request."""
    cls.init_taskqueue()
    headers = {
        "X-test-only": "true" if dry_run else "false",
        "X-requested-by": "GGRC",
    }
    api = Api()
    api.set_user(person)  # Ok if person is None
    response = api.client.post("/_service/import_csv",
                               data=data, headers=headers)
    return json.loads(response.data)

  @classmethod
  @patch("ggrc.gdrive.file_actions.get_gdrive_file",
         new=read_imported_file)
  def _import_file(cls, filename, dry_run=False, person=None):
    """Function that handle sending file to import_csv service"""
    data = {"file": (open(os.path.join(cls.CSV_DIR, filename)), filename)}
    response = cls.send_import_request(data, dry_run=dry_run, person=person)
    return response

  def import_file(self, filename, person=None, safe=True):
    """Import a csv file as a specific user.

    Args:
      filename: the file to import;
      person: the user to use when calling the import endpoint;
      safe: if True (which means import_file is used to set up data),
            assert no errors and warnings occur.

    Returns:
      import response dict.
    """
    response_dry = self._import_file(filename, dry_run=True, person=person)
    response = self._import_file(filename, person=person)
    self.assertEqual(response_dry, response)
    if safe:
      self._check_csv_response(response, {})
    return response

  def export_csv(self, data, exportable_objects=None, headers=None):
    """Export csv handle

    return post action response to export_csv service with data argument as
    sended data
    """
    request_body = {
        "export_to": "csv",
        "objects": data,
        "exportable_objects": exportable_objects or []
    }
    if not headers or not isinstance(headers, dict):
      headers = self.headers
    else:
      headers.update(self.headers)
    return self.client.post("/_service/export_csv",
                            data=json.dumps(request_body),
                            headers=headers)

  def export_csv_template(self, objects):
    """Export csv template handle

    return post action response to export_csv_template service with objects
    argument as objects to make template
    """
    request_body = {
        "export_to": "csv",
        "objects": objects,
    }
    return self.client.post("/_service/export_csv_template",
                            data=json.dumps(request_body),
                            headers=self.headers)

  def export_parsed_csv(self, data, headers=None):
    """returns the dict of list of dict

    keys are humanreadable model name

    values are list of dicts
        keys of that dicts are the exportable field names
        values are the values of this field for current instance
    """
    resp = self.export_csv(data, headers=headers)
    self.assert200(resp)
    rows = csv.reader(StringIO(resp.data))

    object_type = None
    keys = []
    results = defaultdict(list)
    for columns in rows:
      if not any(columns):
        continue
      if columns[0] == "Object type":
        # new block started
        object_type = None
        keys = []
        continue
      if object_type is None:
        keys = columns[1:]
        object_type = columns[0]
        continue
      columns = [unicode(val) for val in columns]
      results[object_type].append(dict(zip(keys, columns[1:])))
    return results

  def assert_slugs(self, field, value, slugs, operator=None):
    """Assert slugs for selected search"""
    assert self.model
    search_request = [{
        "object_name": self.model.__name__,
        "filters": {
            "expression": {
                "left": field,
                "op": {"name": operator or "="},
                "right": value,
            },
        },
        "fields": ["slug"],
    }]
    parsed_data = self.export_parsed_csv(
        search_request
    )[self.model._inflector.title_singular.title()]
    self.assertEqual(sorted(slugs),
                     sorted([i["Code*"] for i in parsed_data]))

  def generate_date_strings(self, datetime_value, formats=None):
    """Generator datestrings

    returns datestrings for sent formats
    if it's empty returns datestrings for DEFAULT_DATETIME_FORMATS"""

    parts = ["year", "month", "day", "hour", "minute", "second"]
    kwargs = {i: getattr(datetime_value, i) for i in parts}
    formats = formats if formats is not None else self.DEFAULT_DATETIME_FORMATS
    for f_string in formats:
      yield f_string.format(**kwargs)

  @staticmethod
  def _get_latest_object_revisions(objects):
    """Get latest revisions of given objects."""
    object_tuples = [(o.id, o.type) for o in objects]
    revisions = Revision.query.filter(
        Revision.id.in_(
            db.session.query(func.max(Revision.id)).filter(
                tuple_(
                    Revision.resource_id,
                    Revision.resource_type,
                ).in_(object_tuples)
            ).group_by(
                Revision.resource_type,
                Revision.resource_id,
            )
        )
    )
    return revisions

  @classmethod
  def _create_snapshots(cls, audit, objects):
    """Create snapshots of latest object revisions for given objects."""
    # This commit is needed if we're using factories with single_commit, so
    # that the latest revisions will be fetched properly.
    db.session.commit()
    revisions = cls._get_latest_object_revisions(objects)
    snapshots = [
        factories.SnapshotFactory(
            child_id=revision.resource_id,
            child_type=revision.resource_type,
            revision=revision,
            parent=audit,
            context=audit.context,
        )
        for revision in revisions
    ]
    return snapshots

  def assert_roles(self, obj, **roles):
    """Assert if persons have required role for object"""
    acl_person_roles = [
        (acl.ac_role.name, person) for person, acl in obj.access_control_list
    ]
    for role, person in roles.items():
      self.assertTrue((role, person) in acl_person_roles)

  @classmethod
  def refresh_object(cls, obj, id_=None):
    """Returns a new instance of a model, fresh and warm from the database."""
    return obj.query.filter_by(id=obj.id if id_ is None else id_).first()

  @classmethod
  def create_assignees(cls, obj, persons):
    """Create assignees for object.

    This is used only during object creation because we cannot create
    assignees at that point yet.

    Args:
      obj: Assignable object.
      persons: [("(string) email", "Assignee roles"), ...] A list of people
        and their roles
    Returns:
      [(person, acr_role), ...] A list of persons with their roles.
    """
    assignees = []
    with factories.single_commit():
      for person, roles in persons:
        person = factories.PersonFactory(email=person)

        for role in roles.split(","):
          factories.AccessControlPersonFactory(
              ac_list=obj.acr_name_acl_map[role],
              person=person,
          )
          assignees.append((person, role))
    return assignees

  @staticmethod
  def get_model_ca(model_name, ids):
    """Get CAs for model."""
    return db.session.query(all_models.Attributes).filter(
        all_models.Attributes.object_type == model_name,
        all_models.Attributes.object_id.in_(ids),
    )

  def assert_notifications_for_object(self, obj, *expected_notification_list):
    """Assert object notifications are equal to expected notification list."""
    active_notifications = all_models.Notification.query.filter(
        all_models.Notification.object_id == obj.id,
        all_models.Notification.object_type == obj.type,
        sa.or_(all_models.Notification.sent_at.is_(None),
               all_models.Notification.repeating == sa.true())
    ).all()
    self.assertEqual(
        sorted(expected_notification_list),
        sorted([n.notification_type.name for n in active_notifications])
    )
