# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Issue RBAC Factory."""

from ggrc.models import all_models, get_model
from integration.ggrc import Api, generator
from integration.ggrc.access_control.rbac_factories import base
from integration.ggrc.models import factories


class IssueRBACFactory(base.BaseRBACFactory):
  """Issue RBAC factory class."""

  def __init__(self, user_id, acr, parent=None):
    """Set up objects for Issue permission tests.

    Args:
        user_id: Id of user under which all operations will be run.
        acr: Instance of ACR that should be assigned for tested user.
        parent: Model name in scope of which objects should be set up.
    """
    self.setup_program_scope(user_id, acr)

    with factories.single_commit():
      issue = factories.IssueFactory()
      if parent == "Audit":
        self.mapping_id = factories.RelationshipFactory(
            source=self.audit, destination=issue
        ).id
      elif parent == "Assessment":
        self.mapping_id = factories.RelationshipFactory(
            source=self.assessment, destination=issue
        ).id

    self.issue_id = issue.id
    self.parent = parent
    self.admin_acr_id = all_models.AccessControlRole.query.filter_by(
        name="Admin",
        object_type="Issue",
    ).one().id
    self.user_id = user_id
    self.api = Api()
    self.objgen = generator.ObjectGenerator()
    self.objgen.api = self.api

    if user_id:
      user = all_models.Person.query.get(user_id)
      self.api.set_user(user)

  def create(self):
    """Create new Issue object."""
    return self.api.post(all_models.Issue, {
        "issue": {
            "access_control_list": [{
                "ac_role_id": self.admin_acr_id,
                "person": {
                    "id": self.user_id,
                    "type": "Person",
                }
            }],
            "title": factories.random_str(),
            "context": None,
        }
    })

  def read(self):
    """Read existing Issue object."""
    return self.api.get(all_models.Issue, self.issue_id)

  def update(self):
    """Update title of existing Issue object."""
    issue = all_models.Issue.query.get(self.issue_id)
    return self.api.put(issue, {"title": factories.random_str()})

  def delete(self):
    """Delete Issue object."""
    issue = all_models.Issue.query.get(self.issue_id)
    return self.api.delete(issue)

  def read_revisions(self):
    """Read revisions of Issue object."""
    model_class = get_model("Issue")
    responses = []
    for query in ["source_type={}&source_id={}",
                  "destination_type={}&destination_id={}",
                  "resource_type={}&resource_id={}"]:
      responses.append(
          self.api.get_query(
              model_class,
              query.format("issue", self.issue_id)
          )
      )
    return responses

  def map(self, issue=None):
    """Map Issue to parent object."""
    if self.parent == "Audit":
      parent = all_models.Audit.query.get(self.audit_id)
    else:
      parent = all_models.Assessment.query.get(self.assessment_id)
    map_issue = issue if issue else factories.IssueFactory()

    return self.objgen.generate_relationship(
        source=parent,
        destination=map_issue
    )[0]

  def create_and_map(self):
    """Create new Issue and map it to parent."""
    response = self.create()
    issue_id = None
    if response.json and response.json.get("issue"):
      issue_id = response.json.get("issue", {}).get("id")
    if not issue_id:
      return response

    issue = all_models.Issue.query.get(issue_id)
    return self.map(issue)

  def unmap(self):
    """Unmap Issue from parent object."""
    mapping = all_models.Relationship.query.get(self.mapping_id)
    return self.api.delete(mapping)

  def raise_issue(self):
    """Raise issue for Assessment."""
    assessment = all_models.Assessment.query.get(self.assessment_id)
    data = [{
        "issue": {
            "assessment": {
                "id": assessment.id,
                "type": assessment.type,
            },
            "title": factories.random_str(),
            "context": None
        }
    }]
    return self.api.post(all_models.Issue, data)
