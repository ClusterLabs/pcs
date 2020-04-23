from .types import (
    DefaultAddressSource,
    ReasonType,
    ServiceAction,
)

SERVICE_ACTION_START = ServiceAction("START")
SERVICE_ACTION_STOP = ServiceAction("STOP")
SERVICE_ACTION_ENABLE = ServiceAction("ENABLE")
SERVICE_ACTION_DISABLE = ServiceAction("DISABLE")
SERVICE_ACTION_KILL = ServiceAction("KILL")

REASON_UNREACHABLE = ReasonType("unreachable")
REASON_NOT_LIVE_CIB = ReasonType("not_live_cib")

DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS = DefaultAddressSource("known_hosts")
DEFAULT_ADDRESS_SOURCE_HOST_NAME = DefaultAddressSource("host_name")
