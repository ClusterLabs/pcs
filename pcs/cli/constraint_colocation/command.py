from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.constraint import command
from pcs.cli.constraint_colocation import console_report


def create_with_set(lib, argv, modificators):
    command.create_with_set(
        lib.constraint_colocation.set,
        argv,
        modificators,
    )

def show(lib, argv, modificators):
    print("\n".join(command.show(
         "Colocation Constraints:",
        lib.constraint_colocation.show,
        console_report.constraint_plain,
        modificators,
    )))
