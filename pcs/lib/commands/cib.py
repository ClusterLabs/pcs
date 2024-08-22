from typing import Collection

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.types import StringCollection
from pcs.lib.cib.remove_elements import (
    ElementsToRemove,
    ensure_resources_stopped,
    remove_specified_elements,
    stop_resources,
)
from pcs.lib.cib.resource.guest_node import is_guest_node
from pcs.lib.cib.resource.remote_node import (
    get_node_name_from_resource as get_node_name_from_remote_resource,
)
from pcs.lib.cib.tools import get_elements_by_ids
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError


def remove_elements(
    env: LibraryEnvironment,
    ids: StringCollection,
    force_flags: Collection[reports.types.ForceCode] = (),
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

    if report_processor.report_list(
        _validate_elements_to_remove(elements_to_remove)
    ).has_errors:
        raise LibraryError()

    if report_processor.report_list(
        _ensure_not_guest_remote(cib, ids)
    ).has_errors:
        raise LibraryError()

    report_processor.report_list(
        elements_to_remove.dependant_elements.to_reports()
    )
    report_processor.report_list(
        elements_to_remove.element_references.to_reports()
    )

    if env.is_cib_live and reports.codes.FORCE not in force_flags:
        cib = _stop_resources_wait(env, cib, elements_to_remove)

    remove_specified_elements(cib, elements_to_remove)
    env.push_cib()


def _stop_resources_wait(
    env: LibraryEnvironment, cib: _Element, elements_to_remove: ElementsToRemove
) -> _Element:
    """
    Stop all resources that are going to be removed. Push cib, wait for the
    cluster to settle down, and check if all resources were properly stopped.
    If not, report errors. Return cib with the applied changes.

    cib -- whole cib
    elements -- elements planned to be removed
    """
    resources_to_disable = elements_to_remove.resources_to_disable
    if not resources_to_disable:
        return cib
    env.report_processor.report(
        reports.ReportItem.info(
            reports.messages.StoppingResourcesBeforeDeleting(
                sorted(resources_to_disable)
            )
        )
    )

    if env.report_processor.report_list(
        stop_resources(cib, env.get_cluster_state(), elements_to_remove)
    ).has_errors:
        raise LibraryError()
    env.push_cib()

    env.wait_for_idle()
    if env.report_processor.report_list(
        ensure_resources_stopped(env.get_cluster_state(), elements_to_remove)
    ).has_errors:
        raise LibraryError()

    return env.get_cib()


def _validate_elements_to_remove(
    element_to_remove: ElementsToRemove,
) -> reports.ReportItemList:
    report_list = []
    for missing_id in sorted(element_to_remove.missing_ids):
        report_list.append(
            reports.ReportItem.error(
                reports.messages.IdNotFound(
                    missing_id, ["configuration element"]
                )
            )
        )

    unsupported_elements = element_to_remove.unsupported_elements
    for unsupported_id in sorted(unsupported_elements.id_tag_map):
        report_list.append(
            reports.ReportItem.error(
                reports.messages.IdBelongsToUnexpectedType(
                    unsupported_id,
                    list(unsupported_elements.supported_element_types),
                    unsupported_elements.id_tag_map[unsupported_id],
                )
            )
        )

    return report_list


def _ensure_not_guest_remote(
    cib: _Element, ids: StringCollection
) -> reports.ReportItemList:
    report_list = []
    elements_to_process, _ = get_elements_by_ids(cib, ids)
    for element in elements_to_process:
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
