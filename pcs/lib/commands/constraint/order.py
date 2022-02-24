from functools import partial

import pcs.lib.commands.constraint.common
from pcs.lib.cib.constraint import order

# configure common constraint command
config = partial(
    pcs.lib.commands.constraint.common.config,
    order.TAG_NAME,
    lambda element: element.attrib.has_key("first"),
)

# configure common constraint command
create_with_set = partial(
    pcs.lib.commands.constraint.common.create_with_set,
    order.TAG_NAME,
    order.prepare_options_with_set,
)
