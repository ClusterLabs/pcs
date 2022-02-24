from functools import partial

import pcs.lib.commands.constraint.common
from pcs.lib.cib.constraint import colocation

# configure common constraint command
config = partial(
    pcs.lib.commands.constraint.common.config,
    colocation.TAG_NAME,
    lambda element: element.attrib.has_key("rsc"),
)

# configure common constraint command
create_with_set = partial(
    pcs.lib.commands.constraint.common.create_with_set,
    colocation.TAG_NAME,
    colocation.prepare_options_with_set,
)
