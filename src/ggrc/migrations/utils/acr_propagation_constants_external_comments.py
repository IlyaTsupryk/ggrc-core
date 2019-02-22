# Copyright (C) 2019 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""Module for keeping constants for ACR propagation rules
DO NOT MODIFY THESE VALUES.
These are just the common propagation dictionaries, that are used in different
migration files.
For migration consistency, do not update these values once they are merged.
If a modification is needed feel free to use these and modify them inside the
migration file, or add new common roles and propagation rules.
"""

COMMENT_DOCUMENT_RUD = {
    "Relationship R": {
        "ExternalComment R": {},
        "Document RU": {
            "Relationship R": {
                "ExternalComment R": {},
            }
        },
    },
}


CONTROL_ROLES = (
    "Admin",
    "Control Operators",
    "Control Owners",
    "Other Contacts",
    "Principal Assignees",
    "Secondary Assignees",
)


CONTROL_PROPAGATION_RULE = {
    "Control": {CONTROL_ROLES: COMMENT_DOCUMENT_RUD},
}
