from functools import partial

from pcs.lib.cib.constraint import order

from . import common

# configure common constraint command
create_with_set = partial(
    common.create_with_set,
    order.TAG,
    order.prepare_options_with_set,
)
