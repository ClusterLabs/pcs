from functools import partial

from pcs.lib.cib.constraint import order

from . import common

# configure common constraint command
config = partial(
    common.config,
    order.TAG_NAME,
    lambda element: element.attrib.has_key("first"),
)

# configure common constraint command
create_with_set = partial(
    common.create_with_set,
    order.TAG_NAME,
    order.prepare_options_with_set,
)
