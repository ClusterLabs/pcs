from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial

from pcs.lib.cib.constraint import colocation
import pcs.lib.commands.constraint.common

#configure common constraint command
show = partial(
    pcs.lib.commands.constraint.common.show,
    colocation.TAG_NAME,
    lambda element: element.attrib.has_key('rsc')
)

#configure common constraint command
create_with_set = partial(
    pcs.lib.commands.constraint.common.create_with_set,
    colocation.TAG_NAME,
    colocation.prepare_options_with_set
)
