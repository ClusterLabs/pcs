from pcs.common.pacemaker.resource.operations import (
    OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME,
)

OPERATION_ATTRIBUTES = [
    "id",
    "description",
    "enabled",
    "interval",
    "interval-origin",
    "name",
    "on-fail",
    "record-pending",
    "role",
    "start-delay",
    "timeout",
    OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME,
]
