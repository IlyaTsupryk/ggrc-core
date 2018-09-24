# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""List of all error and warning messages for the app."""

BAD_REQUEST_MESSAGE = (u"Server error occurred. Please contact your "
                       u"system administrator to receive more details.")

WRONG_STATUS = u"Wrong status."

BAD_PARAMS = u"Bad request parameters."

INCORRECT_REQUEST_DATA = u"{job_type} failed due incorrect request data."

INTERNAL_SERVER_ERROR = u"{job_type} failed due to internal server error."

JOB_FAILED = u"{job_type} failed."

PREVIOUS_RUN_FAILED = u"Previous run has failed."

STATUS_SET_FAILED = u"Failed to set job status"

RELOAD_PAGE = u"Try to reload /export page."

MISSING_FILE = u"The file is missing."

WRONG_FILE_TYPE = u"Invalid file type."

MANDATORY_HEADER = u"{} should be set, contains {!r} instead."

WRONG_PERSON_HEADER_FORMAT = u"{} should have JSON object like" \
                             u" {{'email': str}}, contains {!r} instead."
