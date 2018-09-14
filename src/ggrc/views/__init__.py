# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""ggrc.views
Handle non-RESTful views, e.g. routes which return HTML rather than JSON
"""
# pylint: disable=too-many-lines

import collections
import json
import logging

import datetime
import sqlalchemy
import flask
from werkzeug import exceptions

from ggrc import fulltext, login, models, settings, utils as ggrc_utils, \
    extensions as ggrc_extensions, converters as ggrc_converters
from ggrc.app import app, db
from ggrc.builder import json as builder_json
from ggrc.cache import utils as cache_utils
from ggrc.fulltext import mixin
from ggrc.integrations import integrations_errors, issues
from ggrc.models import background_task, reflection, revision
from ggrc.notifications import common
from ggrc.query import views as query_views
from ggrc.rbac import permissions
from ggrc.services import common as services_common
from ggrc.snapshotter import rules, indexer as snapshot_indexer
from ggrc.utils import benchmark, helpers, revisions
from ggrc.views import converters, cron, filters, notifications, registry, \
    utils


logger = logging.getLogger(__name__)
REINDEX_CHUNK_SIZE = 100


# Needs to be secured as we are removing @login_required
@app.route("/_background_tasks/propagate_acl", methods=["POST"])
@background_task.queued_task
def propagate_acl(_):
  """Web hook to update revision content."""
  models.hooks.acl.propagation.propagate_all()
  return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route("/_background_tasks/create_missing_revisions", methods=["POST"])
@background_task.queued_task
def create_missing_revisions(_):
  """Web hook to create revisions for new objects."""
  revisions.do_missing_revisions()
  return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route("/_background_tasks/reindex_snapshots", methods=["POST"])
@background_task.queued_task
def reindex_snapshots(_):
  """Web hook to update the full text search index."""
  logger.info("Updating index for: %s", "Snapshot")
  with benchmark("Create records for %s" % "Snapshot"):
    snapshot_indexer.reindex()
  return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route("/_background_tasks/reindex", methods=["POST"])
@background_task.queued_task
def reindex(_):
  """Web hook to update the full text search index."""
  do_reindex()
  return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route("/_background_tasks/full_reindex", methods=["POST"])
@background_task.queued_task
def full_reindex(_):
  """Web hook to update the full text search index for all models."""
  do_full_reindex()
  return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route("/_background_tasks/compute_attributes", methods=["POST"])
def compute_attributes(*_, **kwargs):
  """Web hook to update the full text search index."""
  with benchmark("Run compute_attributes background task"):
    event_id = ggrc_utils.get_task_attr("event_id", kwargs)
    revision_ids = ggrc_utils.get_task_attr("revision_ids", kwargs)

    if event_id and not revision_ids:
      rows = db.session.query(
          revision.Revision.id
      ).filter_by(event_id=event_id).all()
      revision_ids = [revision_id for revision_id, in rows]
    elif str(revision_ids) == "all_latest":
      revision_ids = "all_latest"
    else:
      revision_ids = list(revision_ids)

    from ggrc.data_platform import computed_attributes
    computed_attributes.compute_attributes(revision_ids)
    return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route('/_background_tasks/update_audit_issues', methods=['POST'])
@background_task.queued_task
def update_audit_issues(args):
  """Web hook to update the issues associated with an audit."""
  audit_id = args.parameters['audit_id']
  message = args.parameters['message']

  if not audit_id or not message:
    logger.warning(
        'One or more of required parameters (audit_id, message) is empty.')
    return app.make_response((
        'Parameters audit_id and message are required.',
        400, [('Content-Type', 'text/html')]))

  issue_tracker = models.all_models.IssuetrackerIssue
  relationships = models.all_models.Relationship
  query = db.session.query(
      issue_tracker.enabled,
      issue_tracker.issue_id,
      issue_tracker.object_id
  ).join(
      relationships,
      relationships.source_id == issue_tracker.object_id
  ).filter(
      relationships.source_type == 'Assessment',
      relationships.destination_type == 'Audit',
      relationships.destination_id == audit_id
  )
  cli = issues.Client()
  issue_params = {
      'comment': message,
  }
  for enabled, issue_id, assessment_id in query.all():
    if not enabled:
      continue

    try:
      cli.update_issue(issue_id, issue_params)
    except integrations_errors.Error as error:
      logger.error(
          'Unable to update IssueTracker issue ID=%s '
          'for Assessment ID=%s while archiving/unarchiving Audit ID=%s: %s',
          issue_id, assessment_id, audit_id, error)
  return app.make_response(('success', 200, [('Content-Type', 'text/html')]))


@app.route(
    "/_background_tasks/run_children_issues_generation", methods=["POST"]
)
@background_task.queued_task
def run_children_issues_generation(task):
  """Generate IssueTracker issues for objects of child type in parent."""
  try:
    params = getattr(task, "parameters", {})
    parent_type = params.get("parent", {}).get("type")
    parent_id = params.get("parent", {}).get("id")
    child_type = params.get("child_type")

    from ggrc.integrations import issuetracker_bulk_sync
    bulk_creator = issuetracker_bulk_sync.IssueTrackerBulkChildCreator()
    response = bulk_creator.sync_issuetracker(
        parent_type, parent_id, child_type
    )
    update_bulk_sync_history(
        task.id, bulk_creator.created, bulk_creator.failed
    )
    return response
  except integrations_errors.Error as error:
    logger.error('Bulk issue generation failed with error: %s', error.message)
    raise exceptions.BadRequest(error.message)


@app.route(
    "/_background_tasks/run_issues_generation", methods=["POST"]
)
@background_task.queued_task
def run_issues_generation(task):
  """Generate linked IssueTracker issues for provided objects."""
  try:
    from ggrc.integrations import issuetracker_bulk_sync
    bulk_creator = issuetracker_bulk_sync.IssueTrackerBulkCreator()
    params = getattr(task, "parameters", {})
    response = bulk_creator.sync_issuetracker(params.get("objects"))
    update_bulk_sync_history(
        task.id, bulk_creator.created, bulk_creator.failed
    )
    return response
  except integrations_errors.Error as error:
    logger.error('Bulk issue generation failed with error: %s', error.message)
    raise exceptions.BadRequest(error.message)


@app.route(
    "/_background_tasks/run_issues_update", methods=["POST"]
)
@background_task.queued_task
def run_issues_update(task):
  """Update linked IssueTracker issues for provided objects."""
  try:
    from ggrc.integrations import issuetracker_bulk_sync
    bulk_updater = issuetracker_bulk_sync.IssueTrackerBulkUpdater()
    params = getattr(task, "parameters", {})
    response = bulk_updater.sync_issuetracker(params.get("objects"))
    update_bulk_sync_history(
        task.id, bulk_updater.created, bulk_updater.failed
    )
    return response
  except integrations_errors.Error as error:
    logger.error('Bulk issue update failed with error: %s', error.message)
    raise exceptions.BadRequest(error.message)


def start_compute_attributes(revision_ids=None, event_id=None):
  """Start a background task for computed attributes."""
  background_task.create_lightweight_task(
      name="compute_attributes",
      url=flask.url_for(compute_attributes.__name__),
      parameters={"revision_ids": revision_ids, "event_id": event_id},
      method="POST",
      queued_callback=compute_attributes
  )


def start_update_audit_issues(audit_id, message):
  """Start a background task to update IssueTracker issues related to Audit."""
  task = background_task.create_task(
      name='update_audit_issues',
      url=flask.url_for(update_audit_issues.__name__),
      parameters={
          'audit_id': audit_id,
          'message': message,
      },
      method=u'POST',
      queued_callback=update_audit_issues
  )
  task.start()


@app.route("/_background_tasks/generate_wf_tasks_notifications",
           methods=["POST"])
@background_task.queued_task
def generate_wf_tasks_notifications(_):
  """Generate notifications for wf cycle tasks."""
  common.generate_cycle_tasks_notifs()
  return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@helpers.without_sqlalchemy_cache
def do_reindex(with_reindex_snapshots=False):
  """Update the full text search index."""

  indexer = fulltext.get_indexer()
  indexed_models = {
      m.__name__: m for m in models.all_models.all_models
      if issubclass(m, mixin.Indexed) and m.REQUIRED_GLOBAL_REINDEX
  }
  people_query = db.session.query(
      models.all_models.Person.id,
      models.all_models.Person.name,
      models.all_models.Person.email
  )
  indexer.cache["people_map"] = {p.id: (p.name, p.email) for p in people_query}
  indexer.cache["ac_role_map"] = dict(db.session.query(
      models.all_models.AccessControlRole.id,
      models.all_models.AccessControlRole.name,
  ))
  for model_name in sorted(indexed_models.keys()):
    logger.info("Updating index for: %s", model_name)
    with benchmark("Create records for %s" % model_name):
      model = indexed_models[model_name]
      ids = [id_[0] for id_ in db.session.query(model.id)]
      ids_count = len(ids)
      handled_ids = 0
      ids_chunks = ggrc_utils.list_chunks(ids, chunk_size=REINDEX_CHUNK_SIZE)
      for ids_chunk in ids_chunks:
        handled_ids += len(ids_chunk)
        logger.info("%s: %s / %s", model.__name__, handled_ids, ids_count)
        model.bulk_record_update_for(ids_chunk)
        db.session.plain_commit()

  if with_reindex_snapshots:
    logger.info("Updating index for: %s", "Snapshot")
    with benchmark("Create records for %s" % "Snapshot"):
      snapshot_indexer.reindex()

  indexer.invalidate_cache()


@helpers.without_sqlalchemy_cache
def do_full_reindex():
  """Update the full text search index for all models."""

  do_reindex(with_reindex_snapshots=True)
  start_compute_attributes(revision_ids="all_latest")


class SetEncoder(json.JSONEncoder):
  """Encoder that can handle python sets"""
  # pylint: disable=method-hidden
  # false positive: https://github.com/PyCQA/pylint/issues/414

  def default(self, obj):  # pylint: disable=arguments-differ
    """If we get a set we first transform it to a list and then just use
       the default encoder"""
    if isinstance(obj, set):
      return list(obj)
    return super(SetEncoder, self).default(obj)


def get_permissions_json():
  """Get all permissions for current user"""
  with benchmark("Get permission JSON"):
    permissions.permissions_for(permissions.get_user())
    return json.dumps(
        getattr(flask.g, '_request_permissions', None),
        cls=SetEncoder
    )


def get_config_json():
  """Get public app config"""
  with benchmark("Get config JSON"):
    public_config = dict(app.config.public_config)
    public_config.update(get_public_config())

    for extension_module in ggrc_extensions.get_extension_modules():
      if hasattr(extension_module, 'get_public_config'):
        public_config.update(
            extension_module.get_public_config(login.get_current_user()))

    return json.dumps(public_config)


def get_public_config():
  """Expose additional permissions-dependent config to client."""
  if settings.INTEGRATION_SERVICE_URL:
    external_service = "/people/suggest"
  else:
    external_service = None

  public_config = {
      "external_help_url": getattr(settings, "EXTERNAL_HELP_URL", ""),
      "external_import_help_url":
          getattr(settings, "EXTERNAL_IMPORT_HELP_URL", ""),
      "snapshotable_objects": list(rules.Types.all),
      "snapshotable_ignored": list(rules.Types.ignore),
      "snapshotable_parents": list(rules.Types.parents),
      "external_services": {"Person": external_service},
      "enable_release_notes": settings.ENABLE_RELEASE_NOTES,
  }

  if permissions.is_admin():
    if hasattr(settings, "RISK_ASSESSMENT_URL"):
      public_config["RISK_ASSESSMENT_URL"] = settings.RISK_ASSESSMENT_URL
  return public_config


def get_full_user_json():
  """Get the full current user"""
  with benchmark("Get full user JSON"):
    from ggrc.models.person import Person
    current_user = login.get_current_user()
    person = Person.eager_query().filter_by(id=current_user.id).one()
    result = builder_json.publish_representation(
        builder_json.publish(person, (), services_common.inclusion_filter)
    )
    return services_common.as_json(result)


def get_current_user_json():
  """Get current user"""
  with benchmark("Get current user JSON"):
    person = login.get_current_user()
    return services_common.as_json({
        "id": person.id,
        "company": person.company,
        "email": person.email,
        "language": person.language,
        "name": person.name,
        "system_wide_role": person.system_wide_role,
    })


def get_access_control_roles_json():
  """Get a list of all access control roles"""
  with benchmark("Get access roles JSON"):
    attrs = models.all_models.AccessControlRole.query.options(
        sqlalchemy.orm.undefer_group("AccessControlRole_complete")
    ).filter(~models.all_models.AccessControlRole.internal).all()
    published = []
    for attr in attrs:
      published.append(builder_json.publish(attr))
    published = builder_json.publish_representation(published)
    return services_common.as_json(published)


def get_internal_roles_json():
  """Get a list of all access control roles"""
  with benchmark("Get access roles JSON"):
    attrs = models.all_models.AccessControlRole.query.options(
        sqlalchemy.orm.undefer_group("AccessControlRole_complete")
    ).filter(
        models.all_models.AccessControlRole.internal == sqlalchemy.true()
    ).all()
    published = []
    for attr in attrs:
      published.append(builder_json.publish(attr))
    published = builder_json.publish_representation(published)
    return services_common.as_json(published)


def get_attributes_json():
  """Get a list of all custom attribute definitions"""
  with benchmark("Get attributes JSON"):
    with benchmark("Get attributes JSON: query"):
      attrs = models.CustomAttributeDefinition.eager_query().filter(
          models.CustomAttributeDefinition.definition_id.is_(None)
      ).all()
    with benchmark("Get attributes JSON: publish"):
      published = []
      for attr in attrs:
        published.append(builder_json.publish(attr))
      published = builder_json.publish_representation(published)
    with benchmark("Get attributes JSON: json"):
      publish_json = services_common.as_json(published)
      return publish_json


def get_import_types(export_only=False):
  """Returns types that can be imported (and exported) or exported only.

  Args:
    export_only (default False): If set to true, return objects that can only
        be exported and not imported.
  Returns:
    A list of models with model_singular and title_plural as keys.
  """
  # pylint: disable=protected-access
  types = ggrc_converters.get_importables
  if export_only:
    types = ggrc_converters.get_exportables
  data = []
  for model in set(types().values()):
    data.append({
        "model_singular": model.__name__,
        "title_plural": model._inflector.title_plural
    })
  data.sort()
  response_json = json.dumps(data)
  return response_json


def get_export_definitions():
  with benchmark("Get export definitions"):
    return get_import_types(export_only=True)


def get_import_definitions():
  with benchmark("Get import definitions"):
    return get_import_types(export_only=False)


def get_all_attributes_json(load_custom_attributes=False):
  """Get a list of all attribute definitions

  This exports all attributes related to a given model, including custom
  attributes and mapping attributes, that are used in csv import and export.
  """
  with benchmark('Loading all attributes JSON'):
    published = {}
    ca_cache = collections.defaultdict(list)
    if load_custom_attributes:
      definitions = models.CustomAttributeDefinition.eager_query().group_by(
          models.CustomAttributeDefinition.title,
          models.CustomAttributeDefinition.definition_type)
      for attr in definitions:
        ca_cache[attr.definition_type].append(attr)
    for model in models.all_models.all_models:
      published[model.__name__] = \
          reflection.AttributeInfo.get_attr_definitions_array(
              model, ca_cache=ca_cache)
    return services_common.as_json(published)


@app.context_processor
def base_context():
  """Gets the base context"""
  return dict(
      get_model=models.get_model,
      permissions_json=get_permissions_json,
      permissions=permissions,
      config_json=get_config_json,
      current_user_json=get_current_user_json,
      full_user_json=get_full_user_json,
      attributes_json=get_attributes_json,
      access_control_roles_json=get_access_control_roles_json,
      internal_access_control_roles_json=get_internal_roles_json,
      all_attributes_json=get_all_attributes_json,
      import_definitions=get_import_definitions,
      export_definitions=get_export_definitions,
  )


# Actual HTML-producing routes
#


@app.route("/")
def index():
  """The initial entry point of the app
  """
  if not settings.PRODUCTION:
    flask.flash(
        u"""This is not the production instance
        of the GGRC application.<br>
        Company confidential, sensitive or personally identifiable
        information <b>*MUST NOT*</b> be entered or stored here.
        For any questions, please contact your administrator.""",
        "alert alert-warning"
    )
  about_url = getattr(settings, "ABOUT_URL", None)
  about_text = getattr(settings, "ABOUT_TEXT", "About GGRC")
  return flask.render_template(
      "welcome/index.haml",
      about_url=about_url,
      about_text=about_text,
  )


@app.route("/dashboard")
@login.login_required
def dashboard():
  """The dashboard page
  """
  return flask.render_template(
      "dashboard/index.haml",
      page_type="MY_WORK",
  )


@app.route("/objectBrowser")
@login.login_required
def object_browser():
  """The object Browser page
  """
  return flask.render_template(
      "dashboard/index.haml",
      page_type="ALL_OBJECTS",
  )


@app.route("/admin/reindex_snapshots", methods=["POST"])
@login.login_required
@login.admin_required
def admin_reindex_snapshots():
  """Calls a webhook that reindexes indexable objects
  """
  task_queue = background_task.create_task(
      name="reindex_snapshots",
      url=flask.url_for(reindex_snapshots.__name__),
      queued_callback=reindex_snapshots,
  )
  return task_queue.make_response(
      app.make_response(("scheduled %s" % task_queue.name, 200,
                         [('Content-Type', 'text/html')])))


@app.route("/admin/reindex", methods=["POST"])
@login.login_required
@login.admin_required
def admin_reindex():
  """Calls a webhook that reindexes indexable objects
  """
  task_queue = background_task.create_task(
      name="reindex",
      url=flask.url_for(reindex.__name__),
      queued_callback=reindex
  )
  return task_queue.make_response(
      app.make_response(("scheduled %s" % task_queue.name, 200,
                         [('Content-Type', 'text/html')])))


@app.route("/admin/full_reindex", methods=["POST"])
@login.login_required
@login.admin_required
def admin_full_reindex():
  """Calls a webhook that reindexes all indexable objects
  """
  task_queue = background_task.create_task(
      name="full_reindex",
      url=flask.url_for(full_reindex.__name__),
      queued_callback=full_reindex
  )
  return task_queue.make_response(
      app.make_response(("scheduled %s" % task_queue.name, 200,
                         [('Content-Type', 'text/html')])))


@app.route("/admin/compute_attributes", methods=["POST"])
@login.login_required
@login.admin_required
def send_event_job():
  """Trigger background task on every event for computed attributes."""
  with benchmark("POST /admin/compute_attributes"):
    if flask.request.data:
      revision_ids = flask.request.get_json().get("revision_ids", [])
    else:
      revision_ids = "all_latest"
    start_compute_attributes(revision_ids=revision_ids)
    return app.make_response(("success", 200, [("Content-Type", "text/html")]))


@app.route("/admin/propagate_acl", methods=["POST"])
@login.login_required
@login.admin_required
def admin_propagate_acl():
  """Propagates all ACL entries"""
  admins = getattr(settings, "BOOTSTRAP_ADMIN_USERS", [])
  if login.get_current_user().email not in admins:
    raise exceptions.Forbidden()

  task_queue = background_task.create_task("propagate_acl", flask.url_for(
      propagate_acl.__name__), propagate_acl)
  return task_queue.make_response(
      app.make_response(("scheduled %s" % task_queue.name, 200,
                         [('Content-Type', 'text/html')])))


@app.route("/admin/create_missing_revisions", methods=["POST"])
@login.login_required
@login.admin_required
def admin_create_missing_revisions():
  """Create revisions for new objects"""
  admins = getattr(settings, "BOOTSTRAP_ADMIN_USERS", [])
  if login.get_current_user().email not in admins:
    raise exceptions.Forbidden()

  task_queue = background_task.create_task(
      "create_missing_revisions",
      flask.url_for(create_missing_revisions.__name__),
      create_missing_revisions
  )
  return task_queue.make_response(
      app.make_response(("scheduled %s" % task_queue.name, 200,
                        [('Content-Type', 'text/html')])))


@app.route("/admin")
@login.login_required
@login.admin_required
def admin():
  """The admin dashboard page
  """
  return flask.render_template("admin/index.haml")


@app.route("/assessments_view")
@login.login_required
def assessments_view():
  """The clutter-free list of all Person's Assessments"""
  return flask.render_template("assessments_view/index.haml")


@app.route("/background_task/<id_task>", methods=['GET'])
def get_task_response(id_task):
  """Gets the status of a background task"""
  return background_task.make_task_response(id_task)


@app.route(
    "/background_task_status/<object_type>/<object_id>",
    methods=['GET']
)
@login.login_required
def get_background_task_status(object_type, object_id):
  """Gets the status of a background task which was created for object."""
  bg_task = models.BackgroundTask
  bg_operation = models.BackgroundOperation
  task = bg_task.query.join(
      bg_operation,
      bg_operation.bg_task_id == bg_task.id
  ).filter(
      bg_operation.object_type == object_type,
      bg_operation.object_id == object_id,
  ).order_by(
      bg_task.created_at.desc()
  ).first()

  if task and task.bg_operation:
    body = {
        "status": task.status,
        "operation": task.bg_operation.bg_operation_type.name,
        "errors": task.get_content().get("errors", []),
    }
    response = app.make_response(
        (json.dumps(body), 200, [("Content-Type", "application/json")])
    )
  else:
    response = app.make_response(
        ("", 404, [("Content-Type", "application/json")])
    )
  return response


def contributed_object_views():
  """Contributed object views"""
  contributed_objects = [
      models.AccessGroup,
      models.Assessment,
      models.AssessmentTemplate,
      models.Audit,
      models.Contract,
      models.Control,
      models.DataAsset,
      models.Document,
      models.Evidence,
      models.Facility,
      models.Issue,
      models.Market,
      models.Objective,
      models.OrgGroup,
      models.Person,
      models.Policy,
      models.Process,
      models.Product,
      models.Program,
      models.Project,
      models.Regulation,
      models.Requirement,
      models.Risk,
      models.Snapshot,
      models.Standard,
      models.System,
      models.TechnologyEnvironment,
      models.Threat,
      models.Vendor,
      models.Metric,
      models.ProductGroup,
  ]
  return [registry.object_view(obj) for obj in contributed_objects]


def all_object_views():
  """Gets all object views defined in the application"""
  views = contributed_object_views()

  for extension_module in ggrc_extensions.get_extension_modules():
    contributions = getattr(extension_module, "contributed_object_views", None)
    if contributions:
      if callable(contributions):
        contributions = contributions()
      views.extend(contributions)

  return views


def init_extra_views(app_):
  """Init any extra views needed by the app

  This should be used for any views that might use extension modules.
  """
  filters.init_filter_views()
  converters.init_converter_views()
  cron.init_cron_views(app_)
  notifications.init_notification_views(app_)
  query_views.init_query_views(app_)
  query_views.init_clone_views(app_)


def init_all_views(app_):
  """Inits all views defined in the core module and submodules"""
  for entry in all_object_views():
    entry.service_class.add_to(
        app_,
        '/{0}'.format(entry.url),
        entry.model_class,
        decorators=(login.login_required,)
    )

  init_extra_views(app_)
  for extension_module in ggrc_extensions.get_extension_modules():
    ext_extra_views = getattr(extension_module, "init_extra_views", None)
    if ext_extra_views:
      ext_extra_views(app_)


@app.route("/permissions")
@login.login_required
def user_permissions():
  """Permissions object for the currently logged in user"""
  return get_permissions_json()


@app.route("/api/document/documents_exist", methods=["POST"])
@login.login_required
def is_document_exists():
  """Check if documents with gdrive_ids are exists"""
  utils.DocumentEndpoint.validate_doc_request(flask.request.json)
  ids = flask.request.json["gdrive_ids"]
  result_set = db.session.query(
      models.all_models.Document.id,
      models.all_models.Document.gdrive_id
  ).filter(
      models.all_models.Document.gdrive_id.in_(ids)
  )
  response = utils.DocumentEndpoint.build_doc_exists_response(
      flask.request.json,
      result_set
  )
  return flask.Response(json.dumps(response), mimetype='application/json')


@app.route("/api/document/make_admin", methods=["POST"])
@login.login_required
def make_document_admin():
  """Add current user as document admin"""
  utils.DocumentEndpoint.validate_doc_request(flask.request.json)
  ids = flask.request.json["gdrive_ids"]
  docs = models.all_models.Document.query.filter(
      models.all_models.Document.gdrive_id.in_(ids))
  for doc in docs:
    doc.add_admin_role()
  db.session.commit()
  cache_utils.clear_permission_cache()
  response = utils.DocumentEndpoint.build_make_admin_response(
      flask.request.json,
      docs
  )
  return flask.Response(json.dumps(response), mimetype='application/json')


@app.route("/generate_children_issues", methods=["POST"])
@login.login_required
def generate_children_issues():
  """Generate linked issuetracker issues for children objects.

  This endpoint is used to create tickets for all specific type instances
  in scope of parent. For example it allows to create tickets for all
  Assessments in some Audit.
  """
  validate_child_bulk_gen_data(flask.request.json)
  bg_task = background_task.create_task(
      "generate_children_issues",
      flask.url_for(run_children_issues_generation.__name__),
      run_children_issues_generation,
      flask.request.json,
      operation_type="generate_children_issues",
  )
  return bg_task.task_scheduled_response()


@app.route("/generate_issues", methods=["POST"])
@login.login_required
def generate_issues():
  """Bulk generate linked issuetracker issues for provided objects.

  This endpoint creates issuetracker tickets for all provided objects
  (if such tickets haven't been created before).
  """
  validate_bulk_sync_data(flask.request.json)
  bg_task = background_task.create_task(
      "generate_issues",
      flask.url_for(run_issues_generation.__name__),
      run_issues_generation,
      flask.request.json,
  )
  return bg_task.task_scheduled_response()


def background_generate_issues(parameters=None):
  """Bulk generate linked issuetracker issues for provided objects.

  This function creates issuetracker tickets for all provided objects
  (if such tickets haven't been created before). Can be called inside import
  task.
  """
  method = "POST"
  validate_bulk_sync_data(parameters)
  bg_task = background_task.create_task(
      "generate_issues",
      "/_background_tasks/run_issues_generation",
      run_issues_generation,
      parameters=parameters,
      method=method,
  )
  return bg_task.task_scheduled_response()


@app.route("/update_issues", methods=["POST"])
@login.login_required
def update_issues():
  """Bulk update linked issuetracker issues for provided objects.

  This endpoint update issuetracker tickets for all provided objects
  to the current state in the app.
  """
  validate_bulk_sync_data(flask.request.json)
  bg_task = background_task.create_task(
      "update_issues",
      flask.url_for(run_issues_update.__name__),
      run_issues_update,
      flask.request.json,
  )
  return bg_task.task_scheduled_response()


def background_update_issues(parameters=None):
  """Bulk update linked issuetracker issues for provided objects.

  This function update issuetracker tickets for all provided objects
  to the current state in the app. Can be called inside import
  task.
  """
  method = "POST"
  validate_bulk_sync_data(parameters)
  bg_task = background_task.create_task(
      "update_issues",
      "/_background_tasks/run_issues_update",
      run_issues_update,
      parameters=parameters,
      method=method,
  )
  return bg_task.task_scheduled_response()


def validate_child_bulk_gen_data(json_data):
  """Check correctness of input data for bulk child sync."""
  if not json_data or not isinstance(json_data, dict):
    raise exceptions.BadRequest("No data provided.")

  parent_type = json_data.get("parent", {}).get("type")
  parent_id = json_data.get("parent", {}).get("id")
  child_type = json_data.get("child_type")

  if not all((parent_id, parent_type, child_type)):
    raise exceptions.BadRequest("Required parameters is not provided.")

  parent = models.get_model(parent_type)
  child = models.get_model(child_type)
  from ggrc.models.mixins import issue_tracker
  if not issubclass(parent, issue_tracker.IssueTracked) or \
     not issubclass(child, issue_tracker.IssueTracked):
    raise exceptions.BadRequest("Provided model is not IssueTracked.")


def validate_bulk_sync_data(json_data):
  """Check correctness of input data for bulk child sync."""
  if not json_data or not isinstance(json_data, dict):
    raise exceptions.BadRequest("No data provided.")

  objects = json_data.get("objects", {})
  if not objects or not isinstance(objects, list):
    raise exceptions.BadRequest("Objects list is not provided.")

  for obj in objects:
    if not obj.get("id"):
      raise exceptions.BadRequest("Object id is not provided.")

    model = models.get_model(obj.get("type"))
    from ggrc.models.mixins import issue_tracker
    if not issubclass(model, issue_tracker.IssueTracked):
      raise exceptions.BadRequest("Provided object is not IssueTracked.")


def update_bulk_sync_history(task_id, created, failed):
  """Save information about objects synchronized with issuetracker."""
  with benchmark("Save information about created and failed objects"):
    created_history = [
        {
            "bg_task_id": task_id,
            "object_type": obj_type,
            "object_id": obj_id,
            "result": "1",
            "error": None,
            "modified_by_id": login.get_current_user_id(),
            "created_at": datetime.datetime.now(),
            "updated_at": datetime.datetime.now(),
        } for obj_type, obj_id in created
    ]
    failed_history = [
        {
            "bg_task_id": task_id,
            "object_type": obj.type,
            "object_id": obj.id,
            "result": "0",
            "error": err,
            "modified_by_id": login.get_current_user_id(),
            "created_at": datetime.datetime.now(),
            "updated_at": datetime.datetime.now(),
        } for obj, err in failed
    ]
    try:
      db.session.execute(
          models.all_models.IssuetrackerSyncHistory.__table__.insert().values(
              created_history + failed_history
          )
      )
      db.session.plain_commit()
    except sqlalchemy.exc.IntegrityError as exp:
      logging.error("Failed to save bulk sync result with error: %s", str(exp))


@app.route("/admin/generate_wf_tasks_notifications", methods=["POST"])
@login.login_required
@login.admin_required
def generate_wf_tasks_notifs():
  """Generate notifications for updated wf cycle tasks."""
  task_queue = background_task.create_task(
      "generate_wf_tasks_notifications",
      flask.url_for(generate_wf_tasks_notifications.__name__),
      generate_wf_tasks_notifications
  )
  return task_queue.make_response(
      app.make_response(("scheduled %s" % task_queue.name, 200,
                        [('Content-Type', 'text/html')])))
