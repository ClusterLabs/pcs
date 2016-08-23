from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib.cib.tools import find_unique_id


def create_resource_id(resources_section, name, suffix):
    return find_unique_id(
        resources_section.getroottree(), "booth-{0}-{1}".format(name, suffix)
    )

def get_creator(resource_create, resource_remove=None):
    #TODO resource_create  is provisional hack until resources are not moved to
    #lib
    def create_booth_in_cluster(ip, booth_config_file_path, create_id):
        ip_id = create_id("ip")
        booth_id = create_id("service")
        group_id = create_id("group")

        resource_create(
            ra_id=ip_id,
            ra_type="ocf:heartbeat:IPaddr2",
            ra_values=["ip={0}".format(ip)],
            op_values=[],
            meta_values=[],
            clone_opts=[],
            group=group_id,
        )
        try:
            resource_create(
                ra_id=booth_id,
                ra_type="ocf:pacemaker:booth-site",
                ra_values=["config={0}".format(booth_config_file_path)],
                op_values=[],
                meta_values=[],
                clone_opts=[],
                group=group_id,
            )
        except SystemExit:
            resource_remove(ip_id)
    return create_booth_in_cluster

def is_ip_resource(resource_element):
    return resource_element.attrib["type"] == "IPaddr2"

def find_grouped_ip_element_to_remove(booth_element):
    if booth_element.getparent().tag != "group":
        return None

    group = booth_element.getparent()
    if len(group) != 2:
        #when something else in group, ip is not for remove
        return None
    for element in group:
        if is_ip_resource(element):
            return element
    return None

def get_remover(resource_remove):
    def remove_from_cluster(booth_element_list):
        for element in booth_element_list:
            ip_resource_to_remove = find_grouped_ip_element_to_remove(element)
            if ip_resource_to_remove is not None:
                resource_remove(ip_resource_to_remove.attrib["id"])
            resource_remove(element.attrib["id"])

    return remove_from_cluster

def find_for_config(resources_section, booth_config_file_path):
    return resources_section.xpath(("""
        .//primitive[
            @type="booth-site"
            and
            instance_attributes[nvpair[@name="config" and @value="{0}"]]
        ]
    """).format(booth_config_file_path))

def find_bound_ip(resources_section, booth_config_file_path):
    return resources_section.xpath(("""
        .//group[
            primitive[
                @type="booth-site"
                and
                instance_attributes[
                    nvpair[@name="config" and @value="{0}"]
                ]
            ]
        ]
        /primitive[@type="IPaddr2"]
        /instance_attributes
        /nvpair[@name="ip"]
        /@value
    """).format(booth_config_file_path))
