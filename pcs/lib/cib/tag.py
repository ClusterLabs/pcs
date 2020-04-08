from collections import Counter
from typing import (
    cast,
    Container,
    Dict,
    Iterable,
    List,
    Sequence,
    Tuple,
    Union,
)
from xml.etree.ElementTree import Element

from lxml import etree
from lxml.etree import _Element

from pcs.common import reports
from pcs.common.reports import ReportItem, ReportItemList
from pcs.lib.cib.resource.common import (
    find_resources_and_report,
)
from pcs.lib.cib.tools import ElementSearcher, IdProvider
from pcs.lib.pacemaker.values import validate_id

TAG_TAG = "tag"
TAG_OBJREF = "obj_ref"

def _validate_tag_id(tag_id: str, id_provider: IdProvider) -> ReportItemList:
    """
    Validate that tag_id is an valid xml id an it is uniqe in the cib.

    tag_id -- identifier of new tag
    id_provider -- elements' ids generator
    """
    report_list: ReportItemList = []
    validate_id(tag_id, reporter=report_list)
    report_list.extend(id_provider.book_ids(tag_id))
    return report_list

def _validate_tag_id_not_in_idref_list(
    tag_id: str,
    idref_list: Container[str],
) -> ReportItemList:
    """
    Validate that idref_list does not contain tag_id.

    tag_id -- identifier of new tag
    idref_list -- reference ids which we want to tag
    """
    if tag_id in idref_list:
        return [ReportItem.error(reports.messages.TagCannotContainItself())]
    return []

def _validate_duplicate_reference_ids(
    idref_list: Iterable[str],
) -> ReportItemList:
    """
    Validate that idref_list does not contain duplicates.

    idref_list -- reference ids which we want to tag
    """
    duplicate_ids_list = [
        id
        for id, count in Counter(idref_list).items()
        if count > 1
    ]
    if duplicate_ids_list:
        return [
            ReportItem.error(
                reports.messages.TagIdsDuplication(sorted(duplicate_ids_list))
            )
        ]
    return []

def _validate_reference_ids_are_resources(
    resources_section: Element,
    idref_list: Iterable[str],
) -> ReportItemList:
    """
    Validate that ids are resources.

    resources_section -- element resources
    idref_list -- reference ids to validate
    """
    # list for emptiness check (issue with some iterables like iterator)
    idref_list = list(idref_list)
    if not idref_list:
        return [
            ReportItem.error(
                reports.messages.TagCannotCreateEmptyTagNoIdsSpecified()
            )
        ]
    report_list: ReportItemList = []
    find_resources_and_report(
        resources_section,
        idref_list,
        report_list,
    )
    return report_list

def validate_create_tag(
    resources_section: Element,
    tag_id: str,
    idref_list: Sequence[str],
    id_provider: IdProvider,
) -> ReportItemList:
    """
    Validation function for tag creation.

    resources_section -- element resources
    tag_id -- identifier of new tag
    idref_list -- reference ids which we want to tag

    NOTE: Sequence vs. Collection issue:
            Value 'Collection' is unsubscriptable
            https://github.com/PyCQA/pylint/issues/2377
    """
    return (
        _validate_tag_id(tag_id, id_provider)
        +
        _validate_tag_id_not_in_idref_list(tag_id, idref_list)
        +
        _validate_reference_ids_are_resources(resources_section, idref_list)
        +
        _validate_duplicate_reference_ids(idref_list)
    )

def validate_remove_tag(
    constraint_section: Element,
    to_remove_tag_list: Iterable[str],
) -> ReportItemList:
    """
    Validation function for tag removal.

    constraint_section -- element constraints
    to_remove_tag_list -- list of tag ids for removal
    """
    # list for emptiness check (issue with some iterables like iterator)
    to_remove_tag_list = list(to_remove_tag_list)
    if not to_remove_tag_list:
        return [
            ReportItem.error(
                reports.messages.TagCannotRemoveTagsNoTagsSpecified()
            )
        ]
    report_list = []
    for tag_id in to_remove_tag_list:
        constraint_list = find_constraints_referencing_tag(
            constraint_section,
            tag_id,
        )
        if constraint_list:
            report_list.append(
                ReportItem.error(
                    reports.messages.TagCannotRemoveTagReferencedInConstraints(
                        tag_id,
                        sorted(
                            [elem.get("id", "") for elem in constraint_list]
                        ),
                    )
                )
            )
    return report_list

def find_obj_ref_elements(
    tags_section: Element,
    idref_list: Iterable[str],
) -> List[Element]:
    """
    Find obj_ref elements which contain ids from specified list.
    If no obj_ref elements are found, then empty list is returned.

    idref_list -- list with id references
    """
    element_list: List[Element] = []
    for idref in idref_list:
        obj_ref_list = cast(_Element, tags_section).xpath(
            f'.//{TAG_OBJREF}[@id="{idref}"]'
        )
        if obj_ref_list:
            element_list.extend(cast(List[Element], obj_ref_list))
    return element_list

def find_constraints_referencing_tag(
    constraints_section: Element,
    tag_id: str,
) -> Iterable[Element]:
    """
    Find constraint elements which are referencing specified tag.

    constraints_section -- element constraints
    tag_id -- tag id
    """
    constraint_list = cast(_Element, constraints_section).xpath(
        """
        ./rsc_colocation[
            not (descendant::resource_set)
            and
            (@rsc="{_id}" or @with-rsc="{_id}")
        ]
        |
        ./rsc_location[
            not (descendant::resource_set)
            and
            @rsc="{_id}"
        ]
        |
        ./rsc_order[
            not (descendant::resource_set)
            and
            (@first="{_id}" or @then="{_id}")
        ]
        |
        ./rsc_ticket[
            not (descendant::resource_set)
            and
            @rsc="{_id}"
        ]
        |
        (./rsc_colocation|./rsc_location|./rsc_order|./rsc_ticket)[
            ./resource_set/resource_ref[@id="{_id}"]
        ]
        """.format(_id=tag_id)
    )
    return cast(Iterable[Element], constraint_list)

def find_tag_elements_by_ids(
    tags_section: Element,
    tag_id_list: Iterable[str],
) -> Tuple[List[Element], ReportItemList]:
    """
    Try to find tag elements by ids and return them with non-empty report
    list in case of errors.

    tags_section -- element tags
    tag_id_list -- list of tag indentifiers
    """
    element_list = []
    report_list: ReportItemList = []
    for tag_id in tag_id_list:
        searcher = ElementSearcher(TAG_TAG, tag_id, tags_section)
        if searcher.element_found():
            element_list.append(searcher.get_element())
        else:
            report_list.extend(searcher.get_errors())

    return element_list, report_list

def create_tag(
    tags_section: Element,
    tag_id: str,
    idref_list: Iterable[str],
) -> Element:
    """
    Create new tag element and add it to cib.
    Returns newly created tag element.

    tags_section -- element tags
    tag_id -- identifier of new tag
    idref_list -- reference ids which we want to tag
    """
    tag_el = etree.SubElement(cast(_Element, tags_section), TAG_TAG, id=tag_id)
    for ref_id in idref_list:
        etree.SubElement(tag_el, TAG_OBJREF, id=ref_id)
    return cast(Element, tag_el)

def remove_tag(
    tag_elements: Iterable[Element],
) -> None:
    """
    Remove given tag elements from a cib.

    tag_elements -- list of tag elements for the removal
    """
    for _element in tag_elements:
        element = cast(_Element, _element)
        parent = element.getparent()
        if parent is not None:
            parent.remove(element)

def get_list_of_tag_elements(tags_section: Element) -> List[Element]:
    """
    Get list of tag elements from cib.

    tags_section -- element tags
    """
    return tags_section.findall("tag")

def tag_element_to_dict(
    tag_element: Element,
) -> Dict[str, Union[str, Iterable[str]]]:
    """
    Convert tag element to the dict structure

    tag_element -- single tag element that contains obj_ref elements

    {
        "tag_id": "tag1",
        "idref_list": ["i1", "i2"],
    },
    """
    return {
        # NOTE: .get("id", default="") for typing  there always be an id
        "tag_id": tag_element.get("id", default=""),
        "idref_list": [
            obj_ref.get("id", default="")
            for obj_ref in tag_element.findall("obj_ref")
        ],
    }
