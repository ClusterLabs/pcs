from lxml.etree import _Element

from pcs.common import reports
from pcs.common.types import StringCollection
from pcs.lib.cib.resource.common import is_disabled as is_resource_disabled
from pcs.lib.cib.resource.stonith import get_all_node_isolating_resources
from pcs.lib.communication.sbd import GetSbdStatus
from pcs.lib.communication.tools import run as run_communication
from pcs.lib.env import LibraryEnvironment
from pcs.lib.node import get_existing_nodes_names


def ensure_some_stonith_remains(
    env: LibraryEnvironment,
    resources_el: _Element,
    stonith_resources_to_ignore: StringCollection,
    sbd_being_disabled: bool,
    force_flags: reports.types.ForceFlags,
) -> reports.ReportItemList:
    """
    Error out when no sbd or enabled stonith would be left after a config change

    resource_el -- cib element holding resources
    stonith_resources_to_ignore -- ids of stonith being removed, disabled, etc.
    sbd_being_disabled -- ignore working sbd as it is being disabled
    force_flags -- use to emit a warning instead of an error
    """
    # Checking whether sbd is enabled requires communicating with other cluster
    # nodes, which may bring additional issues, like nodes not being
    # accessible. To reduce clutter in reports, check for the sbd being enabled
    # only when necessary.

    if not stonith_resources_to_ignore and not sbd_being_disabled:
        # No stonith resources are being removed or disabled and SBD is not
        # being disabled either. There is no change in cluster fencing
        # capabilities and therefore nothing to report.
        return []

    current_stonith = [
        stonith_el
        for stonith_el in get_all_node_isolating_resources(resources_el)
        # If any nvset disables the resource, even with a rule to limit it to
        # specific time, then the resource wouldn't be able to fence all the
        # time and should be considered disabled.
        # However, pcs currently supports only one nvset for meta attributes,
        # so we only check that to be consistent. Checking all nvsets could
        # lead to a situation not resolvable by pcs, as pcs doesn't allow to
        # change other nvsets than the first one.
        # Technically, stonith resources can be disabled by their parent clones
        # or groups. However, pcs doesn't allow putting stonith to groups and
        # clones, so we don't check that.
        # The check is not perfect, but it is a reasonable effort, considering
        # that multiple nvsets are not supported for meta attributes by pcs now.
        # It can be improved when a need for it raises.
        if not is_resource_disabled(stonith_el)
    ]
    stonith_left = [
        stonith_el
        for stonith_el in current_stonith
        if stonith_el.attrib["id"] not in stonith_resources_to_ignore
    ]

    if stonith_left:
        # Working stonith devices will be present. No need to check for SBD.
        return []

    # No stonith in the cluster, need to check SBD.
    current_sbd_active = _is_sbd_active_on_any_node(env)
    sbd_left_active = current_sbd_active and not sbd_being_disabled

    if sbd_left_active:
        # SBD will be left enabled.
        return []

    if not current_stonith and not current_sbd_active:
        # Now we know that no enabled stonith will be left in the cluster and
        # sbd will also be disabled. However, if that already was the case, we
        # don't produce an error -> the cluster already cannot fence, saying
        # that it is a result of the current change would not be true.
        return []

    return [
        reports.ReportItem(
            reports.get_severity(
                reports.codes.FORCE, reports.codes.FORCE in force_flags
            ),
            reports.messages.NoStonithMeansWouldBeLeft(),
        )
    ]


def _is_sbd_active_on_any_node(env: LibraryEnvironment) -> bool:
    # SBD can be enabled only partially in the cluster. Even when that is the
    # case, we warn the user when disabling it. For example, SBD can be enabled
    # for full stack nodes and disabled for remote / guest nodes.
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
        # Values can be either True (== sbd is enabled), or False (== sbd is
        # disabled), or None (== unknown, not connected).
        # We do not want to block removing resources just because we were
        # temporarily unable to connect to a node.
        # If sbd is enabled and not running, then the cluster won't have any
        # fencing after removing all stonith resources. If sbd is not enabled
        # and running, then the cluster won't have any fencing after removing
        # all stonith resources and rebooting nodes once. So we need both
        # enabled and running to be true to consider sbd as active.
        if response["status"]["enabled"] and response["status"]["running"]:
            return True
    return False
