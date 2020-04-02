from lxml import etree

from pcs.common import reports
from pcs.common.reports import ReportProcessor
from pcs.common.reports.item import ReportItem
from pcs.lib.cib import resource
from pcs.lib.cib.constraint import resource_set
from pcs.lib.cib.tools import (
    find_unique_id,
    find_element_by_tag_and_id,
)
from pcs.lib.errors import LibraryError
from pcs.lib.xml_tools import (
    export_attributes,
    find_parent,
)


def _validate_attrib_names(attrib_names, options):
    invalid_names = [
        name for name in options.keys() if name not in attrib_names
    ]
    if invalid_names:
        raise LibraryError(
            ReportItem.error(
                reports.messages.InvalidOptions(
                    sorted(invalid_names), sorted(attrib_names), None
                )
            )
        )


def find_valid_resource_id(
    report_processor: ReportProcessor, cib, in_clone_allowed, _id
):
    parent_tags = resource.clone.ALL_TAGS + [resource.bundle.TAG]
    resource_element = find_element_by_tag_and_id(
        sorted(parent_tags + [resource.primitive.TAG, resource.group.TAG]),
        cib,
        _id,
    )

    if resource_element.tag in parent_tags:
        return resource_element.attrib["id"]

    clone = find_parent(resource_element, parent_tags)
    if clone is None:
        return resource_element.attrib["id"]

    report_msg = reports.messages.ResourceForConstraintIsMultiinstance(
        resource_element.attrib["id"],
        "clone" if clone.tag == "master" else clone.tag,
        clone.attrib["id"],
    )
    if in_clone_allowed:
        if report_processor.report(ReportItem.warning(report_msg)).has_errors:
            raise LibraryError()
        return resource_element.attrib["id"]

    raise LibraryError(
        ReportItem.error(
            report_msg,
            # repair to clone is workaround for web ui, so we put only
            # information about one forceable possibility
            force_code=reports.codes.FORCE_CONSTRAINT_MULTIINSTANCE_RESOURCE,
        )
    )


def prepare_options(attrib_names, options, create_id_fn, validate_id):
    _validate_attrib_names(attrib_names + ("id",), options)
    options = options.copy()

    if "id" not in options:
        options["id"] = create_id_fn()
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
    _id = (
        "pcs_"
        + type_prefix
        + "".join(
            [
                "_set_" + "_".join(id_set)
                for id_set in resource_set.extract_id_set_list(
                    resource_set_list
                )
            ]
        )
    )
    return find_unique_id(cib, _id)


def have_duplicate_resource_sets(element, other_element):
    get_id_set_list = lambda element: [
        resource_set.get_resource_id_set_list(resource_set_item)
        for resource_set_item in element.findall(".//resource_set")
    ]
    return get_id_set_list(element) == get_id_set_list(other_element)


def check_is_without_duplication(
    report_processor: ReportProcessor,
    constraint_section,
    element,
    are_duplicate,
    export_element,
    duplication_alowed=False,
):
    duplicate_element_list = [
        duplicate_element
        for duplicate_element in constraint_section.findall(".//" + element.tag)
        if (
            element is not duplicate_element
            and are_duplicate(element, duplicate_element)
        )
    ]
    if not duplicate_element_list:
        return

    if report_processor.report_list(
        [
            ReportItem.info(
                reports.messages.DuplicateConstraintsList(
                    element.tag,
                    [
                        export_element(duplicate_element)
                        for duplicate_element in duplicate_element_list
                    ],
                )
            ),
            ReportItem(
                severity=reports.item.get_severity(
                    reports.codes.FORCE_CONSTRAINT_DUPLICATE,
                    duplication_alowed,
                ),
                message=reports.messages.DuplicateConstraintsExist(
                    [
                        duplicate.get("id")
                        for duplicate in duplicate_element_list
                    ]
                ),
            ),
        ]
    ).has_errors:
        raise LibraryError()


def create_with_set(constraint_section, tag_name, options, resource_set_list):
    if not resource_set_list:
        raise LibraryError(
            ReportItem.error(reports.messages.EmptyResourceSetList())
        )
    element = etree.SubElement(constraint_section, tag_name)
    element.attrib.update(options)
    for resource_set_item in resource_set_list:
        resource_set.create(element, resource_set_item)
    return element
