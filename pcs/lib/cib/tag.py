from collections import Counter, defaultdict
from typing import (
    cast,
    Container,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)
from xml.etree.ElementTree import Element

from lxml import etree
from lxml.etree import _Element

from pcs.common import reports
from pcs.common.reports import ReportItem, ReportItemList
from pcs.lib.cib.resource.common import find_resources_and_report
from pcs.lib.cib.tools import ElementSearcher, IdProvider
from pcs.lib.pacemaker.values import validate_id
from pcs.lib.xml_tools import (
    append_elements,
    find_parent,
    move_elements,
    remove_elements,
    remove_one_element,
)

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
    tag_id: str, idref_list: Container[str],
) -> ReportItemList:
    """
    Validate that idref_list does not contain tag_id.

    tag_id -- identifier of new tag
    idref_list -- reference ids which we want to tag
    """
    if tag_id in idref_list:
        return [ReportItem.error(reports.messages.TagCannotContainItself())]
    return []


def _validate_add_remove_duplicate_reference_ids(
    idref_list: Iterable[str], add_or_not_remove: bool = True,
) -> ReportItemList:
    """
    Validate that idref_list does not contain duplicates.

    idref_list -- reference ids which we want to tag
    add_or_not_remove -- flag for add/remove action
    """
    duplicate_ids_list = [
        id for id, count in Counter(idref_list).items() if count > 1
    ]
    if duplicate_ids_list:
        return [
            ReportItem.error(
                reports.messages.TagAddRemoveIdsDuplication(
                    sorted(duplicate_ids_list), add_or_not_remove,
                )
            )
        ]
    return []


def _validate_tag_create_idref_list_not_empty(
    idref_list: Iterable[str],
) -> ReportItemList:
    """
    Validate that list of reference ids for tag create is not empty.

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
    return []


def _validate_reference_ids_are_resources(
    resources_section: Element, idref_list: Iterable[str],
) -> ReportItemList:
    """
    Validate that ids are resources.

    resources_section -- element resources
    idref_list -- reference ids to validate
    """
    report_list: ReportItemList = []
    find_resources_and_report(
        resources_section, idref_list, report_list,
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
        + _validate_tag_create_idref_list_not_empty(idref_list)
        + _validate_tag_id_not_in_idref_list(tag_id, idref_list)
        + _validate_reference_ids_are_resources(resources_section, idref_list)
        + _validate_add_remove_duplicate_reference_ids(idref_list)
    )


def validate_remove_tag(
    constraint_section: Element, to_remove_tag_list: Iterable[str],
) -> ReportItemList:
    """
    Validation function for tag removal. List of tag elements is not empty and
    tag is note referenced in constraint.

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
            constraint_section, tag_id,
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


def validate_add_remove_ids(
    resources_section: Element,
    tag_id: str,
    add_idref_list: Sequence[str],
    remove_idref_list: Sequence[str],
    adjacent_idref: Optional[str],
) -> ReportItemList:
    """
    Validate add/remove ids.

    resources_section --  element tags
    tag_id -- id of tagh we want to update
    add_idref_list -- reference ids to add
    remove_idref_list -- reference ids to remove
    adjacent_idref -- reference id where to add other ids
    """
    if not add_idref_list and (not remove_idref_list or adjacent_idref):
        return [
            ReportItem.error(
                reports.messages.TagCannotUpdateTagNoIdsSpecified()
            )
        ]
    report_list: ReportItemList = []
    report_list += _validate_tag_id_not_in_idref_list(tag_id, add_idref_list)
    report_list += _validate_reference_ids_are_resources(
        resources_section, add_idref_list,
    )
    report_list += _validate_add_remove_duplicate_reference_ids(add_idref_list)
    report_list += _validate_add_remove_duplicate_reference_ids(
        remove_idref_list, add_or_not_remove=False,
    )
    common_ids = set(add_idref_list) & set(remove_idref_list)
    if common_ids:
        report_list.append(
            ReportItem.error(
                reports.messages.TagCannotAddAndRemoveTheSameIdsAtOnce(
                    sorted(common_ids),
                )
            )
        )
    if adjacent_idref is not None:
        if adjacent_idref in add_idref_list:
            report_list.append(
                ReportItem.error(
                    reports.messages.TagCannotPutIdNextToItself(adjacent_idref)
                )
            )
        if adjacent_idref in remove_idref_list:
            report_list.append(
                ReportItem.error(
                    reports.messages.TagCannotRemoveAdjacentId(adjacent_idref)
                )
            )
    return report_list


def validate_add_obj_ref(
    element_list: List[Element], adjacent_el: Optional[Element], tag_id: str,
) -> ReportItemList:
    """
    Validation function for adding reference ids into the tag. If adjacent
    resource is not defined then reference ids being added cannot exist in the
    tag.

    add_list -- elements we want to add or move
    adjacent_el -- adjacent element where we want to put elements
    tag_id -- tag id for the report message
    """
    if adjacent_el is None and element_list:
        return [
            ReportItem.error(
                reports.messages.TagCannotAddReferenceIdsAlreadyInTheTag(
                    sorted([el.get("id", "") for el in element_list]), tag_id,
                )
            )
        ]
    return []


def validate_remove_obj_ref(obj_ref_list: Iterable[Element],) -> ReportItemList:
    """
    Validation function for obj_ref removal from a tag. Elements obj_ref can be
    removed without removing their parent tags.

    obj_ref_list -- list of obj_ref elements
    """
    report_list: ReportItemList = []
    parent2children: Dict[_Element, List[_Element]] = defaultdict(list)
    for _child in obj_ref_list:
        child = cast(_Element, _child)
        parent = child.getparent()
        if parent is not None:
            parent2children[parent].append(child)

    for parent, children in parent2children.items():
        if len(parent.findall(f"./{TAG_OBJREF}")) == len(children):
            report_list.append(
                ReportItem.error(
                    # pylint: disable=line-too-long
                    reports.messages.TagCannotRemoveReferencesWithoutRemovingTag()
                )
            )
    return report_list


def find_adjacent_obj_ref(
    tag_element: Element, adjacent_idref: Optional[str],
) -> Tuple[Optional[Element], ReportItemList]:
    """
    Find adjacent obj_ref element. If not found return None.

    tag_element -- tag element where we looking for adjacent obj_ref element
    adjacent_idref -- id of adjacent obj_ref element
    """
    report_list: ReportItemList = []
    adjacent_el = None
    if adjacent_idref is not None:
        el_list, _ = find_obj_ref_elements_in_tag(
            tag_element, [adjacent_idref],
        )
        if el_list:
            adjacent_el = el_list[0]
        else:
            report_list.append(
                ReportItem.error(
                    reports.messages.TagAdjacentReferenceIdNotInTheTag(
                        adjacent_idref, tag_element.get("id", ""),
                    )
                )
            )
    return adjacent_el, report_list


def find_obj_ref_elements_in_tag(
    tag: Element, idref_list: Iterable[str],
) -> Tuple[List[Element], ReportItemList]:
    element_list: List[Element] = []
    report_list: ReportItemList = []
    for idref in idref_list:
        searcher = ElementSearcher(TAG_OBJREF, idref, tag)
        if searcher.element_found():
            element_list.append(searcher.get_element())
        else:
            report_list.extend(searcher.get_errors())
    return element_list, report_list


def find_obj_ref_elements(
    tags_section: Element, idref_list: Iterable[str],
) -> List[Element]:
    """
    Find obj_ref elements which contain ids from specified list.
    If no obj_ref elements are found, then empty list is returned.

    tags_section -- element tags
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
    constraints_section: Element, tag_id: str,
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
        """.format(
            _id=tag_id
        )
    )
    return cast(Iterable[Element], constraint_list)


def find_tag_elements_by_ids(
    tags_section: Element, tag_id_list: Iterable[str],
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
    tags_section: Element, tag_id: str, idref_list: Iterable[str],
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


def create_obj_ref_elements(
    idref_list: Sequence[str], existing_el_list: Optional[List[Element]] = None,
) -> List[Element]:
    """
    Create list of obj_ref elements from list of reference ids. If element
    alaready exist, existing element is used instead of creating the new one.
    """
    if existing_el_list is None:
        existing_el_list = []
    id2element = {el.get("id", ""): el for el in existing_el_list}
    el_list = []
    for _id in idref_list:
        if _id in id2element:
            el_list.append(id2element[_id])
        else:
            el_list.append(cast(Element, etree.Element(TAG_OBJREF, id=_id)))
    return el_list


def remove_tag(tag_elements: Iterable[Element],) -> None:
    """
    Remove given tag elements from a cib.

    tag_elements -- list of tag elements for the removal
    """
    remove_elements(tag_elements)


def remove_obj_ref(obj_ref_list: Iterable[Element]) -> None:
    """
    Remove specified obj_ref elements and also their parents if they remain
    empty after obj_ref removal.

    obj_ref_list -- list of obj_ref elements
    """
    tag_elements = {find_parent(obj_ref, [TAG_TAG]) for obj_ref in obj_ref_list}
    remove_elements(obj_ref_list)
    for tag in tag_elements:
        if len(tag.findall(TAG_OBJREF)) == 0:
            remove_one_element(tag)


def add_obj_ref(
    tag_element: Element,
    obj_ref_el_list: Iterable[Element],
    adjacent_element: Optional[Element],
    put_after_adjacent: bool = False,
) -> None:
    """
    Add obj_ref elements to a tag element. Decide whether to move or append
    elements to the tag.

    tag_element -- tag element into which we wan to append obj_ref elements
    obj_ref_el_list -- elements we want to move or append to the tag
    adjacent_element -- element where we want to move or add obj_ref elements
    put_after_adjacent -- flag for direction were want to put elements
    """
    if adjacent_element is not None:
        move_elements(adjacent_element, obj_ref_el_list, put_after_adjacent)
    else:
        append_elements(tag_element, obj_ref_el_list)


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
