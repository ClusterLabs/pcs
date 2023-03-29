import dataclasses
from typing import (
    Any,
    Optional,
    cast,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import InputModifiers
from pcs.cli.constraint import command
from pcs.cli.constraint.output import print_config
from pcs.cli.constraint_ticket import parse_args
from pcs.cli.reports.output import (
    deprecation_warning,
    error,
)
from pcs.common import reports
from pcs.common.pacemaker.constraint import CibConstraintsDto
from pcs.common.reports.messages import InvalidOptions
from pcs.common.types import StringSequence


def create_with_set(lib, argv, modifiers):
    """
    create ticket constraint with resource set
    object lib exposes library
    list argv see usage for "constraint colocation set"
    dict like object modifiers can contain
        "force" allows resource in clone/master and constraint duplicity

    Options:
      * --force - allow resource inside clone (or master), allow duplicate
        element
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--force", "-f")
    command.create_with_set(
        lib.constraint_ticket.create_with_set,
        argv,
        modifiers,
    )


def add(lib, argv, modifiers):
    """
    create ticket constraint
    object lib exposes library
    list argv see usage for "constraint colocation add"
    dict like object modifiers can contain
        "force" allows resource in clone/master and constraint duplicity

    Options:
      * --force - allow resource inside clone (or master), allow duplicate
        element
      * -f - CIB file
    """

    def _report_item_preprocessor(
        report_item: reports.ReportItem,
    ) -> Optional[reports.ReportItem]:
        if isinstance(report_item.message, InvalidOptions):
            new_message = dataclasses.replace(
                report_item.message,
                allowed=sorted(set(report_item.message.allowed) - {"rsc-role"}),
            )
            return dataclasses.replace(report_item, message=new_message)
        return report_item

    modifiers.ensure_only_supported("--force", "-f")
    ticket, resource_id, resource_role, options = parse_args.parse_add(argv)
    if "rsc-role" in options:
        raise CmdLineInputError(
            "Resource role must not be specified among options"
            + ", specify it before resource id"
        )

    if resource_role:
        options["rsc-role"] = resource_role

    lib.env.report_processor.set_report_item_preprocessor(
        _report_item_preprocessor
    )

    lib.constraint_ticket.create(
        ticket,
        resource_id,
        options,
        resource_in_clone_alowed=modifiers.get("--force"),
        duplication_alowed=modifiers.get("--force"),
    )


def remove(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if len(argv) != 2:
        raise CmdLineInputError()
    ticket, resource_id = argv
    if not lib.constraint_ticket.remove(ticket, resource_id):
        raise error("no matching ticket constraint found")


def show(lib, argv, modifiers):
    deprecation_warning(
        "This command is deprecated and will be removed. "
        "Please use 'pcs constraint ticket config' instead."
    )
    return config_cmd(lib, argv, modifiers)


def config_cmd(
    lib: Any, argv: StringSequence, modifiers: InputModifiers
) -> None:
    modifiers.ensure_only_supported("-f", "--output-format", "--full")
    if argv:
        raise CmdLineInputError()

    constraints_dto = cast(
        CibConstraintsDto,
        lib.constraint.get_config(evaluate_rules=True),
    )

    print_config(
        CibConstraintsDto(
            ticket=constraints_dto.ticket,
            ticket_set=constraints_dto.ticket_set,
        ),
        modifiers,
    )
