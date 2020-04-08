import re

TRANSPORT_DEFAULT = "knet"
TRANSPORTS_KNET = ("knet",)
TRANSPORTS_UDP = ("udp", "udpu")
TRANSPORTS_ALL = TRANSPORTS_KNET + TRANSPORTS_UDP

LINKS_UDP_MIN = 1
LINKS_UDP_MAX = 1
LINKS_KNET_MIN = 1
LINKS_KNET_MAX = 8
LINKS_MAX = max(LINKS_KNET_MAX, LINKS_UDP_MAX)

NODE_OPTIONS = ["name", "nodeid"] + [f"ring{i}_addr" for i in range(LINKS_MAX)]

IP_VERSION_4 = "ipv4"
IP_VERSION_6 = "ipv6"
IP_VERSION_46 = "ipv4-6"
IP_VERSION_64 = "ipv6-4"
IP_VERSION_VALUES = (IP_VERSION_4, IP_VERSION_6, IP_VERSION_46, IP_VERSION_64)

# This must list ALL knet options even if they translate to themselves.
# The list is used to get a set of allowed options.
LINK_OPTIONS_KNET_TRANSLATION = (
    # (user facing name, corosync.conf name)
    ("linknumber", "linknumber"),
    ("link_priority", "knet_link_priority"),
    ("mcastport", "mcastport"),
    ("ping_interval", "knet_ping_interval"),
    ("ping_precision", "knet_ping_precision"),
    ("ping_timeout", "knet_ping_timeout"),
    ("pong_count", "knet_pong_count"),
    ("transport", "knet_transport"),
)
# This is what pcs expects to get from users. Actual names in corosync.conf are
# different.
LINK_OPTIONS_KNET_USER = tuple(
    sorted([pair[0] for pair in LINK_OPTIONS_KNET_TRANSLATION])
)
# This is what corsync works with.
LINK_OPTIONS_KNET_COROSYNC = tuple(
    sorted([pair[1] for pair in LINK_OPTIONS_KNET_TRANSLATION])
)

LINK_OPTIONS_UDP = (
    "bindnetaddr",
    "broadcast",
    "mcastaddr",
    "mcastport",
    "ttl",
)

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

OPTION_NAME_RE = re.compile(r"^[-_/a-zA-Z0-9]+$")
QUORUM_DEVICE_HEURISTICS_EXEC_NAME_RE = re.compile(r"^exec_[-_/a-zA-Z0-9]+$")
