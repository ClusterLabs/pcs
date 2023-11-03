from typing import (
    Collection,
    Iterable,
)

from lxml import etree
from lxml.etree import _Element

from pcs.common import reports
from pcs.common.types import StringSequence
from pcs.lib.cib.const import TAG_OBJREF
from pcs.lib.cib.constraint.all import is_constraint
from pcs.lib.cib.constraint.location import (
    is_location_constraint,
    is_location_rule,
)
from pcs.lib.cib.constraint.resource_set import is_set_constraint
from pcs.lib.cib.resource.bundle import is_bundle
from pcs.lib.cib.resource.clone import is_any_clone
from pcs.lib.cib.resource.common import get_inner_resources
from pcs.lib.cib.resource.group import is_group
from pcs.lib.cib.tag import is_tag
from pcs.lib.cib.tools import (
    find_elements_referencing_id,
    get_elements_by_ids,
    remove_element_by_id,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.live import parse_cib_xml


def remove_elements(
    env: LibraryEnvironment,
    ids: StringSequence,
    force_flags: Collection[reports.types.ForceCode] = (),
) -> None:
    """
    Remove elements with specified ids from CIB. This function is aware of
    relations and references between elements and will also remove all elements
    that are somehow referencing elements with specified ids.

    ids -- ids of configuration elements to remove
    force_flags -- list of flags codes
    """
    del force_flags
    id_set = set(ids)
    cib = env.get_cib()
    wip_cib = parse_cib_xml(etree.tostring(cib).decode())
    report_processor = env.report_processor

    elements_to_process, not_found_ids = get_elements_by_ids(wip_cib, id_set)

    for non_existing_id in not_found_ids:
        report_processor.report(
            reports.ReportItem.error(
                reports.messages.IdNotFound(
                    non_existing_id, ["configuration element"]
                )
            )
        )

    for element in elements_to_process:
        if not (is_constraint(element) or is_location_rule(element)):
            report_processor.report(
                reports.ReportItem.error(
                    reports.messages.IdBelongsToUnexpectedType(
                        str(element.get("id")),
                        ["constraint", "location rule"],
                        element.tag,
                    )
                )
            )

    if report_processor.has_errors:
        raise LibraryError()

    element_ids_to_remove = _get_dependencies_to_remove(elements_to_process)
    dependant_elements, _ = get_elements_by_ids(
        cib, element_ids_to_remove - id_set
    )
    if dependant_elements:
        report_processor.report(
            reports.ReportItem.info(
                reports.messages.CibRemoveDependantElements(
                    {
                        str(element.attrib["id"]): element.tag
                        for element in dependant_elements
                    }
                )
            )
        )

    for element_id in element_ids_to_remove:
        remove_element_by_id(cib, element_id)

    env.push_cib()


def _get_dependencies_to_remove(elements: list[_Element]) -> set[str]:
    """
    Get ids of all elements that need to be removed (including specified
    elements) together with specified elements based on their relations.

    WARNING: this is a destructive operation for elements and their etree.

    elements -- list of elements that are planned to be removed
    """
    elements_to_process = list(elements)
    element_ids_to_remove: set[str] = set()

    while elements_to_process:
        el = elements_to_process.pop(0)
        element_id = str(el.attrib["id"])
        if el.tag not in ("obj_ref", "resource_ref", "role"):
            if element_id in element_ids_to_remove:
                continue
            element_ids_to_remove.add(element_id)
            elements_to_process.extend(_get_element_references(el))
            elements_to_process.extend(_get_inner_references(el))
        parent_el = el.getparent()
        if parent_el is not None:
            if _is_empty_after_inner_el_removal(parent_el):
                elements_to_process.append(parent_el)
            parent_el.remove(el)

    return element_ids_to_remove


def _get_element_references(element: _Element) -> Iterable[_Element]:
    """
    Return all CIB elements that are referencing specified element

    element -- references to this element will be
    """
    return find_elements_referencing_id(element, str(element.attrib["id"]))


def _get_inner_references(element: _Element) -> Iterable[_Element]:
    """
    Get all inner elements with attribute id, which means that they might be
    refernenced in IDREF. Elements with attribute id and type IDREF are also
    returned.

    Note:
        Only removing of constraint or location rule elements is supported.
        Theirs inner elements cannot be referenced or referencing is not
        supported.
    """
    # pylint: disable=unused-argument
    # return cast(Iterable[_Element], element.xpath("./*[@id]"))
    # if is_resource(element):
    #     return get_inner_resources(element)
    # if element.tag == "alert":
    #     return element.findall("recipient")
    # if is_set_constraint(element):
    #     return element.findall("resource_set")
    # if element.tag == "acl_role":
    #     return element.findall("acl_permission")
    return []


def _is_last_element(parent_element: _Element, child_tag: str) -> bool:
    return len(parent_element.findall(f"./{child_tag}")) == 1


def _is_empty_after_inner_el_removal(parent_el: _Element) -> bool:
    # pylint: disable=too-many-return-statements
    if is_bundle(parent_el) or is_any_clone(parent_el):
        return True
    if is_group(parent_el):
        return len(get_inner_resources(parent_el)) == 1
    if is_tag(parent_el):
        return _is_last_element(parent_el, TAG_OBJREF)
    if parent_el.tag == "resource_set":
        return _is_last_element(parent_el, "resource_ref")
    if is_set_constraint(parent_el):
        return _is_last_element(parent_el, "resource_set")
    if is_location_constraint(parent_el):
        return _is_last_element(parent_el, "rule")
    return False
