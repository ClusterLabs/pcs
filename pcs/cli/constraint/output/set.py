from typing import (
    Optional,
    Sequence,
)

from pcs.cli.common.output import (
    INDENT_STEP,
    bool_to_cli_value,
    options_to_cmd,
    pairs_to_cmd,
)
from pcs.cli.reports.output import warn
from pcs.common.pacemaker.constraint import CibResourceSetDto
from pcs.common.str_tools import (
    format_list,
    format_optional,
    indent,
    pairs_to_text,
)
from pcs.common.types import StringSequence


def _resource_set_options_to_pairs(
    resource_set_dto: CibResourceSetDto,
) -> list[tuple[str, str]]:
    pairs = []
    if resource_set_dto.sequential is not None:
        pairs.append(
            ("sequential", bool_to_cli_value(resource_set_dto.sequential))
        )
    if resource_set_dto.require_all is not None:
        pairs.append(
            ("require-all", bool_to_cli_value(resource_set_dto.require_all))
        )
    if resource_set_dto.ordering:
        pairs.append(("ordering", resource_set_dto.ordering))
    if resource_set_dto.action:
        pairs.append(("action", resource_set_dto.action))
    if resource_set_dto.role:
        pairs.append(("role", resource_set_dto.role))
    if resource_set_dto.score:
        pairs.append(("score", resource_set_dto.score))
    if resource_set_dto.kind:
        pairs.append(("kind", resource_set_dto.kind.capitalize()))
    return pairs


def resource_set_to_text(
    resource_set_dto: CibResourceSetDto,
    with_id: bool,
) -> list[str]:
    output = [
        "Resource Set:{id}".format(
            id=f" {resource_set_dto.set_id}" if with_id else ""
        )
    ]
    set_options = [
        "Resources: {resources}".format(
            resources=format_list(resource_set_dto.resources_ids)
        )
    ] + pairs_to_text(_resource_set_options_to_pairs(resource_set_dto))
    output.extend(indent(set_options, indent_step=INDENT_STEP))
    return output


def set_constraint_to_text(
    constraint_id: str,
    constraint_attrs_lines: StringSequence,
    resource_sets: Sequence[CibResourceSetDto],
    with_id: bool,
) -> list[str]:
    header = "Set Constraint:"
    if with_id:
        header += f" {constraint_id}"
    result = [header]
    result.extend(indent(constraint_attrs_lines, indent_step=INDENT_STEP))
    for res_set_dto in resource_sets:
        result.extend(
            indent(
                resource_set_to_text(res_set_dto, with_id),
                indent_step=INDENT_STEP,
            )
        )
    return result


def resource_set_to_cmd(resource_set: CibResourceSetDto) -> Optional[list[str]]:
    filtered_pairs = []
    for pair in _resource_set_options_to_pairs(resource_set):
        # this list is based on pcs.lib.cib.constraint.resource_set._ATTRIBUTES
        if pair[0] not in ("action", "require-all", "role", "sequential"):
            warn(
                f"Option '{pair[0]}' detected in resource set "
                f"'{resource_set.set_id}' but not "
                "supported by this command."
                " Command for creating the constraint is omitted."
            )
            return None
        filtered_pairs.append(pair)

    return [
        "set {resources}{options}".format(
            resources=options_to_cmd(resource_set.resources_ids),
            options=format_optional(
                pairs_to_cmd(filtered_pairs),
                template=" {}",
            ),
        )
    ]
