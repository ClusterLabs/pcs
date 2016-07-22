from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial

from pcs.lib.booth import reports
from pcs.lib.cib.resource import TAGS_ALL
from pcs.lib.cib.tools import find_unique_id
from pcs.lib.errors import LibraryError


def create_resource_id(resources_section, name, suffix):
    return find_unique_id(
        resources_section.getroottree(), "booth-{0}-{1}".format(name, suffix)
    )

def get_creator(resource_create, resource_group):
    #TODO resource_create and resource_group is provisional hack until resources
    #are not moved to lib
    def create_booth_in_cluster(
        resources_section, name, ip, booth_config_file_path
    ):
        create_id = partial(create_resource_id, resources_section, name)

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
        )
        resource_create(
            ra_id=booth_id,
            ra_type="ocf:pacemaker:booth-site",
            ra_values=["config={0}".format(booth_config_file_path)],
            op_values=[],
            meta_values=[],
            clone_opts=[],
        )
        resource_group(["add", group_id, ip_id, booth_id])
    return create_booth_in_cluster

def validate_no_booth_resource_using_config(
    resources_section, booth_config_file_path
):
    #self::primitive or self::clone or ... selects elements with specified tags
    xpath = (
        './/*['
        '    ('+' or '.join(["self::{0}".format(tag) for tag in TAGS_ALL])+')'
        '    and '
        '    @type="booth-site"'
        '    and '
        '    instance_attributes[nvpair[@name="config" and @value="{0}"]]'
        ']'
    ).format(booth_config_file_path)

    if resources_section.xpath(xpath):
        raise LibraryError(
            reports.booth_already_created(booth_config_file_path)
        )
