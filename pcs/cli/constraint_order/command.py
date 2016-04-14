from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.constraint import command
from pcs.cli.constraint_order import console_report


def create_with_set(lib, argv, modificators):
    command.create_with_set(
        lib.constraint_order.set,
        argv,
        modificators
    )

def show(lib, argv, modificators):
    print("\n".join(command.show(
        "Ordering Constraints:",
        lib.constraint_order.show,
        console_report.constraint_plain,
        modificators,
    )))
