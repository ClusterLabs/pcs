from functools import partial

from pcs.lib.cib.constraint import colocation

from . import common

# configure common constraint command
config = partial(
    common.config,
    colocation.TAG_NAME,
    lambda element: element.attrib.has_key("rsc"),
)

# configure common constraint command
create_with_set = partial(
    common.create_with_set,
    colocation.TAG_NAME,
    colocation.prepare_options_with_set,
)
