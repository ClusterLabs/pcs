from typing import (
    Any,
    Callable,
    Dict,
    List,
    cast,
)

from lxml.etree import (
    SubElement,
    _Element,
)

from pcs.common import reports
from pcs.lib.cib import resource
from pcs.lib.cib.constraint import resource_set
from pcs.lib.cib.tools import (
    find_element_by_tag_and_id,
    find_unique_id,
)
from pcs.lib.errors import LibraryError
from pcs.lib.xml_tools import (
    export_attributes,
    find_parent,
    get_root,
)


def _validate_attrib_names(attrib_names, options):
    positional_arguments = ['rsc','rsc-role','ticket']
    options2 = options.copy()
    for arg in positional_arguments:
        if arg in options2:
            options2.pop(arg)

    invalid_names = [
        name for name in options2.keys() if name not in attrib_names
    ]
    if invalid_names:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.InvalidOptions(
                    sorted(invalid_names), sorted(attrib_names), None
                )
            )
        )


def find_valid_resource_id(
    report_processor: reports.ReportProcessor, cib, in_clone_allowed, _id
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
        str(clone.attrib["id"]),
    )
    if in_clone_allowed:
        if report_processor.report(
            reports.ReportItem.warning(report_msg)
        ).has_errors:
            raise LibraryError()
        return resource_element.attrib["id"]

    raise LibraryError(
        reports.ReportItem.error(
            report_msg,
            force_code=reports.codes.FORCE,
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


def export_with_set(element: _Element) -> Dict[str, Any]:
    return {
        "resource_sets": [
            resource_set.export(resource_set_item)
            for resource_set_item in element.findall(".//resource_set")
        ],
        "options": export_attributes(element),
    }


def export_plain(element: _Element) -> Dict[str, Any]:
    return {"options": export_attributes(element)}


def create_id(cib, type_prefix, resource_set_list):
    # Create a semi-random id. We need it to be predictable (for testing), short
    # and somehow different than other ids so that we don't spend much time in
    # find_unique_id.
    # Avoid using actual resource names. It makes the id very long (consider 10
    # or more resources in a set constraint). Also, if a resource is deleted
    # and therefore removed from the constraint, the id no longer matches the
    # constraint.
    resource_ids = []
    for _set in resource_set_list:
        resource_ids.extend(_set["ids"])
    id_part = "".join([_id[0] + _id[-1] for _id in resource_ids][:3])
    return find_unique_id(cib, "{0}_set_{1}".format(type_prefix, id_part))


def have_duplicate_resource_sets(element, other_element):
    def get_id_set_list(element):
        return [
            resource_set.get_resource_id_set_list(resource_set_item)
            for resource_set_item in element.findall(".//resource_set")
        ]

    return get_id_set_list(element) == get_id_set_list(other_element)


def check_is_without_duplication(
    report_processor: reports.ReportProcessor,
    constraint_section: _Element,
    element: _Element,
    are_duplicate: Callable[[_Element, _Element], bool],
    export_element: Callable[[_Element], Dict[str, Any]],
    duplication_allowed: bool = False,
) -> None:
    duplicate_element_list = [
        duplicate_element
        for duplicate_element in cast(
            # The xpath method has a complicated return value, but we know our
            # xpath expression returns only elements.
            List[_Element],
            constraint_section.xpath(
                ".//*[local-name()=$tag_name]", tag_name=element.tag
            ),
        )
        if (
            element is not duplicate_element
            and are_duplicate(element, duplicate_element)
        )
    ]
    if not duplicate_element_list:
        return

    if report_processor.report_list(
        [
            reports.ReportItem.info(
                reports.messages.DuplicateConstraintsList(
                    element.tag,
                    [
                        export_element(duplicate_element)
                        for duplicate_element in duplicate_element_list
                    ],
                )
            ),
            reports.ReportItem(
                severity=reports.item.get_severity(
                    reports.codes.FORCE,
                    duplication_allowed,
                ),
                message=reports.messages.DuplicateConstraintsExist(
                    [
                        str(duplicate.attrib["id"])
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
            reports.ReportItem.error(reports.messages.EmptyResourceSetList())
        )
    element = SubElement(constraint_section, tag_name)
    element.attrib.update(options)
    if tag_name == "rsc_order":
        all_resource_ids = []
        for resource_set_item in resource_set_list:
            all_resource_ids.extend(resource_set_item["ids"])
        resource_set.is_resource_in_same_group(
            get_root(constraint_section), all_resource_ids
        )
    for resource_set_item in resource_set_list:
        resource_set.create(element, resource_set_item)
    return element
