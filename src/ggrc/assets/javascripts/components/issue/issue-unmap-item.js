/*!
    Copyright (C) 2017 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/
import template from './issue-unmap-item.mustache';

export default GGRC.Components('issueUnmapItem', {
  tag: 'issue-unmap-item',
  template: template,
  viewModel: {
    issueInstance: {},
    target: {},
    showRelatedObjects: false,
    canUnmap: function () {
      return GGRC.Utils.allowed_to_map(this.attr('issueInstance'),
        this.attr('target'), {}, true);
    },
    unmap: function () {
      if (this.attr('target.type') === 'Assessment' &&
        !this.attr('issueInstance.allow_unmap_from_audit')) {
        this.attr('showRelatedSnapshots', true);
        return;
      }

      this.dispatch('unmapIssue');
    },
    modalClossed: function () {
      this.attr('showRelatedSnapshots', false);
    }
  },
  events: {
    click: function (el, ev) {
      this.viewModel.unmap();
      ev.preventDefault();
    }
  }
});
