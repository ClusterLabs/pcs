from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial
from pcs.lib.cib.constraint import order
import pcs.lib.commands.constraint.common

show = partial(
    pcs.lib.commands.constraint.common.show,
    order.TAG_NAME,
    lambda element: element.attrib.has_key('first')
)

create_with_set = partial(
    pcs.lib.commands.constraint.common.create_with_set,
    order.TAG_NAME,
    order.prepare_options_with_set
)
