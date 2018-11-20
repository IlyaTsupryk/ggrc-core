# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

APPENGINE_INSTANCE=some-project
SETTINGS_MODULE="app_engine"
DB_NAME="database_name"
DB_INSTANCE_CONNECTION_NAME="database:connection:string"
SECRET_KEY="Something-secret"
GOOGLE_ANALYTICS_ID=""
GOOGLE_ANALYTICS_DOMAIN=""
GAPI_KEY="<Google Browser Key>"
GAPI_CLIENT_ID="<Google OAuth Client ID>"
GAPI_CLIENT_SECRET="<Google OAuth Client Secret>"
GAPI_ADMIN_GROUP="<Google Group Email Address>"
BOOTSTRAP_ADMIN_USERS="user@example.com"
MIGRATOR="Default Migrator <migrator@example.com>"
RISK_ASSESSMENT_URL="#"
CUSTOM_URL_ROOT=""
ABOUT_URL="#"
ABOUT_TEXT="About GGRC"
EXTERNAL_HELP_URL="#set_GGRC_EXTERNAL_HELP_URL_env_var"
EXTERNAL_IMPORT_HELP_URL="#set_GGRC_EXTERNAL_IMPORT_HELP_URL_env_var"
INSTANCE_CLASS="B4"
MAX_INSTANCES="4"
GGRC_Q_INTEGRATION_URL=""
INTEGRATION_SERVICE_URL=""
EXTERNAL_APP_USER="External App <external_app@example.com>"
URLFETCH_SERVICE_ID=""
ISSUE_TRACKER_ENABLED=""
ISSUE_TRACKER_BUG_URL_TMPL=""
DASHBOARD_INTEGRATION=""
ALLOWED_QUERYAPI_APP_IDS=""
APPENGINE_EMAIL=""
AUTHORIZED_DOMAIN=""
ACCESS_TOKEN=""
VERSION="AUTO" # valid version string or "AUTO" - can be omitted
COMPANY="Company, Inc."
COMPANY_LOGO_TEXT="Company GRC"
CREATE_ISSUE_URL=""
CREATE_ISSUE_BUTTON_NAME=""
APPENGINE_LOCATION="us-central1"

## generated values:

# example for manual scaling:
# SCALING=$(printf "manual_scaling:\\n  instances: ${MAX_INSTANCES}\\n")
SCALING=$(printf "basic_scaling:\\n  max_instances: ${MAX_INSTANCES}\\n  idle_timeout: 10m\\n")
DATABASE_URI="mysql+mysqldb://root@/${DB_NAME}?unix_socket=/cloudsql/${DB_INSTANCE_CONNECTION_NAME}&charset=utf8"
