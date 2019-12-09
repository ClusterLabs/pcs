from collections import Counter
from typing import cast, Container, Dict, Iterable, Sequence
from xml.etree.ElementTree import Element

from lxml import etree
from lxml.etree import _Element

from pcs.common import reports
from pcs.common.reports import ReportItem, ReportItemList
from pcs.lib.cib.resource.common import find_resources_and_report
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
    Validation function for 'pcs tag create' command.

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

def validate_tag_ids_exist(
    tags_section: Element,
    tag_id_list: Iterable[str],
) -> ReportItemList:
    """
    Validate that given tag ids exist in cib.

    tags_section -- element tags
    tag_id_list -- list of tag indentifiers
    """
    report_list: ReportItemList = []
    for tag_id in tag_id_list:
        searcher = ElementSearcher(TAG_TAG, tag_id, tags_section)
        if not searcher.element_found():
            report_list.extend(searcher.get_errors())
    return report_list

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

def get_list_of_tags(
    tags_section: Element,
    tag_filter: Sequence[str],
) -> Iterable[Dict[str, Iterable[str]]]:
    """
    Returns list of tag structures optionally filtered.

    tags_section -- element tags
    tag_filter -- optional list of tags or empty list

    [
        {
            "tag_id": "tag1",
            "idref_list": ["i1", "i2"],
        },
        ...
    ]
    """
    return [
        {
            # NOTE: .get("id", default="") for typing  there always be an id
            "tag_id": tag.get("id", default=""),
            "idref_list": [obj_ref.get("id", default="") for obj_ref in tag],
        }
        for tag in tags_section
        if not tag_filter or tag.get("id", default="") in tag_filter
    ]
