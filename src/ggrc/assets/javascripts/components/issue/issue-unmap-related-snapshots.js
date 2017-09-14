/*!
    Copyright (C) 2017 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/
import template from './issue-unmap-related-snapshots.mustache';

var LoadRelatedError = 'loadRelated';
var UnmapRelatedError = 'unmapRelated';
var errorsMap = {
  loadRelated: 'There was a problem with retrieving related objects.',
  unmapRelated: 'There was a problem with unmapping.'
};
var queryApi = GGRC.Utils.QueryAPI;

export default GGRC.Components('issueUnmapRelatedSnapshots', {
  tag: 'issue-unmap-related-snapshots',
  template: template,
  viewModel: {
    define: {
      showRelatedSnapshots: {
        set: function (value) {
          this.attr('modalState.open', value);
          if (value) {
            this.loadRelatedObjects();
          }
        }
      },
      paging: {
        value: function () {
          return new GGRC.VM.Pagination({pageSizeSelect: [5, 10, 15]});
        }
      }
    },
    issueInstance: {},
    target: {},
    isLoading: false,
    modalTitle: 'Unmapping',
    relatedSnapshots: [],
    relatedAudit: {},
    modalState: {
      open: false
    },
    buildQuery: function (type) {
      return GGRC.Utils.QueryAPI.buildParam(
        type,
        this.attr('paging'),
        [
          {
            type: this.attr('target.type'),
            operation: 'relevant',
            id: this.attr('target.id')
          },
          {
            type: this.attr('issueInstance.type'),
            operation: 'relevant',
            id: this.attr('issueInstance.id')
          }
        ]
      );
    },
    loadRelatedObjects: function () {
      var self = this;
      var snapshotsQuery = this.buildQuery('Snapshot');
      var snapshotsLoader = queryApi
        .makeRequest({data: [snapshotsQuery]});
      var auditLoader = this.getRelatedAuditLoader();
      var dfds = [snapshotsLoader, auditLoader];
      this.attr('isLoading', true);

      $.when.apply($, dfds)
        .then(function (snapResp, audit) {
          var snapshots = snapResp[0][0].Snapshot.values;
          var total = snapResp[0][0].Snapshot.total;
          var title = 'Unmapping (' +
            (total + 1) +
            ' objects)';

          self.attr('relatedAudit', audit);
          self.attr('relatedSnapshots', snapshots);
          self.attr('paging.total', total);
          self.attr('modalTitle', title);
        })
        .fail(this.showError.bind(this, LoadRelatedError))
        .always(function () {
          this.attr('isLoading', false);
        }.bind(this));
    },
    getRelatedAuditLoader: function () {
      var audit = this.attr('target.audit');
      var loadingMethod;

      audit = audit.reify();
      loadingMethod = can.Deferred().resolve(audit);

      if (!audit.title) {
        loadingMethod = audit.refresh();
      }

      return loadingMethod;
    },
    openObject: function (relatedObject) {
      var model;
      var type;
      var url;
      var objectType = relatedObject.type;
      var id = relatedObject.id;

      if (relatedObject.type === 'Snapshot') {
        objectType = relatedObject.child_type;
        id = relatedObject.child_id;
      }

      model = CMS.Models[objectType];
      type = model.root_collection;
      url = '/' + type + '/' + id;

      window.open(url, '_blank');
    },
    unmap: function () {
      var sourceIds = _.pluck(
        this.attr('issueInstance.related_sources'),
        'id');
      var destinationIds = _.pluck(
        this.attr('target.related_destinations'),
        'id');
      var relId = _.intersection(sourceIds, destinationIds);
      var relationship = CMS.Models.Relationship.findInCacheById(relId);
      var currentObject = GGRC.page_instance();

      this.attr('isLoading', true);

      relationship
       .refresh()
       .then(function () {
         return relationship.unmap(true);
       })
       .done(function () {
         if (currentObject === this.attr('issueInstance')) {
           GGRC.navigate(this.attr('issueInstance.viewLink'));
         } else {
           this.attr('showRelatedSnapshots', false);
         }
       }.bind(this))
       .fail(this.showError.bind(this, UnmapRelatedError))
       .always(function () {
         this.attr('isLoading', false);
       }.bind(this));
    },
    showError: function (errorKey) {
      $('body').trigger('ajax:flash', {
        error: errorsMap[errorKey]
      });
    }
  },
  events: {
    '{viewModel.modalState} change': function () {
      // Close modal handler
      var modalState = this.viewModel.attr('modalState');
      if (!modalState.open) {
        this.viewModel.dispatch('modalClossed');
      }
    },
    '{viewModel.paging} current': function () {
      this.viewModel.loadRelatedObjects();
    },
    '{viewModel.paging} pageSize': function () {
      this.viewModel.loadRelatedObjects();
    }
  }
});

