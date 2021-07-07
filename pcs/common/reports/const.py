from .types import (
    BoothConfigUsedWhere,
    DefaultAddressSource,
    FenceHistoryCommandType,
    PcsCommand,
    ReasonType,
    ServiceAction,
    StonithUnableToUpdateScsiDevicesReason,
)


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

STONITH_UNABLE_TO_UPDATE_SCSI_DEVICES_REASON_NOT_RUNNING = (
    StonithUnableToUpdateScsiDevicesReason("not_running")
)
STONITH_UNABLE_TO_UPDATE_SCSI_DEVICES_REASON_OTHER = (
    StonithUnableToUpdateScsiDevicesReason("other")
)
