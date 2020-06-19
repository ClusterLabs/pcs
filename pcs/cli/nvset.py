from typing import (
    cast,
    Iterable,
    List,
    Optional,
)

from pcs.cli.rule import rule_expression_dto_to_lines
from pcs.common.pacemaker.nvset import CibNvsetDto
from pcs.common.str_tools import (
    format_name_value_list,
    indent,
)
from pcs.common.types import CibNvsetType


def nvset_dto_list_to_lines(
    nvset_dto_list: Iterable[CibNvsetDto],
    with_ids: bool = False,
    text_if_empty: Optional[str] = None,
) -> List[str]:
    if not nvset_dto_list:
        return [text_if_empty] if text_if_empty else []
    return [
        line
        for nvset_dto in nvset_dto_list
        for line in nvset_dto_to_lines(nvset_dto, with_ids=with_ids)
    ]


def nvset_dto_to_lines(nvset: CibNvsetDto, with_ids: bool = False) -> List[str]:
    nvset_label = _nvset_type_to_label.get(nvset.type, "Options Set")
    heading_parts = [f"{nvset_label}: {nvset.id}"]
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
