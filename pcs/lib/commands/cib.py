from typing import Iterable

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.types import StringCollection
from pcs.lib.cib import description as cib_description
from pcs.lib.cib.remove_elements import (
    ElementsToRemove,
    ensure_resources_stopped,
    remove_specified_elements,
)
from pcs.lib.cib.resource.guest_node import is_guest_node
from pcs.lib.cib.resource.remote_node import (
    get_node_name_from_resource as get_node_name_from_remote_resource,
)
from pcs.lib.cib.resource.stonith import is_stonith
from pcs.lib.cib.tools import ElementNotFound, get_element_by_id, get_resources
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.sbd_stonith import ensure_some_stonith_remains


def remove_elements(
    env: LibraryEnvironment,
    ids: StringCollection,
    force_flags: reports.types.ForceFlags = (),
) -> None:
    """
    Remove elements with specified ids from CIB. This function is aware of
    relations and references between elements and will also remove all elements
    that are somehow referencing elements with specified ids.

    ids -- ids of configuration elements to remove
    force_flags -- list of flags codes
    """
    cib = env.get_cib()
    report_processor = env.report_processor

    elements_to_remove = ElementsToRemove(cib, ids)

    stonith_ids = []
    non_stonith_ids = []
    for res_el in elements_to_remove.resources_to_remove:
        if is_stonith(res_el):
            stonith_ids.append(str(res_el.attrib["id"]))
        else:
            non_stonith_ids.append(str(res_el.attrib["id"]))

    report_processor.report_list(
        _validate_elements_to_remove(elements_to_remove)
        + _ensure_not_guest_remote(elements_to_remove.resources_to_remove)
        + ensure_some_stonith_remains(
            env,
            get_resources(cib),
            stonith_resources_to_ignore=stonith_ids,
            sbd_being_disabled=False,
            force_flags=force_flags,
        )
    )

    # stonith resources do not need to be stopped, because they do not left
    # orphaned resources behind, so we check only the state of non-stonith
    # resources
    if non_stonith_ids:
        if env.is_cib_live:
            report_processor.report_list(
                ensure_resources_stopped(
                    env.get_cluster_state(), non_stonith_ids, force_flags
                )
            )
        else:
            report_processor.report(
                reports.ReportItem.warning(
                    reports.messages.StoppedResourcesBeforeDeleteCheckSkipped(
                        non_stonith_ids, reports.const.REASON_NOT_LIVE_CIB
                    )
                )
            )
    if report_processor.has_errors:
        raise LibraryError()

    report_processor.report_list(
        elements_to_remove.dependant_elements.to_reports()
    )
    report_processor.report_list(
        elements_to_remove.element_references.to_reports()
    )
    remove_specified_elements(cib, elements_to_remove)
    env.push_cib()


def set_description(
    env: LibraryEnvironment, element_id: str, description: str
) -> None:
    """
    Set, update, or delete the description of specified element.

    env -- LibraryEnvironment
    element_id -- id of the element
    description -- new description, if empty, delete existing description
    """
    try:
        element = get_element_by_id(env.get_cib(), element_id)
        env.report_processor.report_list(
            cib_description.validate_description_support(element)
        )
    except ElementNotFound:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.IdNotFound(
                    element_id,
                    sorted(cib_description.TAG_LIST_SUPPORTS_DESCRIPTION),
                )
            )
        )
    if env.report_processor.has_errors:
        raise LibraryError()

    cib_description.set_description(element, description)
    env.push_cib()


def get_description(env: LibraryEnvironment, element_id: str) -> str:
    """
    Get description of specified element.

    env -- LibraryEnvironment
    element_id -- id of the element
    """
    try:
        element = get_element_by_id(env.get_cib(), element_id)
        env.report_processor.report_list(
            cib_description.validate_description_support(element)
        )
    except ElementNotFound:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.IdNotFound(
                    element_id,
                    sorted(cib_description.TAG_LIST_SUPPORTS_DESCRIPTION),
                )
            )
        )
    if env.report_processor.has_errors:
        raise LibraryError()

    return cib_description.get_description(element)


def _validate_elements_to_remove(
    element_to_remove: ElementsToRemove,
) -> reports.ReportItemList:
    report_list = [
        reports.ReportItem.error(reports.messages.IdNotFound(missing_id, []))
        for missing_id in sorted(element_to_remove.missing_ids)
    ]
    unsupported_elements = element_to_remove.unsupported_elements
    report_list.extend(
        reports.ReportItem.error(
            reports.messages.IdBelongsToUnexpectedType(
                unsupported_id,
                list(unsupported_elements.supported_element_types),
                unsupported_elements.id_tag_map[unsupported_id],
            )
        )
        for unsupported_id in sorted(unsupported_elements.id_tag_map)
    )
    return report_list


def _ensure_not_guest_remote(
    resource_elements: Iterable[_Element],
) -> reports.ReportItemList:
    report_list = []
    for element in resource_elements:
        if is_guest_node(element):
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.UseCommandNodeRemoveGuest(
                        str(element.attrib["id"])
                    )
                )
            )
        if get_node_name_from_remote_resource(element) is not None:
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.UseCommandNodeRemoveRemote(
                        str(element.attrib["id"])
                    )
                )
            )
    return report_list
