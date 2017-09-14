/*!
    Copyright (C) 2017 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/
import component from
  '../issue-unmap-related-snapshots';

describe('GGRC.Components.IssueUnmapRelatedSnapshots', function () {
  var viewModel;
  var events;
  beforeEach(function () {
    viewModel = new (can.Map.extend(component.prototype.viewModel));
    events = component.prototype.events;
  });

  describe('loadRelatedObjects() method', function () {
    var reqDeferred;
    var auditDeferred;

    beforeEach(function () {
      reqDeferred = can.Deferred();
      auditDeferred = can.Deferred();
      spyOn(viewModel, 'buildQuery').and.returnValue(['query']);
      spyOn(GGRC.Utils.QueryAPI, 'makeRequest').and.returnValue(reqDeferred);
      spyOn(viewModel, 'getRelatedAuditLoader').and.returnValue(auditDeferred);
      spyOn($.prototype, 'trigger');
    });

    it('should load snapshots correctly', function () {
      var snapshots = [[{
        Snapshot: {
          values: [{}, {}],
          total: 10
        }
      }]];
      var audit = {};

      viewModel.loadRelatedObjects();

      expect(viewModel.attr('isLoading')).toBeTruthy();

      reqDeferred.resolve(snapshots);
      auditDeferred.resolve(audit);

      expect(viewModel.attr('relatedSnapshots.length'))
        .toBe(2);
      expect(viewModel.attr('paging.total'))
        .toBe(10);
      expect(viewModel.attr('modalTitle'))
        .toBe('Unmapping (11 objects)');
      expect(viewModel.attr('isLoading')).toBeFalsy();
    });

    it('should handle server errors correctly', function () {
      viewModel.loadRelatedObjects();

      expect(viewModel.attr('isLoading')).toBeTruthy();

      reqDeferred.reject();

      expect($.prototype.trigger).toHaveBeenCalledWith('ajax:flash', {
        error: 'There was a problem with retrieving related objects.'
      });
      expect(viewModel.attr('isLoading')).toBeFalsy();
    });
  });

  describe('unmap() method', function () {
    var refreshDfd;
    var unmapDfd;
    var pageInstance;

    beforeEach(function () {
      var relationship;
      pageInstance = new can.Map({viewLink: 'temp url'});
      unmapDfd = can.Deferred();
      refreshDfd = can.Deferred();
      relationship = {
        refresh: function () {
          return refreshDfd;
        },
        unmap: function () {
          return unmapDfd;
        }
      };
      spyOn($.prototype, 'trigger');
      spyOn(CMS.Models.Relationship, 'findInCacheById')
        .and.returnValue(relationship);
      spyOn(GGRC, 'page_instance')
        .and.returnValue(pageInstance);
      spyOn(GGRC, 'navigate');
    });

    it('should unmap issue correctly', function () {
      viewModel.attr('issueInstance', {});
      viewModel.attr('issueInstance.related_sources', [
        {id: 1}, {id: 2}, {id: 3}]);
      viewModel.attr('target.related_destinations', [
        {id: 4}, {id: 4}, {id: 3}]);

      viewModel.unmap();

      expect(viewModel.attr('isLoading')).toBeTruthy();

      refreshDfd.resolve();
      unmapDfd.resolve();

      expect(viewModel.attr('showRelatedSnapshots'))
        .toBeFalsy();
      expect(viewModel.attr('isLoading')).toBeFalsy();
    });

    it('should unmap from issue correctly', function () {
      viewModel.attr('issueInstance', pageInstance);
      viewModel.attr('issueInstance.related_sources', [
        {id: 1}, {id: 2}, {id: 3}]);
      viewModel.attr('target.related_destinations', [
        {id: 4}, {id: 4}, {id: 3}]);

      viewModel.unmap();

      expect(viewModel.attr('isLoading')).toBeTruthy();

      refreshDfd.resolve();
      unmapDfd.resolve();

      expect(GGRC.navigate)
        .toHaveBeenCalledWith('temp url');
      expect(viewModel.attr('isLoading')).toBeFalsy();
    });

    it('should handle server errors correctly', function () {
      viewModel.unmap();

      expect(viewModel.attr('isLoading')).toBeTruthy();

      refreshDfd.reject();

      expect($.prototype.trigger).toHaveBeenCalledWith('ajax:flash', {
        error: 'There was a problem with unmapping.'
      });
      expect(viewModel.attr('isLoading')).toBeFalsy();
    });
  });

  describe('modalState.change event', function () {
    var handler;

    beforeEach(function () {
      handler = events['{viewModel.modalState} change']
        .bind({viewModel: viewModel});
      spyOn(viewModel, 'dispatch');
    });

    it('shouldn\'t dispatch event when modal opens', function () {
      viewModel.attr('modalState.open', true);

      handler();

      expect(viewModel.dispatch).not.toHaveBeenCalled();
    });

    it('should dispatch event when modal closes', function () {
      viewModel.attr('modalState.open', false);

      handler();

      expect(viewModel.dispatch).toHaveBeenCalled();
    });
  });
});

