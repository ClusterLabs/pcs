from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib import reports
from pcs.lib.cib.resource import primitive
from pcs.lib.node import NodeAddresses
from pcs.lib.resource_agent import find_valid_resource_agent_by_name

def find_node_list(resources_section):
    return [
        NodeAddresses(
            nvpair.attrib["value"],
            name=nvpair.getparent().getparent().attrib["id"]
        )
        for nvpair in resources_section.xpath("""
            .//primitive[
                @class="ocf"
                and
                @provider="pacemaker"
                and
                @type="remote"
            ]
            /instance_attributes
            /nvpair[@name="server" and string-length(@value) > 0]
        """)
    ]

def validate_host_not_ambiguous(host, instance_attributes):
    if instance_attributes.get("server", host) != host:
        return [
            reports.ambiguous_host_specification(
                [
                    host,
                    instance_attributes["server"]
                ]
            )
        ]
    return []

def prepare_instance_atributes(instance_attributes, host):
    enriched_resources = instance_attributes.copy()
    enriched_resources["server"] = host
    return enriched_resources

def create(
    report_processor, cmd_runner, resources_section, node_name,
    raw_operation_list=None, meta_attributes=None,
    instance_attributes=None,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
):
    return primitive.create(
        report_processor,
        resources_section,
        node_name,
        find_valid_resource_agent_by_name(
            report_processor,
            cmd_runner,
            "ocf:pacemaker:remote",
        ),
        raw_operation_list,
        meta_attributes,
        instance_attributes,
        allow_invalid_operation,
        allow_invalid_instance_attributes,
    )
