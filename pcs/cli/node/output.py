import shlex
from typing import Optional, Sequence

from pcs.cli.common.output import (
    INDENT_STEP,
    pairs_to_cmd,
)
from pcs.cli.nvset import filter_nvpairs_by_names, nvset_dto_to_lines
from pcs.common.pacemaker.node import CibNodeDto, CibNodeListDto
from pcs.common.pacemaker.nvset import CibNvsetDto
from pcs.common.str_tools import (
    indent,
)


def _description_to_lines(desc: Optional[str]) -> list[str]:
    return [f"Description: {desc}"] if desc else []


def _nvsets_to_lines(label: str, nvsets: Sequence[CibNvsetDto]) -> list[str]:
    if nvsets and nvsets[0].nvpairs:
        return nvset_dto_to_lines(nvset=nvsets[0], nvset_label=label)
    return []


def _node_dto_to_nvset_lines(
    node_dto: CibNodeDto, label: str, nvsets: Sequence[CibNvsetDto]
) -> list[str]:
    nvsets_lines = _nvsets_to_lines(label, nvsets)
    if not nvsets_lines:
        return []
    lines = _description_to_lines(node_dto.description)
    lines.extend(nvsets_lines)
    return [f"Node: {node_dto.uname}"] + indent(lines, indent_step=INDENT_STEP)


def node_utilization_to_lines(config_dto: CibNodeListDto) -> list[str]:
    result = []
    for node_dto in config_dto.nodes:
        result.extend(
            _node_dto_to_nvset_lines(
                node_dto, "Utilization", node_dto.utilization
            )
        )
    return result


def node_attribute_to_lines(config_dto: CibNodeListDto) -> list[str]:
    result = []
    for node_dto in config_dto.nodes:
        result.extend(
            _node_dto_to_nvset_lines(
                node_dto, "Attributes", node_dto.instance_attributes
            )
        )
    return result


def _nvsets_to_cmd(
    nvset_cmd: str, node_name: str, nvsets: Sequence[CibNvsetDto]
) -> list[str]:
    if nvsets and nvsets[0].nvpairs:
        nvset_cmd = shlex.quote(nvset_cmd)
        node = shlex.quote(node_name)
        options = pairs_to_cmd(
            (nvpair.name, nvpair.value) for nvpair in nvsets[0].nvpairs
        )
        return [f"pcs -- node {nvset_cmd} {node} {options}"]
    return []


def config_dto_to_attribute_cmd(config_dto: CibNodeListDto) -> list[str]:
    commands = []
    for node_dto in config_dto.nodes:
        commands.extend(
            _nvsets_to_cmd(
                "attribute", node_dto.uname, node_dto.instance_attributes
            )
        )
    return commands


def config_dto_to_utilization_cmd(config_dto: CibNodeListDto) -> list[str]:
    commands = []
    for node_dto in config_dto.nodes:
        commands.extend(
            _nvsets_to_cmd("utilization", node_dto.uname, node_dto.utilization)
        )
    return commands


def filter_nodes_by_node_name(
    config_dto: CibNodeListDto, node_name: str
) -> CibNodeListDto:
    return CibNodeListDto(
        nodes=[
            node_dto
            for node_dto in config_dto.nodes
            if node_dto.uname == node_name
        ]
    )


def filter_nodes_by_nvpair_name(
    config_dto: CibNodeListDto, name: str
) -> CibNodeListDto:
    return CibNodeListDto(
        [
            CibNodeDto(
                id=node_dto.id,
                uname=node_dto.uname,
                description=node_dto.description,
                score=node_dto.score,
                type=node_dto.type,
                instance_attributes=filter_nvpairs_by_names(
                    node_dto.instance_attributes, [name]
                ),
                utilization=filter_nvpairs_by_names(
                    node_dto.utilization, [name]
                ),
            )
            for node_dto in config_dto.nodes
        ]
    )
