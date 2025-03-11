from typing import (
    Iterable,
    Sequence,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.types import StringCollection
from pcs.lib.cib.remove_elements import (
    ElementsToRemove,
    ensure_resources_stopped,
    remove_specified_elements,
    stop_resources,
    warn_resource_unmanaged,
)
from pcs.lib.cib.resource.guest_node import is_guest_node
from pcs.lib.cib.resource.remote_node import (
    get_node_name_from_resource as get_node_name_from_remote_resource,
)
from pcs.lib.cib.resource.stonith import (
    get_all_node_isolating_resources,
    is_stonith,
)
from pcs.lib.cib.tools import get_resources
from pcs.lib.communication.sbd import GetSbdStatus
from pcs.lib.communication.tools import run as run_communication
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.node import get_existing_nodes_names


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

    if report_processor.report_list(
        _validate_elements_to_remove(elements_to_remove)
        + _ensure_not_guest_remote(elements_to_remove.resources_to_remove)
        + _ensure_some_stonith_remains(
            env, get_resources(cib), elements_to_remove, force_flags
        )
    ).has_errors:
        raise LibraryError()

    report_processor.report_list(
        elements_to_remove.dependant_elements.to_reports()
    )
    report_processor.report_list(
        elements_to_remove.element_references.to_reports()
    )

    cib = _stop_resources_wait(
        env, cib, elements_to_remove.resources_to_remove, force_flags
    )

    remove_specified_elements(cib, elements_to_remove)
    env.push_cib()


def _stop_resources_wait(
    env: LibraryEnvironment,
    cib: _Element,
    resource_elements: Sequence[_Element],
    force_flags: reports.types.ForceFlags = (),
) -> _Element:
    """
    Stop all resources that are going to be removed. Push cib, wait for the
    cluster to settle down, and check if all resources were properly stopped.
    If not, report errors. Return cib with the applied changes.

    cib -- whole cib
    resource_elements -- resources that should be stopped
    force_flags -- list of flags codes
    """
    if not resource_elements:
        return cib
    if not env.is_cib_live:
        return cib
    if reports.codes.FORCE in force_flags:
        env.report_processor.report(
            reports.ReportItem.warning(
                reports.messages.StoppingResourcesBeforeDeletingSkipped()
            )
        )
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


def _ensure_some_stonith_remains(
    env: LibraryEnvironment,
    resources_el: _Element,
    elements_to_remove: ElementsToRemove,
    force_flags: reports.types.ForceFlags,
) -> reports.ReportItemList:
    if not any(is_stonith(el) for el in elements_to_remove.resources_to_remove):
        # if no stonith are beieng removed then we don't need to check if any
        # stonith will be left
        return []

    stonith_left = [
        stonith_el
        for stonith_el in get_all_node_isolating_resources(resources_el)
        if stonith_el.attrib["id"] not in elements_to_remove.ids_to_remove
    ]
    if stonith_left:
        return []
    if _is_sbd_enabled(env):
        return []
    return [
        reports.ReportItem(
            reports.get_severity(
                reports.codes.FORCE, reports.codes.FORCE in force_flags
            ),
            reports.messages.NoStonithMeansWouldBeLeft(),
        )
    ]


def _is_sbd_enabled(env: LibraryEnvironment) -> bool:
    if not env.is_cib_live:
        # We cannot tell whether sbd is enabled or not, as we do not have
        # access to a cluster. Expect sbd is not enabled.
        return False

    # Do not return errors. The check should not prevent deleting a resource
    # just because a node in a cluster is temporarily unavailable. We do our
    # best to figure out sbd status.
    node_list, get_nodes_report_list = get_existing_nodes_names(
        env.get_corosync_conf()
    )
    env.report_processor.report_list(get_nodes_report_list)
    if not node_list:
        env.report_processor.report(
            reports.ReportItem.warning(
                reports.messages.CorosyncConfigNoNodesDefined()
            )
        )
        return False

    com_cmd = GetSbdStatus(env.report_processor)
    com_cmd.set_targets(
        env.get_node_target_factory().get_target_list(
            node_list, skip_non_existing=True
        )
    )
    response_per_node = run_communication(env.get_node_communicator(), com_cmd)
    for response in response_per_node:
        # It is required to compare with False even if it looks wrong. The
        # value can be either True (== sbd is enabled), or False (== sbd is
        # disabled), or None (== unknown, not connected).
        # We do not want to block removing resources just because we were
        # temporarily unable to connect to a node, so we do not return False
        # when the result is None.
        if (
            response["status"]["enabled"] is False
            or response["status"]["running"] is False
        ):
            return False
    return True
