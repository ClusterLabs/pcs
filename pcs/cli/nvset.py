from typing import (
    cast,
    Iterable,
    List,
    Optional,
)

from pcs.cli.rule import (
    get_in_effect_label,
    rule_expression_dto_to_lines,
)
from pcs.common.pacemaker.nvset import CibNvsetDto
from pcs.common.str_tools import (
    format_name_value_list,
    format_optional,
    indent,
)
from pcs.common.types import (
    CibNvsetType,
    CibRuleInEffectStatus,
)


def nvset_dto_list_to_lines(
    nvset_dto_list: Iterable[CibNvsetDto],
    with_ids: bool = False,
    include_expired: bool = False,
    text_if_empty: Optional[str] = None,
) -> List[str]:
    if not nvset_dto_list:
        return [text_if_empty] if text_if_empty else []
    if not include_expired:
        nvset_dto_list = [
            nvset_dto
            for nvset_dto in nvset_dto_list
            if not nvset_dto.rule
            or nvset_dto.rule.in_effect != CibRuleInEffectStatus.EXPIRED
        ]
    return [
        line
        for nvset_dto in nvset_dto_list
        for line in nvset_dto_to_lines(nvset_dto, with_ids=with_ids)
    ]


def nvset_dto_to_lines(nvset: CibNvsetDto, with_ids: bool = False) -> List[str]:
    nvset_label = _nvset_type_to_label.get(nvset.type, "Options Set")
    in_effect_label = get_in_effect_label(nvset.rule) if nvset.rule else None
    heading_parts = [
        "{label}{in_effect}: {id}".format(
            label=nvset_label,
            in_effect=format_optional(in_effect_label, " ({})"),
            id=nvset.id,
        )
    ]
    if nvset.options:
        heading_parts.append(
            " ".join(format_name_value_list(sorted(nvset.options.items())))
        )

    lines = format_name_value_list(
        sorted([(nvpair.name, nvpair.value) for nvpair in nvset.nvpairs])
    )
    if nvset.rule:
        lines.extend(
            rule_expression_dto_to_lines(nvset.rule, with_ids=with_ids)
        )

    return [" ".join(heading_parts)] + indent(lines)


_nvset_type_to_label = {
    cast(str, CibNvsetType.INSTANCE): "Attributes",
    cast(str, CibNvsetType.META): "Meta Attrs",
}
