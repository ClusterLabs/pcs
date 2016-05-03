from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial

from lxml import etree

from pcs.lib import reports
from pcs.lib.cib import resource
from pcs.lib.cib.constraint import resource_set
from pcs.lib.cib.tools import export_attributes, find_unique_id, find_parent
from pcs.lib.errors import LibraryError


def _validate_attrib_names(attrib_names, options):
    for option_name in options.keys():
        if option_name not in attrib_names:
            raise LibraryError(reports.invalid_option(
                attrib_names, option_name
            ))

def find_valid_resource_id(cib, can_repair_to_clone, in_clone_allowed, id):
    resource_element = resource.find_by_id(cib, id)

    if(resource_element is None):
        raise LibraryError(reports.resource_does_not_exist(id))

    if resource_element.tag in resource.TAGS_CLONE:
        return resource_element.attrib["id"]

    clone = find_parent(resource_element, resource.TAGS_CLONE)
    if clone is None:
        return resource_element.attrib["id"]

    if can_repair_to_clone:
        return clone.attrib["id"]

    if in_clone_allowed:
        return resource_element.attrib["id"]

    raise LibraryError(reports.resource_for_constraint_is_multiinstance(
        resource_element.attrib["id"], clone.tag, clone.attrib["id"]
    ))

def prepare_resource_set_list(
    cib, can_repair_to_clone, in_clone_allowed, resource_set_list
):
    """return resource_set_list with corrected ids"""
    find_valid_id = partial(
        find_valid_resource_id,
        cib, can_repair_to_clone, in_clone_allowed
    )
    return [
         resource_set.prepare_set(find_valid_id, resource_set_item)
         for resource_set_item in resource_set_list
    ]

def prepare_options(attrib_names, options, create_id, validate_id):
    _validate_attrib_names(attrib_names+("id",), options)
    options = options.copy()

    if "id" not in options:
        options["id"] = create_id()
    else:
        validate_id(options["id"])
    return options

def export_with_set(element):
    return {
        "resource_sets": [
            resource_set.export(resource_set_item)
            for resource_set_item in element.findall(".//resource_set")
        ],
        "options": export_attributes(element),
    }

def export_plain(element):
    return {"options": export_attributes(element)}

def create_id(cib, type_prefix, resource_set_list):
    id = "pcs_" +type_prefix +"".join([
        "_set_"+"_".join(id_set)
        for id_set in resource_set.extract_id_set_list(resource_set_list)
    ])
    return find_unique_id(cib, id)

def have_duplicate_resource_sets(element, other_element):
    get_id_set_list = lambda element: [
        resource_set.get_resource_id_set_list(resource_set_item)
        for resource_set_item in element.findall(".//resource_set")
    ]
    return get_id_set_list(element) == get_id_set_list(other_element)

def check_is_without_duplication(
    constraint_section, element, are_duplicate, export_element

):
    duplicate_element_list = [
        duplicate_element
        for duplicate_element in constraint_section.findall(".//"+element.tag)
        if(
            element is not duplicate_element
            and
            are_duplicate(element, duplicate_element)
        )
    ]

    if duplicate_element_list:
        raise LibraryError(reports.duplicate_constraints_exist(
            element.tag, [
                export_element(duplicate_element)
                for duplicate_element in duplicate_element_list
            ]
        ))

def create_with_set(constraint_section, tag_name, options, resource_set_list):
    if not resource_set_list:
        raise LibraryError(reports.empty_resource_set_list())
    element = etree.SubElement(constraint_section, tag_name)
    element.attrib.update(options)
    for resource_set_item in resource_set_list:
        resource_set.create(element, resource_set_item)
    return element
