/*
    Copyright (C) 2018 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import RefreshQueue from '../refresh_queue';
import {
  Proxy,
  Direct,
  Indirect,
  Search,
  Multi,
  TypeFilter,
  CustomFilter,
  Cross,
} from '../mappers/mapper-helpers';
import Mappings from './mappings';
import CustomAttributeDefinition from '../custom-attributes/custom-attribute-definition';
import AccessControlRole from '../custom-roles/access-control-role';

const businessObjects = [
  'Metric', 'TechnologyEnvironment', 'AccessGroup',
  'DataAsset', 'Facility', 'Market', 'OrgGroup', 'Vendor', 'Process',
  'Product', 'ProductGroup', 'Project', 'System', 'Regulation',
  'Policy', 'Contract', 'Standard', 'Program', 'Issue', 'Control',
  'Requirement', 'Objective', 'Audit', 'Assessment',
  'AssessmentTemplate', 'Risk', 'Threat', 'Document',
];

const scopingObjects = [
  'Metric', 'TechnologyEnvironment', 'AccessGroup',
  'DataAsset', 'Facility', 'Market', 'OrgGroup', 'Vendor', 'Process',
  'Product', 'ProductGroup', 'Project', 'System',
];

(function (GGRC, can) {
  new Mappings('ggrc_core', {
    base: {},

    // Governance
    Control: {
      _mixins: [
        'related_object', 'assignable',
      ],
      orphaned_objects: Multi([
        'related_objects', 'controls', 'programs', 'objectives',
      ]),
    },
    Objective: {
      _mixins: ['related_object'],
      orphaned_objects: Multi([
        'related_objects', 'contracts', 'controls',
        'objectives', 'policies', 'programs', 'regulations',
        'requirements', 'standards',
      ]),
    },
    Requirement: {
      _mixins: ['related_object'],
    },
    Document: {
      _mixins: ['related_object'],
    },
    assignable: {
      info_related_objects: CustomFilter('related_objects',
        function (relatedObjects) {
          return !_.includes(['Comment', 'Document', 'Person'],
            relatedObjects.instance.type);
        }),
    },
    related_object: {
      _canonical: {
        related_objects_as_source: businessObjects,
      },
      related_objects_as_source: Proxy(
        null, 'destination', 'Relationship', 'source', 'related_destinations'),
      related_objects_as_destination: Proxy(
        null, 'source', 'Relationship', 'destination', 'related_sources'),
      related_objects:
        Multi(['related_objects_as_source', 'related_objects_as_destination']),
      destinations: Direct('Relationship', 'source', 'related_destinations'),
      sources: Direct('Relationship', 'destination', 'related_sources'),
      relationships: Multi(['sources', 'destinations']),
      related_access_groups: TypeFilter('related_objects', 'AccessGroup'),
      related_data_assets: TypeFilter('related_objects', 'DataAsset'),
      related_facilities: TypeFilter('related_objects', 'Facility'),
      related_markets: TypeFilter('related_objects', 'Market'),
      related_metrics: TypeFilter('related_objects', 'Metric'),
      related_org_groups: TypeFilter('related_objects', 'OrgGroup'),
      related_vendors: TypeFilter('related_objects', 'Vendor'),
      related_processes: TypeFilter('related_objects', 'Process'),
      related_products: TypeFilter('related_objects', 'Product'),
      related_product_groups: TypeFilter('related_objects', 'ProductGroup'),
      related_projects: TypeFilter('related_objects', 'Project'),
      related_systems: TypeFilter('related_objects', 'System'),
      related_issues: TypeFilter('related_objects', 'Issue'),
      related_audits: TypeFilter('related_objects', 'Audit'),
      related_controls: TypeFilter('related_objects', 'Control'),
      related_assessments: TypeFilter('related_objects', 'Assessment'),
      related_risks: TypeFilter('related_objects', 'Risk'),
      related_threats: TypeFilter('related_objects', 'Threat'),
      related_technology_environments: TypeFilter('related_objects',
        'TechnologyEnvironment'),
      regulations: TypeFilter('related_objects', 'Regulation'),
      contracts: TypeFilter('related_objects', 'Contract'),
      policies: TypeFilter('related_objects', 'Policy'),
      standards: TypeFilter('related_objects', 'Standard'),
      programs: TypeFilter('related_objects', 'Program'),
      controls: TypeFilter('related_objects', 'Control'),
      requirements: TypeFilter('related_objects', 'Requirement'),
      objectives: TypeFilter('related_objects', 'Objective'),
      risks: TypeFilter('related_objects', 'Risk'),
      threats: TypeFilter('related_objects', 'Threat'),
    },
    // Program
    Program: {
      _mixins: [
        'related_object',
      ],
      _canonical: {
        audits: 'Audit',
        context: 'Context',
      },
      related_issues: TypeFilter('related_objects', 'Issue'),
      audits: Direct('Audit', 'program', 'audits'),
      related_people_via_audits:
        TypeFilter('related_objects_via_audits', 'Person'),
      authorizations_via_audits: Cross('audits', 'authorizations'),
      context: Direct('Context', 'related_object', 'context'),
      contexts_via_audits: Cross('audits', 'context'),
      program_authorized_people: Cross('context', 'authorized_people'),
      program_authorizations: Cross('context', 'user_roles'),
      authorization_contexts: Multi(['context', 'contexts_via_audits']),
      authorizations_via_contexts:
        Cross('authorization_contexts', 'user_roles'),
      authorizations: Cross('authorization_contexts', 'user_roles'),
      authorized_people: Cross('authorization_contexts', 'authorized_people'),
      owner_authorizations: CustomFilter('program_authorizations',
        function (authBinding) {
          return new RefreshQueue()
            .enqueue(authBinding.instance.role.reify())
            .trigger()
            .then(function (roles) {
              return roles[0].name === 'ProgramOwner';
            });
        }),
      program_owners: Cross('owner_authorizations', 'person'),
      orphaned_objects: Multi([
        'related_objects',
      ]),
    },
    directive_object: {
      _mixins: [
        'related_object',
      ],
      orphaned_objects: Multi([
        'controls', 'objectives', 'related_objects',
      ]),
    },

    // Directives
    Regulation: {
      _mixins: ['directive_object'],
      _canonical: {
        related_objects_as_source: _.difference(
          businessObjects, scopingObjects),
      },
    },
    Contract: {
      _mixins: ['directive_object'],
    },
    Standard: {
      _mixins: ['directive_object'],
      _canonical: {
        related_objects_as_source: _.difference(
          businessObjects, scopingObjects),
      },
    },
    Policy: {
      _mixins: ['directive_object'],
    },

    // Business objects
    business_object: {
      _mixins: [
        'related_object',
      ],
      _canonical: {
        related_objects_as_source: _.difference(businessObjects,
          ['Standard', 'Regulation']),
      },
      orphaned_objects: Multi([
        'related_objects', 'controls', 'objectives', 'requirements',
      ]),
    },
    AccessGroup: {
      _mixins: ['business_object'],
    },
    DataAsset: {
      _mixins: ['business_object'],
    },
    Facility: {
      _mixins: ['business_object'],
    },
    Market: {
      _mixins: ['business_object'],
    },
    Metric: {
      _mixins: ['business_object'],
    },
    OrgGroup: {
      _mixins: ['business_object'],
    },
    Vendor: {
      _mixins: ['business_object'],
    },
    Product: {
      _mixins: ['business_object'],
    },
    ProductGroup: {
      _mixins: ['business_object'],
    },
    Project: {
      _mixins: ['business_object'],
    },
    System: {
      _mixins: ['business_object'],
    },
    Process: {
      _mixins: ['business_object'],
    },
    TechnologyEnvironment: {
      _mixins: ['business_object'],
    },
    Context: {
      _canonical: {
        user_roles: 'UserRole',
        authorized_people: 'Person',
      },
      user_roles: Direct('UserRole', 'context', 'user_roles'),
      authorized_people: Proxy('Person', 'person', 'UserRole', 'context',
        'user_roles'),
    },
    UserRole: {
      // FIXME: These should not need to be `Indirect` --
      //   `context.related_object` *should* point to the right object.
      audit_via_context: Indirect('Audit', 'context'),
      person: Direct('Person', 'user_roles', 'person'),
      role: Direct('Role', 'user_roles', 'role'),
    },
    Audit: {
      _canonical: {
        _program: 'Program',
        context: 'Context',
        evidence: 'Evidence',
      },
      _mixins: [
        'related_object',
      ],
      _program: Direct('Program', 'audits', 'program'),
      evidence: TypeFilter('related_objects', 'Evidence'),
      program_controls: Cross('_program', 'controls'),
      context: Direct('Context', 'related_object', 'context'),
      authorizations: Cross('context', 'user_roles'),
      authorized_program_people: Cross('_program', 'authorized_people'),
      authorized_audit_people: Cross('authorizations', 'person'),
      authorized_people:
        Multi(['authorized_audit_people', 'authorized_program_people']),
      auditor_authorizations: CustomFilter('authorizations', function (result) {
        return new RefreshQueue()
          .enqueue(result.instance.role.reify())
          .trigger()
          .then(function (roles) {
            return roles[0].name === 'Auditor';
          });
      }),
      auditors: Cross('auditor_authorizations', 'person'),
    },
    Assessment: {
      _canonical: {
        evidence: 'Evidence',
      },
      _mixins: [
        'related_object', 'assignable',
      ],
      evidence: TypeFilter('related_objects', 'Evidence'),
      audits: TypeFilter('related_objects', 'Audit'),
      related_regulations: TypeFilter('related_objects', 'Regulation'),
    },
    Evidence: {
      _canonical: {
        related_objects_as_source: ['Audit', 'Assessment'],
      },
      related_objects_as_source: Proxy(
        null, 'destination', 'Relationship', 'source', 'related_destinations',
      ),
    },
    AssessmentTemplate: {},
    Issue: {
      _mixins: [
        'related_object', 'assignable',
      ],
      audits: TypeFilter('related_objects', 'Audit'),
    },
    Comment: {
      _mixins: ['related_object'],
    },
    MultitypeSearch: {
      _canonical: {
        related_objects_as_source: [
          'DataAsset', 'Facility', 'Market', 'OrgGroup', 'Vendor', 'Process',
          'Product', 'ProductGroup', 'Project', 'System', 'Regulation',
          'Policy', 'Contract', 'Standard', 'Program', 'Issue', 'Control',
          'Requirement', 'Objective', 'Audit', 'Assessment',
          'AssessmentTemplate', 'AccessGroup', 'Risk', 'Threat', 'Document',
          'Metric', 'TechnologyEnvironment', 'Workflow', 'Evidence', 'Person',
          'TaskGroupTask', 'TaskGroup', 'CycleTaskGroupObjectTask',
        ],
      },
    },
    // Used by Custom Attributes widget
    CustomAttributable: {
      custom_attribute_definitions: Search(function (binding) {
        return CustomAttributeDefinition.findAll({
          definition_type: binding.instance.root_object,
          definition_id: null,
        });
      }, 'CustomAttributeDefinition'),
    },
    // used by the Custom Roles admin panel tab
    Roleable: {
      access_control_roles: Search(function (binding) {
        return AccessControlRole.findAll({
          object_type: binding.instance.model_singular,
          internal: false,
        });
      }, 'AccessControlRole'),
    },
    Risk: {
      _mixins: ['directive_object'],
    },
    Threat: {
      _mixins: ['directive_object'],
    },
  });
})(window.GGRC, window.can);
