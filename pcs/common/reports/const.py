from .types import (
    AddRemoveContainerType,
    AddRemoveItemType,
    BoothConfigUsedWhere,
    DefaultAddressSource,
    FenceHistoryCommandType,
    PcsCommand,
    ReasonType,
    ServiceAction,
    StonithRestartlessUpdateUnableToPerformReason,
)

ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE = AddRemoveContainerType("stonith")
ADD_REMOVE_CONTAINER_TYPE_GROUP = AddRemoveContainerType("group")
ADD_REMOVE_ITEM_TYPE_DEVICE = AddRemoveItemType("device")
ADD_REMOVE_ITEM_TYPE_RESOURCE = AddRemoveItemType("resource")
BOOTH_CONFIG_USED_IN_CLUSTER_RESOURCE = BoothConfigUsedWhere(
    "in a cluster resource"
)
BOOTH_CONFIG_USED_ENABLED_IN_SYSTEMD = BoothConfigUsedWhere(
    "enabled in systemd"
)
BOOTH_CONFIG_USED_RUNNING_IN_SYSTEMD = BoothConfigUsedWhere(
    "running in systemd"
)

FENCE_HISTORY_COMMAND_CLEANUP = FenceHistoryCommandType("cleanup")
FENCE_HISTORY_COMMAND_SHOW = FenceHistoryCommandType("show")
FENCE_HISTORY_COMMAND_UPDATE = FenceHistoryCommandType("update")

PCS_COMMAND_OPERATION_DEFAULTS_UPDATE = PcsCommand(
    "resource op defaults update"
)
PCS_COMMAND_RESOURCE_DEFAULTS_UPDATE = PcsCommand("resource defaults update")

SERVICE_ACTION_START = ServiceAction("START")
SERVICE_ACTION_STOP = ServiceAction("STOP")
SERVICE_ACTION_ENABLE = ServiceAction("ENABLE")
SERVICE_ACTION_DISABLE = ServiceAction("DISABLE")
SERVICE_ACTION_KILL = ServiceAction("KILL")

REASON_UNREACHABLE = ReasonType("unreachable")
REASON_NOT_LIVE_CIB = ReasonType("not_live_cib")

DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS = DefaultAddressSource("known_hosts")
DEFAULT_ADDRESS_SOURCE_HOST_NAME = DefaultAddressSource("host_name")

STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_NOT_RUNNING = (
    StonithRestartlessUpdateUnableToPerformReason("not_running")
)
STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM_REASON_OTHER = (
    StonithRestartlessUpdateUnableToPerformReason("other")
)
