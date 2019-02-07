# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Test for not_empty operator."""

from ggrc.models import all_models

from integration import ggrc as test_ggrc
from integration.ggrc import factories
from integration.ggrc import api_helper
from integration.ggrc import query_helper
from integration.ggrc import review


class TestNotEmptyRevisions(test_ggrc.TestCase, query_helper.WithQueryApi):
  """Test for correctness of `not_empty_revisions` operator."""

  @classmethod
  def setUpClass(cls):  # pylint: disable=missing-docstring
    super(TestNotEmptyRevisions, cls).setUpClass()
    cls.api = api_helper.Api()

  def setUp(self):
    super(TestNotEmptyRevisions, self).setUp()
    self.client.get("/login")

  def _turn_on_bg_indexing(self):
    """Helper method to turn on bg indexing."""
    from ggrc.fulltext import listeners
    from ggrc.models import background_task

    listeners.reindex_on_commit = background_task.reindex_on_commit
    self.init_taskqueue()

  def _turn_off_bg_indexing(self):
    """Helper method to turn off bg indexing."""
    from ggrc.fulltext import listeners

    listeners.reindex_on_commit = lambda: True
    self.del_taskueue()

  def _query_not_empty_revisions(self, instance):
    """Helper function to qeury not empty revisions with query API."""
    return self._get_first_result_set(
        {
            "object_name": "Revision",
            "type": "ids",
            "filters": {
                "expression": {
                    "op": {"name": "not_empty_revisions"},
                    "resource_type": instance.type,
                    "resource_id": instance.id,
                },
            },
        },
        "Revision",
        "ids",
    )

  @staticmethod
  def _count_revisions(instance):
    """Helper function to count instance revisions."""
    return all_models.Revision.query.filter(
        all_models.Revision.resource_type == instance.type,
        all_models.Revision.resource_id == instance.id,
    ).count()

  @staticmethod
  def _refresh_instance(instance_type, instance_id):
    """Helper function to refresh instance from db."""
    instance_cls = getattr(all_models, instance_type, None)
    if instance_cls is None:
      raise ValueError("'{}' is not a valid instance type"
                       .format(instance_type))
    return instance_cls.query.get(instance_id)

  def test_not_empty_revisions(self):
    """Test `not_empty_revisions` returns revisions with changes."""
    self._turn_on_bg_indexing()
    instance = factories.ProgramFactory()

    def edit_without_changes(instance):
      """Helper function to perform instance edit without actual changes."""
      response = self.api.put(instance, {})
      self.assert200(response)

    edit_without_changes(instance)
    instance = self._refresh_instance(instance.type, instance.id)
    revisions_count = self._count_revisions(instance)
    not_empty_revisions = self._query_not_empty_revisions(instance)

    self.assertEqual(revisions_count, 2)
    self.assertEqual(len(not_empty_revisions), 1)
    self._turn_off_bg_indexing()

  def test_review_status(self):
    """Test not_empty_revisions works correcly with review status change."""
    instance = factories.ProgramFactory()

    def mark_as_reviewed(instance):
      """Helper function to mark `instance` as reviewed."""
      response = self.api.post(
          all_models.Review,
          {
              "review": {
                  "reviewable": {
                      "type": instance.type,
                      "id": instance.id,
                  },
                  "context": None,
                  "notification_type": "email",
                  "status": all_models.Review.STATES.REVIEWED,
                  "access_control_list": review.build_reviewer_acl(),
              },
          },
      )
      self.assertStatus(response, 201)

    mark_as_reviewed(instance)
    instance = self._refresh_instance(instance.type, instance.id)
    revisions_count = self._count_revisions(instance)
    not_empty_revisions = self._query_not_empty_revisions(instance)

    self.assertEqual(revisions_count, 2)
    self.assertEqual(len(not_empty_revisions), 2)
