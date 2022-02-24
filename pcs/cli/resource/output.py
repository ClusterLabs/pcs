from typing import List

from pcs.cli.common.output import format_with_indentation
from pcs.cli.resource_agent import get_resource_agent_full_name
from pcs.common import resource_agent
from pcs.common.pacemaker.resource.operations import CibResourceOperationDto
from pcs.common.str_tools import indent


def format_resource_agent_metadata(
    metadata: resource_agent.dto.ResourceAgentMetadataDto,
    default_operations: List[CibResourceOperationDto],
    verbose: bool = False,
) -> List[str]:
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-statements
    sub_section_indent = 2
    wrapped_line_indent = 4
    output = []
    is_stonith = metadata.name.standard == "stonith"
    agent_name = (
        metadata.name.type
        if is_stonith
        else get_resource_agent_full_name(metadata.name)
    )
    if metadata.shortdesc:
        output.extend(
            format_with_indentation(
                "{agent_name} - {shortdesc}".format(
                    agent_name=agent_name,
                    shortdesc=metadata.shortdesc.replace("\n", " "),
                ),
                indentation=wrapped_line_indent,
            )
        )
    else:
        output.append(agent_name)

    if metadata.longdesc:
        output.append("")
        output.extend(
            format_with_indentation(metadata.longdesc.replace("\n", " "))
        )

    params = []
    for param in metadata.parameters:
        if not verbose and (param.advanced or param.deprecated):
            continue
        param_title = [param.name]
        if param.deprecated_by:
            param_title.append(
                "(deprecated by {})".format(", ".join(param.deprecated_by))
            )
        elif param.deprecated:
            param_title.append("(deprecated)")
        if param.required:
            param_title.append("(required)")
        if param.unique_group:
            if param.unique_group.startswith(
                resource_agent.const.DEFAULT_UNIQUE_GROUP_PREFIX
            ):
                param_title.append("(unique)")
            else:
                param_title.append(
                    "(unique group: {})".format(param.unique_group)
                )
        desc = ""
        if param.longdesc:
            desc = param.longdesc.replace("\n", " ")
        if not desc and param.shortdesc:
            desc = param.shortdesc.replace("\n", " ")
        if not desc:
            desc = "No description available"
        if param.deprecated_desc:
            desc += "DEPRECATED: {param.deprecated_desc}"
        params.extend(
            format_with_indentation(
                "{}: {}".format(" ".join(param_title), desc),
                indentation=wrapped_line_indent,
                max_length_trim=sub_section_indent,
            )
        )
    if params:
        output.append("")
        if is_stonith:
            output.append("Stonith options:")
        else:
            output.append("Resource options:")
        output.extend(indent(params, sub_section_indent))

    operations = []
    for operation in default_operations:
        op_params = [f"interval={operation.interval}"]
        if operation.start_delay:
            op_params.append(f"start-delay={operation.start_delay}")
        if operation.timeout:
            op_params.append(f"timeout={operation.timeout}")
        if operation.role:
            op_params.append(f"role={operation.role}")
        # TODO: deal with depth aka OCF_CHECK_LEVEL
        operations.extend(
            format_with_indentation(
                "{name}: {params}".format(
                    name=operation.name, params=" ".join(op_params)
                ),
                indentation=wrapped_line_indent,
                max_length_trim=sub_section_indent,
            )
        )

    if operations:
        output.append("")
        output.append("Default operations:")
        output.extend(indent(operations, sub_section_indent))

    return output
