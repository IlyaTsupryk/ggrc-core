/*
    Copyright (C) 2019 Google Inc.
    Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import {
  getInfoUrl,
  isChangeableExternally,
} from '../../plugins/utils/ggrcq-utils';
import template from './questionnaire-link.mustache';

export default can.Component.extend({
  tag: 'questionnaire-link',
  template,
  leakScope: true,
  viewModel: {
    define: {
      infoUrl: {
        type: String,
        get: function () {
          const instance = this.attr('instance');

          return getInfoUrl(instance);
        },
      },
      isChangeableExternally: {
        type: Boolean,
        get: function () {
          const instance = this.attr('instance');

          return isChangeableExternally(instance);
        },
      },
    },
    instance: null,
  },
});
