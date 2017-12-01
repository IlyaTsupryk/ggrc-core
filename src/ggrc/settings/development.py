# Copyright (C) 2017 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

import os

DEBUG = True
TESTING = False
PRODUCTION = False
FLASK_DEBUGTOOLBAR = False
HOST = '0.0.0.0'
SQLALCHEMY_DATABASE_URI = os.environ.get(
    'GGRC_DATABASE_URI',
    'mysql+mysqldb://root:root@127.0.0.1/ggrcdev?charset=utf8')
FULLTEXT_INDEXER = 'ggrc.fulltext.mysql.MysqlIndexer'
LOGIN_MANAGER = 'ggrc.login.noop'
SQLALCHEMY_ECHO = True
SQLALCHEMY_RECORD_QUERIES = 'slow'
AUTOBUILD_ASSETS = True
ENABLE_JASMINE = True
# DEBUG_ASSETS = True
USE_APP_ENGINE_ASSETS_SUBDOMAIN = False
MEMCACHE_MECHANISM = False
APPENGINE_EMAIL = "user@example.com"

LOGGING_FORMATTER = {
    "()": "colorlog.ColoredFormatter",
    "format": "%(log_color)s%(levelname)-8s %(asctime)s %(name)s %(message)s",
}
