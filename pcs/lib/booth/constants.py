from pcs import settings
from pcs.common.types import StringCollection

DEFAULT_INSTANCE_NAME = "booth"
AUTHFILE_FIX_OPTION = "enable-authfile"

GLOBAL_KEYS: StringCollection = (
    "transport",
    "port",
    "name",
    "authfile",
    "maxtimeskew",
    "site",
    "arbitrator",
    "site-user",
    "site-group",
    "arbitrator-user",
    "arbitrator-group",
    "debug",
    "ticket",
) + (
    (AUTHFILE_FIX_OPTION,)
    if settings.booth_enable_authfile_set_enabled
    or settings.booth_enable_authfile_unset_enabled
    else tuple()
)

TICKET_KEYS = (
    "acquire-after",
    "attr-prereq",
    "before-acquire-handler",
    "expire",
    "mode",
    "renewal-freq",
    "retries",
    "timeout",
    "weights",
)
