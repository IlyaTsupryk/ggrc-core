# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Assessment Template RBAC Factory."""

from ggrc.models import all_models, get_model

from integration.ggrc import Api
from integration.ggrc.access_control.rbac_factories import base
from integration.ggrc.models import factories


class AssessmentTemplateRBACFactory(base.BaseRBACFactory):
  """Assessment Template RBAC factory class."""

  def __init__(self, user_id, acr, parent=None):
    """Set up objects for Assessment Template permission tests.

    Args:
        user_id: Id of user under which all operations will be run.
        acr: Instance of ACR that should be assigned for tested user.
        parent: Model name in scope of which objects should be set up.
    """
    self.setup_program_scope(user_id, acr, parent)

    with factories.single_commit():
      template = factories.AssessmentTemplateFactory(audit=self.audit)
      factories.RelationshipFactory(source=self.audit, destination=template)

    self.template_id = template.id
    self.default_assignees = "Admin"
    self.default_verifiers = "Admin"
    self.api = Api()

    if user_id:
      user = all_models.Person.query.get(user_id)
      self.api.set_user(user)

  def create(self):
    """Create new Assessment Template object."""
    return self.api.post(all_models.AssessmentTemplate, {
        "assessment_template": {
            "audit": {"id": self.audit_id},
            "context": None,
            "default_people": {
                "assignees": self.default_assignees,
                "verifiers": self.default_verifiers,
            },
            "title": "New Assessment Template"
        }
    })

  def read(self):
    """Read existing Assessment Template object."""
    return self.api.get(all_models.AssessmentTemplate, self.template_id)

  def update(self):
    """Update title of existing Assessment Template object."""
    template = all_models.AssessmentTemplate.query.get(self.template_id)
    return self.api.put(template, {"title": factories.random_str()})

  def delete(self):
    """Delete Assessment Template object."""
    template = all_models.AssessmentTemplate.query.get(self.template_id)
    return self.api.delete(template)

  def read_revisions(self):
    """Read revisions for Assessment Template object."""
    model_class = get_model("AssessmentTemplate")
    responses = []
    for query in ["source_type={}&source_id={}",
                  "destination_type={}&destination_id={}",
                  "resource_type={}&resource_id={}"]:
      responses.append(
          self.api.get_query(
              model_class,
              query.format("assessment_template", self.template_id)
          )
      )
    return responses
