from typing import (
    Iterable,
    List,
)

from pcs.cli.rule import (
    get_in_effect_label,
    rule_expression_dto_to_lines,
)
from pcs.common.pacemaker.nvset import CibNvsetDto
from pcs.common.str_tools import (
    format_name_value_id_list,
    format_name_value_list,
    format_optional,
    indent,
)
from pcs.common.types import CibRuleInEffectStatus


def filter_out_expired_nvset(
    nvset_dto_list: Iterable[CibNvsetDto],
) -> list[CibNvsetDto]:
    return [
        nvset_dto
        for nvset_dto in nvset_dto_list
        if not nvset_dto.rule
        or nvset_dto.rule.in_effect != CibRuleInEffectStatus.EXPIRED
    ]


def nvset_dto_list_to_lines(
    nvset_dto_list: Iterable[CibNvsetDto],
    nvset_label: str,
    with_ids: bool = False,
) -> List[str]:
    return [
        line
        for nvset_dto in nvset_dto_list
        for line in nvset_dto_to_lines(
            nvset_dto, nvset_label=nvset_label, with_ids=with_ids
        )
    ]


def nvset_dto_to_lines(
    nvset: CibNvsetDto, nvset_label: str = "Options Set", with_ids: bool = False
) -> List[str]:
    in_effect_label = get_in_effect_label(nvset.rule) if nvset.rule else None
    heading_parts = [
        "{label}{in_effect}:{id}".format(
            label=nvset_label,
            in_effect=format_optional(in_effect_label, " ({})"),
            id=format_optional(nvset.id, " {}"),
        )
    ]
    if nvset.options:
        heading_parts.append(
            " ".join(format_name_value_list(sorted(nvset.options.items())))
        )

    if with_ids:
        lines = format_name_value_id_list(
            sorted(
                [
                    (nvpair.name, nvpair.value, nvpair.id)
                    for nvpair in nvset.nvpairs
                ]
            )
        )
    else:
        lines = format_name_value_list(
            sorted([(nvpair.name, nvpair.value) for nvpair in nvset.nvpairs])
        )

    if nvset.rule:
        lines.extend(
            rule_expression_dto_to_lines(nvset.rule, with_ids=with_ids)
        )

    return [" ".join(heading_parts)] + indent(lines)
