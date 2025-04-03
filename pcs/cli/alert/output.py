import shlex
from typing import Optional, Sequence, Union

from pcs.cli.common.output import (
    INDENT_STEP,
    pairs_to_cmd,
)
from pcs.cli.nvset import nvset_dto_to_lines
from pcs.common.pacemaker.alert import (
    CibAlertDto,
    CibAlertListDto,
    CibAlertRecipientDto,
    CibAlertSelectDto,
)
from pcs.common.pacemaker.nvset import CibNvsetDto
from pcs.common.str_tools import (
    format_list,
    format_optional,
    indent,
)


def _description_to_lines(desc: Optional[str]) -> list[str]:
    return [f"Description: {desc}"] if desc else []


def _nvsets_to_lines(label: str, nvsets: Sequence[CibNvsetDto]) -> list[str]:
    if nvsets and nvsets[0].nvpairs:
        return nvset_dto_to_lines(nvset=nvsets[0], nvset_label=label)
    return []


def _recipient_dto_to_lines(recipient_dto: CibAlertRecipientDto) -> list[str]:
    lines = (
        _description_to_lines(recipient_dto.description)
        + [f"Value: {recipient_dto.value}"]
        + _nvsets_to_lines("Attributes", recipient_dto.instance_attributes)
        + _nvsets_to_lines("Meta Attributes", recipient_dto.meta_attributes)
    )
    return [f"Recipient: {recipient_dto.id}"] + indent(
        lines, indent_step=INDENT_STEP
    )


def _recipients_to_lines(
    recipient_dto_list: Sequence[CibAlertRecipientDto],
) -> list[str]:
    if not recipient_dto_list:
        return []
    lines = []
    for recipient_dto in recipient_dto_list:
        lines.extend(_recipient_dto_to_lines(recipient_dto))
    return ["Recipients:"] + indent(lines, indent_step=INDENT_STEP)


def _select_dto_to_lines(select_dto: Optional[CibAlertSelectDto]) -> list[str]:
    if not select_dto:
        return []
    lines = []
    if select_dto.nodes:
        lines.append("nodes")
    if select_dto.fencing:
        lines.append("fencing")
    if select_dto.resources:
        lines.append("resources")
    if select_dto.attributes:
        attr_names = format_list(
            attr.name for attr in select_dto.attributes_select
        )
        lines.append("attributes" + format_optional(attr_names, ": {}"))
    return ["Receives:"] + indent(lines, indent_step=INDENT_STEP)


def alert_dto_to_lines(alert_dto: CibAlertDto) -> list[str]:
    lines = (
        _description_to_lines(alert_dto.description)
        + [f"Path: {alert_dto.path}"]
        + _recipients_to_lines(alert_dto.recipients)
        + _select_dto_to_lines(alert_dto.select)
        + _nvsets_to_lines("Attributes", alert_dto.instance_attributes)
        + _nvsets_to_lines("Meta Attributes", alert_dto.meta_attributes)
    )
    return [f"Alert: {alert_dto.id}"] + indent(lines, indent_step=INDENT_STEP)


def config_dto_to_lines(config_dto: CibAlertListDto) -> list[str]:
    result = []
    for alert_dto in config_dto.alerts:
        result.extend(alert_dto_to_lines(alert_dto))
    return result


def config_dto_to_cmd(config_dto: CibAlertListDto) -> list[str]:
    commands = []
    for alert_dto in config_dto.alerts:
        # alert
        alert_parts = [
            "pcs -- alert create path={path} id={id}".format(
                path=shlex.quote(alert_dto.path), id=shlex.quote(alert_dto.id)
            )
        ] + _desc_instance_meta_to_cmd(alert_dto)
        # TODO export select, once it is supported by pcs
        commands.append(" ".join(alert_parts))
        # recipients
        for recipient_dto in alert_dto.recipients:
            recipient_parts = [
                "pcs -- alert recipient add {alert_id} value={value} id={id}".format(
                    alert_id=shlex.quote(alert_dto.id),
                    value=shlex.quote(recipient_dto.value),
                    id=shlex.quote(recipient_dto.id),
                )
            ] + _desc_instance_meta_to_cmd(recipient_dto)
            commands.append(" ".join(recipient_parts))
    return commands


def _nvset_to_cmd(
    label: Optional[str],
    nvsets: Sequence[CibNvsetDto],
) -> list[str]:
    if nvsets and nvsets[0].nvpairs:
        options = pairs_to_cmd(
            (nvpair.name, nvpair.value) for nvpair in nvsets[0].nvpairs
        )
        if label:
            options = f"{label} {options}"
        return [options]
    return []


def _desc_instance_meta_to_cmd(
    dto: Union[CibAlertDto, CibAlertRecipientDto],
) -> list[str]:
    parts = []
    if dto.description:
        parts.append(
            "description={desc}".format(desc=shlex.quote(dto.description))
        )
    parts.extend(_nvset_to_cmd("options", dto.instance_attributes))
    parts.extend(_nvset_to_cmd("meta", dto.meta_attributes))
    return parts
