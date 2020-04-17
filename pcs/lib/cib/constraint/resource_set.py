from lxml import etree

from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.lib.cib.tools import find_unique_id
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import RESOURCE_ROLES
from pcs.lib.xml_tools import export_attributes

ATTRIB = {
    "sequential": ("true", "false"),
    "require-all": ("true", "false"),
    "action": ("start", "promote", "demote", "stop"),
    "role": RESOURCE_ROLES,
}


def prepare_set(find_valid_id, resource_set):
    """return resource_set with corrected ids"""
    validate_options(resource_set["options"])
    return {
        "ids": [find_valid_id(id) for id in resource_set["ids"]],
        "options": resource_set["options"],
    }


def validate_options(options):
    # Pacemaker does not care currently about meaningfulness for concrete
    # constraint, so we use all attribs.
    for name, value in options.items():
        if name not in ATTRIB:
            raise LibraryError(
                ReportItem.error(
                    reports.messages.InvalidOptions(
                        [name], sorted(ATTRIB.keys()), None
                    )
                )
            )
        if value not in ATTRIB[name]:
            raise LibraryError(
                ReportItem.error(
                    reports.messages.InvalidOptionValue(
                        name, value, ATTRIB[name]
                    )
                )
            )


def create(parent, resource_set):
    """
    parent - lxml element for append new resource_set
    """
    element = etree.SubElement(parent, "resource_set")
    element.attrib.update(resource_set["options"])
    element.attrib["id"] = find_unique_id(
        parent.getroottree(),
        "{0}_set".format(parent.attrib.get("id", "constraint_set")),
    )

    for _id in resource_set["ids"]:
        etree.SubElement(element, "resource_ref").attrib["id"] = _id

    return element


def get_resource_id_set_list(element):
    return [
        resource_ref_element.attrib["id"]
        for resource_ref_element in element.findall(".//resource_ref")
    ]


def export(element):
    return {
        "ids": get_resource_id_set_list(element),
        "options": export_attributes(element),
    }
