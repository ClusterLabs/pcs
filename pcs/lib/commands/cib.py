from typing import Iterable, Sequence

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.resource_status import (
    MoreChildrenQuantifierType,
    ResourcesStatusFacade,
    ResourceState,
)
from pcs.common.types import StringCollection, StringSequence
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
from pcs.lib.cib.resource.stonith import is_stonith
from pcs.lib.cib.tools import get_resources
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.state import ensure_resource_state
from pcs.lib.pacemaker.status import (
    ClusterStatusParser,
    ClusterStatusParsingError,
    cluster_status_parsing_error_to_report,
)
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

    report_processor.report_list(
        _validate_elements_to_remove(elements_to_remove)
        + _ensure_not_guest_remote(elements_to_remove.resources_to_remove)
        + ensure_some_stonith_remains(
            env,
            get_resources(cib),
            stonith_resources_to_ignore=[
                str(res_el.attrib["id"])
                for res_el in elements_to_remove.resources_to_remove
                if is_stonith(res_el)
            ],
            sbd_being_disabled=False,
            force_flags=force_flags,
        )
    )
    if elements_to_remove.resources_to_remove:
        resource_ids = [
            str(el.attrib["id"])
            for el in elements_to_remove.resources_to_remove
        ]
        if env.is_cib_live:
            report_processor.report_list(
                ensure_resources_stopped(
                    env.get_cluster_state(), resource_ids, force_flags
                )
            )
        else:
            report_processor.report(
                reports.ReportItem.warning(
                    reports.messages.StoppedResourcesBeforeDeleteCheckSkipped(
                        resource_ids, reports.const.REASON_NOT_LIVE_CIB
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


# TODO: remove, since we want to handle resource stopping in clients instead
# of this lib command
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
        _ensure_resources_stopped_after_stop(
            env.get_cluster_state(), resource_ids
        )
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


# TODO: remove, since we want to handle resource stopping in clients instead
# of this lib command. Also remove the report message that is used here
def _ensure_resources_stopped_after_stop(
    state: _Element, resource_ids: StringSequence
) -> reports.ReportItemList:
    """
    Ensure that all resources that should be stopped are stopped.

    state -- state of the cluster
    elements -- elements planned to be removed
    """
    not_stopped_ids = []
    report_list: reports.ReportItemList = []
    try:
        parser = ClusterStatusParser(state)
        try:
            status_dto = parser.status_xml_to_dto()
        except ClusterStatusParsingError as e:
            report_list.append(cluster_status_parsing_error_to_report(e))
            return report_list
        report_list.extend(parser.get_warnings())

        status = ResourcesStatusFacade.from_resources_status_dto(status_dto)
        for r_id in resource_ids:
            if not status.exists(r_id, None):
                # Pacemaker does not put misconfigured resources into cluster
                # status and we are unable to check state of such resources.
                # This happens for e.g. undle with primitive resource inside and
                # no IP address for the bundle specified. We expect the resource
                # to be stopped since it is misconfigured.
                report_list.append(
                    reports.ReportItem.debug(
                        reports.messages.ConfiguredResourceMissingInStatus(
                            r_id, ResourceState.STOPPED
                        )
                    )
                )
            elif not status.is_state(
                r_id,
                None,
                ResourceState.STOPPED,
                instances_quantifier=(
                    MoreChildrenQuantifierType.ALL
                    if status.can_have_multiple_instances(r_id)
                    else None
                ),
            ):
                not_stopped_ids.append(r_id)
    except NotImplementedError:
        # TODO remove when issue with bundles in status is fixed
        not_stopped_ids = [
            resource_id
            for resource_id in resource_ids
            if ensure_resource_state(False, state, resource_id).severity.level
            == reports.item.ReportItemSeverity.ERROR
        ]

    if not_stopped_ids:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.CannotStopResourcesBeforeDeleting(
                    not_stopped_ids
                ),
                force_code=reports.codes.FORCE,
            )
        )

    return report_list
