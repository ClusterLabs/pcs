from collections.abc import Sequence

from pcs.common.pacemaker.fencing_topology import (
    CibFencingLevel,
    CibFencingLevelAttributeDto,
    CibFencingLevelRegexDto,
    CibFencingTopologyDto,
)
from pcs.common.str_tools import indent
from pcs.common.types import (
    StringCollection,
    StringSequence,
)


def _get_targets_with_levels_str(
    levels: Sequence[CibFencingLevel],
) -> list[str]:
    lines = []
    last_target_value = ""
    for level in levels:
        if isinstance(level, CibFencingLevelAttributeDto):
            target_label = "attribute"
            target_value = f"{level.target_attribute}={level.target_value}"
        elif isinstance(level, CibFencingLevelRegexDto):
            target_label = "regexp"
            target_value = level.target_pattern
        else:
            target_label = "node"
            target_value = level.target
        if target_value != last_target_value:
            lines.append(f"Target ({target_label}): {target_value}")
        last_target_value = target_value
        lines.extend(
            indent(
                [
                    "Level {level}: {devices}".format(
                        level=level.index, devices=" ".join(level.devices)
                    )
                ]
            )
        )
    return lines


def stonith_level_config_to_text(
    fencing_topology: CibFencingTopologyDto,
) -> StringSequence:
    target_node_levels = sorted(
        fencing_topology.target_node,
        key=lambda level: (level.target, level.index),
    )
    target_regex_levels = sorted(
        fencing_topology.target_regex,
        key=lambda level: (level.target_pattern, level.index),
    )
    target_attr_levels = sorted(
        fencing_topology.target_attribute,
        key=lambda level: (
            level.target_value,
            level.target_attribute,
            level.index,
        ),
    )

    return (
        _get_targets_with_levels_str(target_node_levels)
        + _get_targets_with_levels_str(target_regex_levels)
        + _get_targets_with_levels_str(target_attr_levels)
    )


def _get_level_add_cmd(
    index: int,
    target: str,
    device_list: StringCollection,
    level_id: str,
) -> str:
    devices = " ".join(device_list)
    return (
        f"pcs stonith level add --force -- {index} {target} {devices} "
        f"id={level_id}"
    )


def stonith_level_config_to_cmd(
    fencing_topology: CibFencingTopologyDto,
) -> StringSequence:
    lines: list[str] = []
    lines.extend(
        _get_level_add_cmd(level.index, level.target, level.devices, level.id)
        for level in fencing_topology.target_node
    )
    for level_regex in fencing_topology.target_regex:
        target = f"regexp%{level_regex.target_pattern}"
        lines.append(
            _get_level_add_cmd(
                level_regex.index, target, level_regex.devices, level_regex.id
            )
        )
    for level_attr in fencing_topology.target_attribute:
        target = (
            f"attrib%{level_attr.target_attribute}={level_attr.target_value}"
        )
        lines.append(
            _get_level_add_cmd(
                level_attr.index, target, level_attr.devices, level_attr.id
            )
        )

    return lines
