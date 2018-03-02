from ggrc.models import all_models, get_model
from integration.ggrc import Api, TestCase, generator
from integration.ggrc.models import factories


class AssessmentRBACFactory(object):
  def __init__(self, audit_id, assessment_id, user):
    self.api = Api()
    self.objgen = generator.ObjectGenerator()
    self.objgen.api = self.api
    self.audit_id = audit_id
    self.assessment_id = assessment_id
    self.api.set_user(user)

  def create(self):
    return self.api.post(all_models.Assessment, {
        "assessment": {
            "title": "New Assessment",
            "context": None,
            "audit": {"id": self.audit_id},
        },
    })

  def generate(self):
    with factories.single_commit():
      control = factories.ControlFactory()
      template_id = factories.AssessmentTemplateFactory().id
    audit = all_models.Audit.query.get(self.audit_id)
    snapshot_id = TestCase._create_snapshots(audit, [control])[0].id

    responses = []
    asmnt_data = {
        "assessment": {
            "_generated": True,
            "audit": {
                "id": self.audit_id,
                "type": "Audit"
            },
            "object": {
                "id": snapshot_id,
                "type": "Snapshot"
            },
            "context": None,
            "title": "New assessment",
        }
    }
    responses.append(self.api.post(all_models.Assessment, asmnt_data))

    asmnt_data["assessment"]["template"] = {
        "id": template_id,
        "type": "AssessmentTemplate"
    }
    responses.append(self.api.post(all_models.Assessment, asmnt_data))
    return responses

  def read(self):
    """Test access to model endpoint."""
    responses = []
    # TODO: check correctness of this
    responses.append(self.api.get_query(all_models.Assessment, ""))
    responses.append(
        self.api.get_query(all_models.Assessment, self.assessment_id)
    )
    return responses

  def update(self):
    asmnt = all_models.Assessment.query.get(self.assessment_id)
    return self.api.put(asmnt, {"title": factories.random_str()})

  def delete(self):
    asmnt = all_models.Assessment.query.get(self.assessment_id)
    return self.api.delete(asmnt)

  def read_revisions(self):
    model_class = get_model("Assessment")
    responses = []
    for query in ["source_type={}&source_id={}",
                  "destination_type={}&destination_id={}",
                  "resource_type={}&resource_id={}"]:
      responses.append(
          self.api.get_query(
              model_class,
              query.format("assessment", self.assessment_id)
          )
      )
    return responses

  def map_snapshot(self):
    control = factories.ControlFactory()
    assessment = all_models.Assessment.query.get(self.assessment_id)
    snapshot = TestCase._create_snapshots(assessment, [control])[0]

    return self.objgen.generate_relationship(
        source=assessment,
        destination=snapshot,
    )[0]
