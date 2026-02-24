from dataclasses import replace
from typing import Iterable, Mapping, Optional

from pcs.cli.rule import (
    get_in_effect_label,
    rule_expression_dto_to_lines,
)
from pcs.common.pacemaker.nvset import CibNvpairDto, CibNvsetDto
from pcs.common.str_tools import (
    format_name_optional_value_list,
    format_name_value_id_list,
    format_name_value_list,
    format_optional,
    indent,
)
from pcs.common.types import CibRuleInEffectStatus, StringSequence


def filter_out_expired_nvset(
    nvset_dto_list: Iterable[CibNvsetDto],
) -> list[CibNvsetDto]:
    return [
        nvset_dto
        for nvset_dto in nvset_dto_list
        if not nvset_dto.rule
        or nvset_dto.rule.in_effect != CibRuleInEffectStatus.EXPIRED
    ]


def filter_nvpairs_by_names(
    nvsets: Iterable[CibNvsetDto], nvpair_names: StringSequence
) -> list[CibNvsetDto]:
    return [
        replace(
            nvset_dto,
            nvpairs=[
                nvpair_dto
                for nvpair_dto in nvset_dto.nvpairs
                if nvpair_dto.name in nvpair_names
            ],
        )
        for nvset_dto in nvsets
    ]


def _get_nvpairs_by_sensitivity(
    nvset_dto: CibNvsetDto,
    secrets_map: Mapping[str, Optional[str]],
    sensitive: bool,
) -> list[CibNvpairDto]:
    if not secrets_map:
        return [] if sensitive else list(nvset_dto.nvpairs)
    return [
        nvpair_dto
        for nvpair_dto in nvset_dto.nvpairs
        if (
            sensitive
            and nvpair_dto.name in secrets_map
            or not sensitive
            and nvpair_dto.name not in secrets_map
        )
    ]


def _get_secret_nvpairs(
    nvset_dto: CibNvsetDto, secrets_map: Mapping[str, Optional[str]]
) -> list[CibNvpairDto]:
    return _get_nvpairs_by_sensitivity(nvset_dto, secrets_map, True)


def _get_non_secret_nvpairs(
    nvset_dto: CibNvsetDto, secrets_map: Mapping[str, Optional[str]]
) -> list[CibNvpairDto]:
    return _get_nvpairs_by_sensitivity(nvset_dto, secrets_map, False)


def nvset_dto_list_to_lines(
    nvset_dto_list: Iterable[CibNvsetDto],
    nvset_label: str,
    with_ids: bool = False,
    secrets_map: Optional[Mapping[str, Optional[str]]] = None,
) -> list[str]:
    return [
        line
        for nvset_dto in nvset_dto_list
        for line in nvset_dto_to_lines(
            nvset_dto,
            nvset_label=nvset_label,
            with_ids=with_ids,
            secrets_map=secrets_map,
        )
    ]


def nvset_dto_to_lines(
    nvset: CibNvsetDto,
    nvset_label: str = "Options Set",
    with_ids: bool = False,
    secrets_map: Optional[Mapping[str, Optional[str]]] = None,
) -> list[str]:
    if secrets_map is None:
        secrets_map = {}
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
                    for nvpair in _get_non_secret_nvpairs(nvset, secrets_map)
                ]
            )
        )
    else:
        lines = format_name_value_list(
            sorted(
                [
                    (nvpair.name, nvpair.value)
                    for nvpair in _get_non_secret_nvpairs(nvset, secrets_map)
                ]
            )
        )

    secret_lines = format_name_optional_value_list(
        sorted(
            (nvpair.name, secrets_map[nvpair.name])
            for nvpair in _get_secret_nvpairs(nvset, secrets_map)
        )
    )
    if secret_lines:
        lines.extend(["Secret Attributes:"] + indent(secret_lines))
    if nvset.rule:
        lines.extend(
            rule_expression_dto_to_lines(nvset.rule, with_ids=with_ids)
        )
    return [" ".join(heading_parts)] + indent(lines)
