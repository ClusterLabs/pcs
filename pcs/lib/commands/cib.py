from typing import (
    Collection,
    Iterable,
    Sequence,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.types import (
    StringCollection,
    StringSequence,
)
from pcs.lib.cib.remove_elements import (
    ElementsToRemove,
    ensure_resources_stopped,
    remove_specified_elements,
    stop_resources,
    warn_resource_unmanaged,
)
from pcs.lib.cib.resource.guest_node import (
    get_node_name_from_resource as get_node_name_from_guest_resource,
)
from pcs.lib.cib.resource.guest_node import is_guest_node
from pcs.lib.cib.resource.remote_node import (
    get_node_name_from_resource as get_node_name_from_remote_resource,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.live import remove_node


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
    remote_node_names = _get_remote_node_names(
        elements_to_remove.resources_to_disable
    )
    guest_node_names = _get_guest_node_names(
        elements_to_remove.resources_to_disable
    )

    if remote_node_names:
        report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.UseCommandNodeRemoveRemote()
            )
        )
    if guest_node_names:
        report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.UseCommandNodeRemoveGuest()
            )
        )

    if report_processor.report_list(
        _validate_elements_to_remove(elements_to_remove)
        + _warn_remote_guest(remote_node_names, guest_node_names)
    ).has_errors:
        raise LibraryError()

    report_processor.report_list(
        elements_to_remove.dependant_elements.to_reports()
    )
    report_processor.report_list(
        elements_to_remove.element_references.to_reports()
    )

    if env.is_cib_live and reports.codes.FORCE not in force_flags:
        cib = _stop_resources_wait(
            env, cib, elements_to_remove.resources_to_disable
        )

    remove_specified_elements(cib, elements_to_remove)
    env.push_cib()

    if env.is_cib_live:
        for node_name in remote_node_names + guest_node_names:
            remove_node(env.cmd_runner(), node_name)


def _stop_resources_wait(
    env: LibraryEnvironment,
    cib: _Element,
    resource_elements: Sequence[_Element],
) -> _Element:
    """
    Stop all resources that are going to be removed. Push cib, wait for the
    cluster to settle down, and check if all resources were properly stopped.
    If not, report errors. Return cib with the applied changes.

    cib -- whole cib
    resource_elements -- resources that should be stopped
    """
    if not resource_elements:
        return cib

    resource_ids = [str(el.attrib["id"]) for el in resource_elements]

    env.report_processor.report(
        reports.ReportItem.info(
            reports.messages.StoppingResourcesBeforeDeleting(resource_ids)
        )
    )

    if env.report_processor.report_list(
        warn_resource_unmanaged(env.get_cluster_state(), resource_ids)
    ).has_errors:
        raise LibraryError()
    stop_resources(cib, resource_elements)
    env.push_cib()

    env.wait_for_idle()
    if env.report_processor.report_list(
        ensure_resources_stopped(env.get_cluster_state(), resource_ids)
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
                reports.messages.IdNotFound(missing_id, [])
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


def _warn_remote_guest(
    remote_node_names: StringSequence, guest_node_names: StringSequence
) -> reports.ReportItemList:
    return [
        reports.ReportItem.warning(
            reports.messages.RemoteNodeRemovalIncomplete(node_name)
        )
        for node_name in remote_node_names
    ] + [
        reports.ReportItem.warning(
            reports.messages.GuestNodeRemovalIncomplete(node_name)
        )
        for node_name in guest_node_names
    ]


def _get_remote_node_names(resource_elements: Iterable[_Element]) -> list[str]:
    return [
        get_node_name_from_remote_resource(el)
        for el in resource_elements
        if get_node_name_from_remote_resource(el) is not None
    ]


def _get_guest_node_names(resource_elements: Iterable[_Element]) -> list[str]:
    return [
        get_node_name_from_guest_resource(el)
        for el in resource_elements
        if is_guest_node(el)
    ]
