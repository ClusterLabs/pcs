from collections import Counter, defaultdict, OrderedDict
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
    find_parent,
    move_elements,
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


def _prepare_add_obj_ref_elements(
    idref_list: Sequence[str],
    existing_element_list: Optional[List[Element]] = None,
) -> List[Element]:
    """
    Prepare list of obj_ref elements for adding to a tag from a list of
    reference ids and list of existing elements. If element with a
    reference id does not exist, then new element is created. Resulting
    order of elements respects order of given reference ids.

    idref_list -- list of reference ids which must not contain duplicates
    existing_element_list -- existing obj_ref elements from a tag
    """
    if existing_element_list is None:
        existing_element_list = []
    final_element_list = []
    existing_id2element_dict = {
        element.get("id", ""): element for element in existing_element_list
    }
    for idref in idref_list:
        if idref in existing_id2element_dict:
            final_element_list.append(existing_id2element_dict[idref])
        else:
            final_element_list.append(
                cast(Element, etree.Element(TAG_OBJREF, id=idref)),
            )
    return final_element_list


class ValidateTagUpdateByIds:
    # pylint:disable=too-many-instance-attributes
    """
    Validate update of a tag element by using ids.

    Class provides single validate method, which returns a report item list,
    and methods for accessing to required elements needed for update.

    Class is inspired by class ValidateMoveResourcesToGroupByIds from module
    'pcs/lib/cib/resource/hierarchy.py' which is used in command 'pcs resource
    group add'. It does validation based on given ids.  There is also class
    ValidateMoveResourcesToGroupByElements which implements validation based on
    given elements.
    Validation of tag update from existing elements is not implemented because
    it wans't needed. Please look into hierarchy module in case you would need
    validation for tag update from existing elements.
    """

    def __init__(
        self,
        tag_id: str,
        add_idref_list: Sequence[str],
        remove_idref_list: Sequence[str],
        adjacent_idref: Optional[str] = None,
    ) -> None:
        """
        tag_id -- id of an existing tag we want to update
        add_idref_list -- list of reference ids we want to add to the tag
        remove_idref_list -- list of reference ids we want to remove from the
        tag
        adjacent_idref -- reference id from the tag where we want to add new ids
        """
        self._tag_id = tag_id
        self._add_idref_list = add_idref_list
        self._remove_idref_list = remove_idref_list
        self._adjacent_idref = adjacent_idref
        self._tag_element: Optional[Element] = None
        self._add_obj_ref_element_list: List[Element] = []
        self._adjacent_obj_ref_element: Optional[Element] = None
        self._remove_obj_ref_element_list: List[Element] = []

    def tag_element(self) -> Optional[Element]:
        return self._tag_element

    def add_obj_ref_element_list(self) -> List[Element]:
        return self._add_obj_ref_element_list

    def adjacent_obj_ref_element(self) -> Optional[Element]:
        return self._adjacent_obj_ref_element

    def remove_obj_ref_element_list(self) -> List[Element]:
        return self._remove_obj_ref_element_list

    def validate(
        self, resources_section: Element, tags_section: Element,
    ) -> ReportItemList:
        """
        Run the validation and return a report item list

        resources_section -- resources section of a cib
        tags_section -- tags section of a cib
        """
        return (
            self._validate_tag_exists(tags_section)
            + self._validate_ids_for_update_are_specified()
            + self._valdiate_no_common_add_remove_ids()
            + self._validate_ids_can_be_added_or_moved(resources_section)
            + self._validate_ids_can_be_removed()
            + self._validate_adjacent_id()
        )

    def _validate_tag_exists(self, tags_section: Element) -> ReportItemList:
        """
        Validate that tag with given tag_id exists and save founded element.

        tags_section -- tags section of a cib
        """
        tag_list, report_list = find_tag_elements_by_ids(
            tags_section, [self._tag_id],
        )
        if tag_list:
            self._tag_element = tag_list[0]
        return report_list

    def _validate_ids_for_update_are_specified(self) -> ReportItemList:
        """
        Validate that either of add or remove ids were specifiad or if add ids
        were specified in case of specified adjacent id.
        """
        report_list: ReportItemList = []
        if not self._add_idref_list and not self._remove_idref_list:
            report_list.append(
                ReportItem.error(
                    reports.messages.TagCannotUpdateTagNoIdsSpecified()
                )
            )
        if not self._add_idref_list and self._adjacent_idref is not None:
            report_list.append(
                ReportItem.error(
                    reports.messages.TagCannotSpecifyAdjacentIdWithoutIdsToAdd(
                        self._adjacent_idref,
                    )
                )
            )
        return report_list

    def _valdiate_no_common_add_remove_ids(self) -> ReportItemList:
        """
        Validate that we do not remove ids currently being added.
        """
        common_ids = set(self._add_idref_list) & set(self._remove_idref_list)
        if common_ids:
            return [
                ReportItem.error(
                    reports.messages.TagCannotAddAndRemoveIdsAtTheSameTime(
                        sorted(common_ids),
                    )
                )
            ]
        return []

    def _validate_adjacent_id(self) -> ReportItemList:
        """
        Validate that element with adjacent id exists and it is not currently
        being added or removed.
        """
        report_list: ReportItemList = []
        if self._tag_element is not None and self._adjacent_idref is not None:
            el_list, _ = find_obj_ref_elements(
                self._tag_element, [self._adjacent_idref],
            )
            if el_list:
                self._adjacent_obj_ref_element = el_list[0]
            else:
                report_list.append(
                    ReportItem.error(
                        reports.messages.TagAdjacentReferenceIdNotInTheTag(
                            self._adjacent_idref,
                            self._tag_element.get("id", ""),
                        )
                    )
                )
            if self._adjacent_obj_ref_element is not None:
                if self._adjacent_idref in self._add_idref_list:
                    report_list.append(
                        ReportItem.error(
                            reports.messages.TagCannotPutIdNextToItself(
                                self._adjacent_idref,
                            )
                        )
                    )
                if self._adjacent_idref in self._remove_idref_list:
                    report_list.append(
                        ReportItem.error(
                            reports.messages.TagCannotRemoveAdjacentId(
                                self._adjacent_idref,
                            )
                        )
                    )
        return report_list

    def _validate_ids_can_be_added_or_moved(
        self, resources_section: Element,
    ) -> ReportItemList:
        """
        Validates that ids can be added or moved:
        - there are no duplciate ids specified
        - ids belongs to the allowed elements in cas of adding (e.g. resources)
        - ids do not exist in tag if adjacent id was not specified
        - create ids if do not exist in tag and adjacend id was specified
        Save newly created and existing elements into a list respecting the
        order of given ids to add or move in case of success validation.
        """
        report_list: ReportItemList = []
        unique_add_ids = list(OrderedDict.fromkeys(self._add_idref_list))

        if self._add_idref_list:
            # report duplicate ids
            report_list.extend(
                _validate_add_remove_duplicate_reference_ids(
                    self._add_idref_list,
                )
            )
            # report if references not found or belongs to unexpected types
            report_list.extend(
                _validate_reference_ids_are_resources(
                    resources_section, unique_add_ids,
                )
            )
        if self._tag_element is not None and self._add_idref_list:
            existing_element_list, _ = find_obj_ref_elements(
                self._tag_element, unique_add_ids,
            )
            # report if a reference id exists in tag and adjacent reference id
            # was not specified
            if self._adjacent_idref is None and existing_element_list:
                report_list.append(
                    ReportItem.error(
                        # pylint: disable=line-too-long
                        reports.messages.TagCannotAddReferenceIdsAlreadyInTheTag(
                            self._tag_id,
                            sorted(
                                [
                                    el.get("id", "")
                                    for el in existing_element_list
                                ]
                            ),
                        )
                    )
                )
            if not report_list:
                self._add_obj_ref_element_list = _prepare_add_obj_ref_elements(
                    self._add_idref_list, existing_element_list,
                )
        return report_list

    def _validate_ids_can_be_removed(self) -> ReportItemList:
        """
        Validate that ids can be removed:
        - there are no duplciate ids specified
        - ids exist in the tag
        - tag would not be left empty after removal
        Saves found elements to remove in case of succes validation.
        """
        report_list: ReportItemList = []
        if self._tag_element is not None and self._remove_idref_list:
            report_list.extend(
                _validate_add_remove_duplicate_reference_ids(
                    self._remove_idref_list, add_or_not_remove=False,
                ),
            )

            element_list, tmp_report_list = find_obj_ref_elements(
                self._tag_element,
                list(OrderedDict.fromkeys(self._remove_idref_list)),
            )
            report_list.extend(tmp_report_list)

            if not report_list and not self._add_idref_list:
                report_list.extend(_validate_remove_obj_ref(element_list),)
            if not report_list:
                self._remove_obj_ref_element_list = element_list
        return report_list


def _validate_remove_obj_ref(
    obj_ref_list: Iterable[Element],
) -> ReportItemList:
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


def find_obj_ref_elements(
    context_element: Element, idref_list: Iterable[str],
) -> Tuple[List[Element], ReportItemList]:
    """
    Find obj_ref elements which contain ids from specified list.

    context_element -- element where we searching for obj_ref elements, usually
        element <tags> or <tag>
    idref_list -- id references list
    """
    obj_ref_el_list: List[Element] = []
    report_list: ReportItemList = []
    for idref in idref_list:
        xpath_result = cast(_Element, context_element).xpath(
            f'.//{TAG_OBJREF}[@id="{idref}"]',
        )
        if xpath_result:
            obj_ref_el_list.extend(cast(List[Element], xpath_result))
        else:
            report_list.append(
                ReportItem.error(
                    reports.messages.IdNotFound(
                        idref,
                        [TAG_OBJREF],
                        context_element.tag,
                        context_element.attrib.get("id", ""),
                    )
                )
            )
    return obj_ref_el_list, report_list


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


def remove_tag(tag_elements: Iterable[Element],) -> None:
    """
    Remove given tag elements from a cib.

    tag_elements -- tag elements to be removed
    """
    for tag in tag_elements:
        remove_one_element(tag)


def remove_obj_ref(obj_ref_list: Iterable[Element]) -> None:
    """
    Remove specified obj_ref elements and also their parents if they remain
    empty after obj_ref removal.

    obj_ref_list -- list of obj_ref elements
    """
    tag_elements = {find_parent(obj_ref, [TAG_TAG]) for obj_ref in obj_ref_list}
    for obj_ref in obj_ref_list:
        remove_one_element(obj_ref)
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
    Add or move obj_ref elements in given tag element.

    tag_element -- the tag element to be updated with obj_ref elements
    obj_ref_el_list -- elements to be added or moved in the updated tag
    adjacent_element -- the element next to which the obj_ref elements will be
        put
    put_after_adjacent -- put elements after (True) or before (False) the
        adjacent element
    """
    if adjacent_element is not None:
        move_elements(
            obj_ref_el_list,
            adjacent_element,
            put_after_adjacent=put_after_adjacent,
        )
    else:
        for obj_ref in obj_ref_el_list:
            tag_element.append(obj_ref)


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
