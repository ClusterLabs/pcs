from pcs.common import reports
from pcs.daemon.app.api_v0_tools import reports_to_str
from pcs.daemon.app.ui_manage.base_handler import BaseAjaxProtectedManageHandler


class ManageExistingClusterHandler(BaseAjaxProtectedManageHandler):
    async def _handle_request(self) -> None:
        node_name = self.get_argument("node-name", "")
        result = await self._process_request(
            "manage_clusters.add_existing_cluster",
            {"node_name": node_name},
        )

        # Replicate the output format of the original Ruby implementation where
        # possible and reasonable
        if result.success:
            for rep in result.reports:
                if (
                    rep.message.code
                    == reports.codes.UNABLE_TO_GET_CLUSTER_KNOWN_HOSTS
                ):
                    cluster_name = rep.message.payload.get("cluster_name", "")
                    self.write(
                        "Unable to automatically authenticate against cluster "
                        "nodes: cannot get authentication info from cluster "
                        f"'{cluster_name}'"
                    )
                    return
            return

        for rep in result.reports:
            if (
                rep.message.code
                == reports.codes.UNABLE_TO_GET_CLUSTER_INFO_FROM_STATUS
            ):
                node = rep.context.node if rep.context else node_name
                raise self._error(
                    (
                        "Unable to communicate with remote pcsd on node "
                        f"'{node}'."
                    ),
                )

            if rep.message.code == reports.codes.NODE_NOT_IN_CLUSTER:
                node = rep.context.node if rep.context else node_name
                raise self._error(
                    (
                        f"The node, '{node}', does not currently have a cluster "
                        "configured. You must create a cluster using this node "
                        "before adding it to pcsd."
                    ),
                )

            if rep.message.code == reports.codes.CLUSTER_NAME_ALREADY_IN_USE:
                cluster_name = rep.message.payload.get("cluster_name", "")
                raise self._error(
                    (
                        f"The cluster name '{cluster_name}' has already been "
                        "added. You may not add two clusters with the same "
                        "name."
                    ),
                )

        # return all errors and warnings in case we did not handle them above
        raise self._error(
            reports_to_str(
                rep
                for rep in result.reports
                if rep.severity.level
                in (
                    reports.ReportItemSeverity.ERROR,
                    reports.ReportItemSeverity.WARNING,
                )
            )
        )
