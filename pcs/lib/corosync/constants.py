import re

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

QUORUM_DEVICE_HEURISTICS_EXEC_NAME_RE = re.compile("^exec_[^.:{}#\s]+$")
