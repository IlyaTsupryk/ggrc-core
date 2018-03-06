# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test Access Control roles propagation."""
from ggrc.models import all_models, get_model
from integration.ggrc import TestCase
from integration.ggrc.models import factories
from integration.ggrc_basic_permissions.models \
    import factories as rbac_factories


class TestACLPropagation(TestCase):
  """TestACLPropagation base class."""

  GLOBAL_ROLES = ["Creator", "Reader", "Editor", "Administrator"]

  SUCCESS = 200
  SUCCESS_CREATED = 201
  FORBIDDEN = 403

  ACCESS_ERROR = "Response for current operation has wrong status. {} " \
                 "expected, {} received."
  CAN_NOT_READ_ERROR = "{} objects weren't read. Non-zero object count " \
                       "expected."
  CAN_READ_ERROR = "Some {} objects were read. No objects expected."

  READ_COLLECTION_OPERATIONS = ["read_revisions", "get_latest_version"]

  def setup_people(self):
    """Setup people with global roles."""
    # pylint: disable=attribute-defined-outside-init
    roles_query = all_models.Role.query.filter(
        all_models.Role.name.in_(self.GLOBAL_ROLES)
    )
    global_roles = {role.name: role for role in roles_query}

    self.people = {}
    with factories.single_commit():
      for role_name in self.GLOBAL_ROLES:
        user = factories.PersonFactory()
        self.people[role_name] = user
        rbac_factories.UserRoleFactory(
            role=global_roles[role_name],
            person=user
        )

  def assert_read_collection(self, response, expected_res, model):
    """Check collection read operation.

    Args:
        response(TestResponse): Received operation response.
        expected_res: Boolean flag showing if objects should be read or not.
        model: Model name.
    """
    self.assertStatus(response, self.SUCCESS)
    table_plural = get_model(model)._inflector.table_plural
    response_data = response.json.get("{}_collection".format(table_plural), {})
    if expected_res:
      err = self.CAN_NOT_READ_ERROR.format(model)
    else:
      err = self.CAN_READ_ERROR.format(model)
    self.assertEqual(bool(response_data.get(table_plural)), expected_res, err)

  def assert_status(self, response, expected_res):
    """Check correctness of response status.

    Args:
        response: Response instance.
        expected_res: Boolean flag. If True 200/201 status expected, if False
          403 status expected.
    """
    success_statuses = [self.SUCCESS, self.SUCCESS_CREATED]
    exp_statuses = success_statuses if expected_res else [self.FORBIDDEN]
    self.assertIn(
        response.status_code,
        exp_statuses,
        self.ACCESS_ERROR.format(exp_statuses[0], response.status_code)
    )

  def assert_result(self, response, expected_res, operation, model):
    """Check correctness of response result.

    Args:
        response: Response instance.
        expected_res: Boolean flag that show if response should be succeeded.
        operation: Action name.
        model: Model name.
    """
    # Snapshot is a special case. All operation with it
    # is done through Revisions.
    model = "Revision" if model == "Snapshot" else model
    # Some operations based on several requests and responses,
    # need to verify all of these responses
    responses = response if isinstance(response, list) else [response]
    for res in responses:
      if operation in self.READ_COLLECTION_OPERATIONS:
        self.assert_read_collection(res, expected_res, model)
      else:
        self.assert_status(res, expected_res)

  def runtest(self, role, model, action_name, expected_result):
    """Run integration RBAC test.

    Args:
        role: Global user role (Creator/Reader/Editor).
        model: Model that should be tested (Audit/Assessment/...).
        action_name: Action that should be tested (read/update/delete/...).
        expected_result: Boolean expected result of action.
    """
    model_name, parent = model, None
    if " " in model:
      model_name, parent = model.split(" ")
    rbac_factory = self.init_factory(role, model_name, parent)
    if not rbac_factory:
      raise Exception("There is no factory for model '{}'".format(model_name))

    action = getattr(rbac_factory, action_name, None)
    if not action:
      raise NotImplementedError(
          "Action {} is not implemented for this test.".format(action_name)
      )
    self.assert_result(action(), expected_result, action_name, model_name)
