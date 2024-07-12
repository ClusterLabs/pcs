from collections import (
    Counter,
    OrderedDict,
)
from typing import (
    Iterable,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)

from lxml import etree
from lxml.etree import _Element

from pcs.common import reports
from pcs.common.pacemaker.tag import CibTagDto
from pcs.common.reports import (
    ReportItem,
    ReportItemList,
)
from pcs.common.types import (
    StringCollection,
    StringIterable,
    StringSequence,
)
from pcs.lib.cib.resource.common import find_resources
from pcs.lib.cib.tools import (
    ElementSearcher,
    IdProvider,
    get_configuration_elements_by_id,
)
from pcs.lib.pacemaker.values import validate_id
from pcs.lib.xml_tools import (
    find_parent,
    move_elements,
    remove_one_element,
)

from .const import (
    TAG_OBJREF,
    TAG_TAG,
)


def is_tag(element: _Element) -> bool:
    return element.tag == TAG_TAG


def _validate_tag_id(tag_id: str, id_provider: IdProvider) -> ReportItemList:
    """
    Validate that tag_id is a valid xml id and it is unique in the cib.

    tag_id -- identifier of new tag
    id_provider -- elements' ids generator
    """
    report_list: ReportItemList = []
    validate_id(tag_id, reporter=report_list)
    report_list.extend(id_provider.book_ids(tag_id))
    return report_list


def _validate_tag_id_not_in_idref_list(
    tag_id: str, idref_list: StringCollection
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
    idref_list: StringSequence,
    add_or_not_remove: bool = True,
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
                    sorted(duplicate_ids_list),
                    add_or_not_remove,
                )
            )
        ]
    return []


def _validate_tag_create_idref_list_not_empty(
    idref_list: StringIterable,
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
    resources_section: _Element,
    idref_list: StringSequence,
) -> ReportItemList:
    """
    Validate that ids are resources.

    resources_section -- element resources
    idref_list -- reference ids to validate
    """
    dummy_resources, report_list = find_resources(resources_section, idref_list)
    return report_list


def validate_create_tag(
    resources_section: _Element,
    tag_id: str,
    idref_list: StringSequence,
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
    constraint_section: _Element, to_remove_tag_list: StringIterable
) -> ReportItemList:
    """
    Validation function for tag removal. List of tag elements is not empty and
    no tag is referenced in any constraint.

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
                            [
                                str(elem.get("id", ""))
                                for elem in constraint_list
                            ]
                        ),
                    )
                )
            )
    return report_list


class ValidateTagUpdateByIds:
    # pylint:disable=too-many-instance-attributes
    """
    Validate update of a tag element by using ids.

    Class provides single validate method which returns a report item list,
    and methods for accessing required elements needed for update.

    Class is inspired by class ValidateMoveResourcesToGroupByIds from module
    'pcs/lib/cib/resource/hierarchy.py' which is used in command 'pcs resource
    group add'. It does validation based on given ids.  There is also class
    ValidateMoveResourcesToGroupByElements which implements validation based on
    given elements.
    Validation of tag update from existing elements is not implemented because
    it wasn't needed yet. If you need it, feel free to implement it. Take a look
    at the hierarchy module to see how it's done.
    """

    def __init__(
        self,
        tag_id: str,
        add_idref_list: StringSequence,
        remove_idref_list: StringSequence,
        adjacent_idref: Optional[str] = None,
    ) -> None:
        """
        tag_id -- id of an existing tag we want to update
        add_idref_list -- list of reference ids we want to add to the tag
        remove_idref_list -- list of reference ids we want to remove from the
            tag
        adjacent_idref -- id of an element next to which the added elements will
            be put
        """
        self._tag_id = tag_id
        self._add_idref_list = add_idref_list
        self._remove_idref_list = remove_idref_list
        self._adjacent_idref = adjacent_idref
        self._tag_element: Optional[_Element] = None
        self._add_obj_ref_element_list: List[_Element] = []
        self._adjacent_obj_ref_element: Optional[_Element] = None
        self._remove_obj_ref_element_list: List[_Element] = []

    def tag_element(self) -> Optional[_Element]:
        return self._tag_element

    def add_obj_ref_element_list(self) -> List[_Element]:
        return self._add_obj_ref_element_list

    def adjacent_obj_ref_element(self) -> Optional[_Element]:
        return self._adjacent_obj_ref_element

    def remove_obj_ref_element_list(self) -> List[_Element]:
        return self._remove_obj_ref_element_list

    def validate(
        self,
        resources_section: _Element,
        tags_section: _Element,
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

    def _validate_tag_exists(self, tags_section: _Element) -> ReportItemList:
        """
        Validate that tag with given tag_id exists and save the found element.

        tags_section -- tags section of a cib
        """
        tag_list, report_list = find_tag_elements_by_ids(
            tags_section,
            [self._tag_id],
        )
        if tag_list:
            self._tag_element = tag_list[0]
        return report_list

    def _validate_ids_for_update_are_specified(self) -> ReportItemList:
        """
        Validate that either of add or remove ids were specified or that add ids
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
        if self._tag_element is None or self._adjacent_idref is None:
            return report_list
        self._adjacent_obj_ref_element = self._find_obj_ref_in_tag(
            self._adjacent_idref,
        )
        if self._adjacent_obj_ref_element is None:
            report_list.append(
                ReportItem.error(
                    reports.messages.TagAdjacentReferenceIdNotInTheTag(
                        self._adjacent_idref,
                        self._tag_id,
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
        self,
        resources_section: _Element,
    ) -> ReportItemList:
        """
        Validate that ids can be added or moved:
        - there are no duplicate ids specified
        - ids belong to elements allowed to be put in a tag in case of adding
        - ids do not exist in the tag if no adjacent id was specified
        Save a list of created (for ids newly added to the tag) and found (for
        ids already existing in the tag) obj_ref elements keeping the order of
        given ids to add or move them in case of success validation.
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
                    resources_section,
                    unique_add_ids,
                )
            )
        if self._tag_element is not None and self._add_idref_list:
            existing_element_id_list = []
            for id_ref in unique_add_ids:
                obj_ref = self._find_obj_ref_in_tag(id_ref)
                if obj_ref is None:
                    obj_ref = etree.Element(TAG_OBJREF, id=id_ref)
                else:
                    existing_element_id_list.append(id_ref)
                self._add_obj_ref_element_list.append(obj_ref)
            # report if a reference id exists in tag and no adjacent reference
            # id was specified
            if self._adjacent_idref is None and existing_element_id_list:
                report_list.append(
                    ReportItem.error(
                        reports.messages.TagCannotAddReferenceIdsAlreadyInTheTag(
                            self._tag_id,
                            sorted(existing_element_id_list),
                        )
                    )
                )
        return report_list

    def _validate_ids_can_be_removed(self) -> ReportItemList:
        """
        Validate that ids can be removed:
        - there are no duplicate ids specified
        - ids exist in the tag
        - tag would not be left empty after removal
        Saves found elements to remove in case of a successful validation.
        """
        report_list: ReportItemList = []
        if self._tag_element is None or not self._remove_idref_list:
            return report_list
        report_list.extend(
            _validate_add_remove_duplicate_reference_ids(
                self._remove_idref_list,
                add_or_not_remove=False,
            ),
        )
        missing_id_list = []
        for id_ref in set(self._remove_idref_list):
            obj_ref = self._find_obj_ref_in_tag(id_ref)
            if obj_ref is not None:
                self._remove_obj_ref_element_list.append(obj_ref)
            else:
                missing_id_list.append(id_ref)
        if missing_id_list:
            report_list.append(
                ReportItem.error(
                    reports.messages.TagIdsNotInTheTag(
                        self._tag_id,
                        sorted(missing_id_list),
                    )
                )
            )
        if not report_list and not self._add_idref_list:
            remove_difference = set(
                self._tag_element.findall(TAG_OBJREF),
            ).difference(set(self._remove_obj_ref_element_list))
            if not remove_difference:
                report_list.append(
                    ReportItem.error(
                        reports.messages.TagCannotRemoveReferencesWithoutRemovingTag(
                            self._tag_id,
                        )
                    )
                )
        return report_list

    def _find_obj_ref_in_tag(self, obj_ref_id: str) -> Optional[_Element]:
        """
        Find obj_ref element in the tag element being updated.

        obj_ref_id -- reference id
        """
        if self._tag_element is None:
            return None
        xpath_result = cast(
            List[_Element],
            self._tag_element.xpath(
                f"./{TAG_OBJREF}[@id=$obj_ref_id]", obj_ref_id=obj_ref_id
            ),
        )
        return xpath_result[0] if xpath_result else None


def find_constraints_referencing_tag(
    constraints_section: _Element,
    tag_id: str,
) -> List[_Element]:
    """
    Find constraint elements which are referencing specified tag.

    constraints_section -- element constraints
    tag_id -- tag id
    """
    # TODO: replace by find_elements_referencing_id
    constraint_list = constraints_section.xpath(
        """
        ./rsc_colocation[
            not (descendant::resource_set)
            and
            (@rsc=$tag_id or @with-rsc=$tag_id)
        ]
        |
        ./rsc_location[
            not (descendant::resource_set)
            and
            @rsc=$tag_id
        ]
        |
        ./rsc_order[
            not (descendant::resource_set)
            and
            (@first=$tag_id or @then=$tag_id)
        ]
        |
        ./rsc_ticket[
            not (descendant::resource_set)
            and
            @rsc=$tag_id
        ]
        |
        (./rsc_colocation|./rsc_location|./rsc_order|./rsc_ticket)[
            ./resource_set/resource_ref[@id=$tag_id]
        ]
        """,
        tag_id=tag_id,
    )
    return cast(List[_Element], constraint_list)


def find_tag_elements_by_ids(
    tags_section: _Element,
    tag_id_list: StringIterable,
) -> Tuple[List[_Element], ReportItemList]:
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
    tags_section: _Element, tag_id: str, idref_list: StringIterable
) -> _Element:
    """
    Create new tag element and add it to cib.
    Returns newly created tag element.

    tags_section -- element tags
    tag_id -- identifier of new tag
    idref_list -- reference ids which we want to tag
    """
    tag_el = etree.SubElement(tags_section, TAG_TAG, id=tag_id)
    for ref_id in idref_list:
        etree.SubElement(tag_el, TAG_OBJREF, id=ref_id)
    return tag_el


def remove_tag(
    tag_elements: Iterable[_Element],
) -> None:
    """
    Remove given tag elements from a cib.

    tag_elements -- tag elements to be removed
    """
    for tag in tag_elements:
        remove_one_element(tag)


def remove_obj_ref(obj_ref_list: Iterable[_Element]) -> None:
    """
    Remove specified obj_ref elements and also their parents if they remain
    empty after obj_ref removal.

    obj_ref_list -- list of obj_ref elements
    """
    tag_elements = {
        element
        for element in {
            find_parent(obj_ref, [TAG_TAG]) for obj_ref in obj_ref_list
        }
        if element is not None
    }

    for obj_ref in obj_ref_list:
        remove_one_element(obj_ref)
    for tag in tag_elements:
        if len(tag.findall(TAG_OBJREF)) == 0:
            remove_one_element(tag)


def add_obj_ref(
    tag_element: _Element,
    obj_ref_el_list: Iterable[_Element],
    adjacent_element: Optional[_Element],
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


def get_list_of_tag_elements(tags_section: _Element) -> List[_Element]:
    """
    Get list of tag elements from cib.

    tags_section -- element tags
    """
    return tags_section.findall(TAG_TAG)


def tag_element_to_dict(
    tag_element: _Element,
) -> dict[str, Union[str, list[str]]]:
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
        "tag_id": str(tag_element.get("id", default="")),
        "idref_list": [
            str(obj_ref.get("id", default=""))
            for obj_ref in tag_element.findall(TAG_OBJREF)
        ],
    }


def tag_element_to_dto(tag_element: _Element) -> CibTagDto:
    return CibTagDto(
        str(tag_element.attrib["id"]),
        [
            str(obj_ref.attrib["id"])
            for obj_ref in tag_element.findall(TAG_OBJREF)
        ],
    )


def expand_tag(
    some_or_tag_el: _Element,
    only_expand_types: Optional[StringCollection] = None,
) -> List[_Element]:
    """
    Substitute a tag element with elements which the tag refers to.

    some_or_tag_el -- an already expanded element or a tag element to expand
    only_expand_types -- if specified, return only elements of these types
    """
    if some_or_tag_el.tag != TAG_TAG:
        return [some_or_tag_el]

    conf_section = find_parent(some_or_tag_el, {"configuration"})
    if conf_section is None:
        return []

    expanded_elements = []
    for element_id in [
        str(obj_ref.get("id", ""))
        for obj_ref in some_or_tag_el.iterfind(TAG_OBJREF)
    ]:
        if only_expand_types:
            searcher = ElementSearcher(
                only_expand_types, element_id, conf_section
            )
            if searcher.element_found():
                expanded_elements.append(searcher.get_element())
        else:
            expanded_elements.extend(
                get_configuration_elements_by_id(conf_section, element_id)
            )
    return expanded_elements
