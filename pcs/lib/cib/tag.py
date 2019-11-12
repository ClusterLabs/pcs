from collections import Counter
from typing import cast, Container, Iterable, Sequence
from xml.etree.ElementTree import Element

from lxml import etree
from lxml.etree import _Element

from pcs.common import reports
from pcs.common.reports import ReportItem, ReportItemList
from pcs.lib.cib.tools import IdProvider
from pcs.lib.pacemaker.values import validate_id
from pcs.lib.xml_tools import get_root

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

def _validate_reference_ids_exist(
        idref_list: Iterable[str],
        tags_section: Element,
) -> ReportItemList:
    """
    Validate that all reference ids exist in cib.

    cib_tags_section -- section of cib
    idref_list -- reference ids which we want to tag
    """
    tree = get_root(tags_section)
    report_list = []
    for idref in idref_list:
        element = tree.find(f'./configuration//*[@id="{idref}"]')
        if element is None:
            report_list.append(
                ReportItem.error(reports.messages.IdNotFound(idref, []))
            )
    return report_list

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

def validate_create_tag(
        tag_id: str,
        idref_list: Sequence[str],
        tags_section: Element,
        id_provider: IdProvider,
) -> ReportItemList:
    """
    Validation function for 'pcs tag create' command.

    tag_id -- identifier of new tag
    idref_list -- reference ids which we want to tag
    tags_section -- element tags

    NOTE: Sequence vs. Collection issue:
            Value 'Collection' is unsubscriptable
            https://github.com/PyCQA/pylint/issues/2377
    """
    return (
        _validate_tag_id(tag_id, id_provider)
        +
        _validate_tag_id_not_in_idref_list(tag_id, idref_list)
        +
        _validate_reference_ids_exist(idref_list, tags_section)
        +
        _validate_duplicate_reference_ids(idref_list)
    )

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
