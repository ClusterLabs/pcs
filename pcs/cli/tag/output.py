import json
import shlex

from pcs.cli.common.output import lines_to_str
from pcs.cli.common.parse_args import (
    OUTPUT_FORMAT_VALUE_CMD,
    OUTPUT_FORMAT_VALUE_JSON,
    InputModifiers,
)
from pcs.common.interface import dto
from pcs.common.pacemaker.tag import CibTagListDto
from pcs.common.str_tools import indent


def tags_to_text(tags_dto: CibTagListDto) -> list[str]:
    result = []
    for tag in tags_dto.tags:
        result.append(tag.id)
        result.extend(indent(list(tag.idref_list)))
    return result


def tags_to_cmd(tags_dto: CibTagListDto) -> list[str]:
    return [
        "pcs -- tag create {tag_id} {idref_list}".format(
            tag_id=shlex.quote(tag.id),
            idref_list=" ".join(shlex.quote(idref) for idref in tag.idref_list),
        )
        for tag in tags_dto.tags
    ]


def print_config(tags_dto: CibTagListDto, modifiers: InputModifiers) -> None:
    output_format = modifiers.get_output_format()
    if output_format == OUTPUT_FORMAT_VALUE_JSON:
        print(json.dumps(dto.to_dict(tags_dto), indent=2))
        return

    if output_format == OUTPUT_FORMAT_VALUE_CMD:
        print(";\n".join(tags_to_cmd(tags_dto)))
        return

    result = lines_to_str(tags_to_text(tags_dto))
    if result:
        print(result)
