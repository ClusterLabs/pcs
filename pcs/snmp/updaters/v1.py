import logging

from pcs.snmp.agentx.types import (
    IntegerType,
    Oid,
    StringType,
)
from pcs.snmp.agentx.updater import AgentxUpdaterBase
from pcs.utils import run_pcsdcli

logger = logging.getLogger("pcs.snmp.updaters.v1")
logger.addHandler(logging.NullHandler())

_cluster_v1_oid_tree = Oid(
    1,
    "pcmkPcsV1Cluster",
    member_list=[
        Oid(1, "pcmkPcsV1ClusterName", StringType),
        Oid(2, "pcmkPcsV1ClusterQuorate", IntegerType),
        Oid(3, "pcmkPcsV1ClusterNodesNum", IntegerType),
        Oid(4, "pcmkPcsV1ClusterNodesNames", StringType),
        Oid(5, "pcmkPcsV1ClusterCorosyncNodesOnlineNum", IntegerType),
        Oid(6, "pcmkPcsV1ClusterCorosyncNodesOnlineNames", StringType),
        Oid(7, "pcmkPcsV1ClusterCorosyncNodesOfflineNum", IntegerType),
        Oid(8, "pcmkPcsV1ClusterCorosyncNodesOfflineNames", StringType),
        Oid(9, "pcmkPcsV1ClusterPcmkNodesOnlineNum", IntegerType),
        Oid(10, "pcmkPcsV1ClusterPcmkNodesOnlineNames", StringType),
        Oid(11, "pcmkPcsV1ClusterPcmkNodesStandbyNum", IntegerType),
        Oid(12, "pcmkPcsV1ClusterPcmkNodesStandbyNames", StringType),
        Oid(13, "pcmkPcsV1ClusterPcmkNodesOfflineNum", IntegerType),
        Oid(14, "pcmkPcsV1ClusterPcmkNodesOfflineNames", StringType),
        Oid(15, "pcmkPcsV1ClusterAllResourcesNum", IntegerType),
        Oid(16, "pcmkPcsV1ClusterAllResourcesIds", StringType),
        Oid(17, "pcmkPcsV1ClusterRunningResourcesNum", IntegerType),
        Oid(18, "pcmkPcsV1ClusterRunningResourcesIds", StringType),
        Oid(19, "pcmkPcsV1ClusterStoppedResourcesNum", IntegerType),
        Oid(20, "pcmkPcsV1ClusterStoppedResourcesIds", StringType),
        Oid(21, "pcmkPcsV1ClusterFailedResourcesNum", IntegerType),
        Oid(22, "pcmkPcsV1ClusterFailedResourcesIds", StringType),
    ],
)


class ClusterPcsV1Updater(AgentxUpdaterBase):
    _oid_tree = Oid(0, "pcs_v1", member_list=[_cluster_v1_oid_tree])

    def update(self):
        # pylint: disable=too-many-locals
        output, ret_val = run_pcsdcli("node_status")
        if ret_val != 0 or output["status"] != "ok":
            logger.error(
                "Unable to obtain cluster status.\nPCSD return code: %s\n"
                "PCSD output: %s\n",
                ret_val,
                output,
            )
            return
        data = output["data"]
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterName",
            data.get("cluster_name", ""),
        )
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterQuorate",
            _bool_to_int(data.get("node", {}).get("quorum")),
        )

        # nodes
        known_nodes = data.get("known_nodes", [])
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterNodesNum", len(known_nodes)
        )
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterNodesNames", known_nodes
        )

        corosync_nodes_online = data.get("corosync_online")
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterCorosyncNodesOnlineNum",
            len(corosync_nodes_online),
        )
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterCorosyncNodesOnlineNames",
            corosync_nodes_online,
        )

        corosync_nodes_offline = data.get("corosync_offline")
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterCorosyncNodesOfflineNum",
            len(corosync_nodes_offline),
        )
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterCorosyncNodesOfflineNames",
            corosync_nodes_offline,
        )

        pcmk_nodes_online = data.get("pacemaker_online")
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterPcmkNodesOnlineNum",
            len(pcmk_nodes_online),
        )
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterPcmkNodesOnlineNames",
            pcmk_nodes_online,
        )

        pcmk_nodes_standby = data.get("pacemaker_standby")
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterPcmkNodesStandbyNum",
            len(pcmk_nodes_standby),
        )
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterPcmkNodesStandbyNames",
            pcmk_nodes_standby,
        )

        pcmk_nodes_offline = data.get("pacemaker_offline")
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterPcmkNodesOfflineNum",
            len(pcmk_nodes_offline),
        )
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterPcmkNodesOfflineNames",
            pcmk_nodes_offline,
        )

        # resources
        primitive_list = []
        for resource in data.get("resource_list", []):
            primitive_list.extend(_get_primitives(resource))

        primitive_id_list = _get_resource_id_list(primitive_list)
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterAllResourcesNum",
            len(primitive_id_list),
        )
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterAllResourcesIds",
            primitive_id_list,
        )
        running_primitive_id_list = _get_resource_id_list(
            primitive_list, _res_in_status(["running"])
        )

        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterRunningResourcesNum",
            len(running_primitive_id_list),
        )
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterRunningResourcesIds",
            running_primitive_id_list,
        )

        disabled_primitive_id_list = _get_resource_id_list(
            primitive_list, _res_in_status(["disabled"])
        )
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterStoppedResourcesNum",
            len(disabled_primitive_id_list),
        )
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterStoppedResourcesIds",
            disabled_primitive_id_list,
        )

        failed_primitive_id_list = _get_resource_id_list(
            primitive_list,
            lambda res: not _res_in_status(["running", "disabled"])(res),
        )
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterFailedResourcesNum",
            len(failed_primitive_id_list),
        )
        self.set_value(
            "pcmkPcsV1Cluster.pcmkPcsV1ClusterFailedResourcesIds",
            failed_primitive_id_list,
        )


def _bool_to_int(value):
    return 1 if value else 0


def _get_primitives(resource):
    res_type = resource["class_type"]
    if res_type == "primitive":
        return [resource]
    if res_type == "group":
        primitive_list = []
        for primitive in resource["members"]:
            primitive_list.extend(_get_primitives(primitive))
        return primitive_list
    # check master-slave type
    if res_type in ["clone", "master"]:
        return _get_primitives(resource["member"])
    return []


def _get_resource_id_list(resource_list, predicate=None):
    if predicate is None:

        def predicate(_):
            return True

    return [resource["id"] for resource in resource_list if predicate(resource)]


def _res_in_status(status_list):
    return lambda res: res["status"] in status_list
