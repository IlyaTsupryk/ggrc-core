/*
  Copyright (C) 2019 Google Inc.
  Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
*/

import {getUrl} from '../utils/ggrcq-utils';

describe('GGRCQ utils', () => {
  let originalIntegrationUrl;

  beforeAll(() => {
    originalIntegrationUrl = GGRC.GGRC_Q_INTEGRATION_URL;
    GGRC.GGRC_Q_INTEGRATION_URL = originalIntegrationUrl || 'http://example.com/';
  });

  afterAll(() => {
    GGRC.GGRC_Q_INTEGRATION_URL = originalIntegrationUrl;
  });

  describe('getUrl util', () => {
    it('should return url', () => {
      const options = {
        model: 'control',
        path: 'control',
        slug: 'control-1',
        view: 'info',
      };

      expect(getUrl(options))
        .toBe(`${GGRC.GGRC_Q_INTEGRATION_URL}control/control=control-1/info`);
    });

    it('should return url without view path', () => {
      const options = {
        model: 'control',
        path: 'questionnaires',
        slug: 'control-1',
      };

      expect(getUrl(options))
        .toBe(`${GGRC.GGRC_Q_INTEGRATION_URL}questionnaires/control=control-1`);
    });
  });
});
