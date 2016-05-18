from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib import reports
from pcs.lib.cib.tools import (
    find_unique_id,
    export_attributes,
)
from pcs.lib.errors import LibraryError

ATTRIB = {
    "sequential": ("true", "false"),
    "require-all":("true", "false"),
    "action" : ("start", "promote", "demote", "stop"),
    "role" : ("Stopped", "Started", "Master", "Slave"),
}

def prepare_set(find_valid_id, resource_set):
    """return resource_set with corrected ids"""
    validate_options(resource_set["options"])
    return {
        "ids": [find_valid_id(id) for id in resource_set["ids"]],
        "options": resource_set["options"]
    }

def validate_options(options):
    #Pacemaker does not care currently about meaningfulness for concrete
    #constraint, so we use all attribs.
    for name, value in options.items():
        if name not in ATTRIB:
            raise LibraryError(
                reports.invalid_option(name, list(ATTRIB.keys()), None)
            )
        if value not in ATTRIB[name]:
            raise LibraryError(
                reports.invalid_option_value(name, value, ATTRIB[name])
            )

def extract_id_set_list(resource_set_list):
    return [resource_set["ids"] for resource_set in resource_set_list]

def create(parent, resource_set):
    """
    parent - lxml element for append new resource_set
    """
    element = etree.SubElement(parent, "resource_set")
    element.attrib.update(resource_set["options"])
    element.attrib["id"] = find_unique_id(
        parent.getroottree(),
        "pcs_rsc_set_{0}".format("_".join(resource_set["ids"]))
    )

    for id in resource_set["ids"]:
        etree.SubElement(element, "resource_ref").attrib["id"] = id

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
