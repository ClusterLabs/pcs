import re

TRANSPORTS_KNET = ("knet", )
TRANSPORTS_UDP = ("udp", "udpu")
TRANSPORTS_ALL = TRANSPORTS_KNET + TRANSPORTS_UDP

LINKS_UDP_MIN = 1
LINKS_UDP_MAX = 1
LINKS_KNET_MIN = 1
LINKS_KNET_MAX = 8
LINKS_MAX = max(LINKS_KNET_MAX, LINKS_UDP_MAX)

NODE_OPTIONS = (
    ["name", "nodeid"]
    +
    [f"ring{i}_addr" for i in range(LINKS_MAX)]
)

IP_VERSION_VALUES = ("ipv4", "ipv6", "ipv4-6", "ipv6-4")

QUORUM_OPTIONS = (
    "auto_tie_breaker",
    "last_man_standing",
    "last_man_standing_window",
    "wait_for_all",
)

QUORUM_OPTIONS_INCOMPATIBLE_WITH_QDEVICE = (
    "auto_tie_breaker",
    "last_man_standing",
    "last_man_standing_window",
)

QUORUM_DEVICE_HEURISTICS_EXEC_NAME_RE = re.compile(r"^exec_[^.:{}#\s]+$")
