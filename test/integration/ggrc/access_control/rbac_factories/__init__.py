from integration.ggrc.access_control.rbac_factories import audit, assessment


def get_factory(model):
  factories = {
      "Audit": audit.AuditRBACFactory,
      "Assessment": assessment.AssessmentRBACFactory,
  }
  return factories[model]
