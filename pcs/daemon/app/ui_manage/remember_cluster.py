from pcs.common import reports
from pcs.daemon.app.api_v0_tools import reports_to_str
from pcs.daemon.app.ui_manage.base_handler import BaseAjaxProtectedManageHandler


class RememberClusterHandler(BaseAjaxProtectedManageHandler):
    """
    Input format:

    Request arguments:
        cluster_name: Name of the cluster to add
        nodes[]: List of node names in the cluster (multiple values)

    Example:
        cluster_name=mycluster
        nodes[]=node1
        nodes[]=node2
        nodes[]=node3
    """

    async def _handle_request(self) -> None:
        lib_command_arguments = {
            "cluster_name": self.get_argument("cluster_name", ""),
            "cluster_nodes": self.get_arguments("nodes[]"),
        }
        result = await self._run_library_command(
            "manage_clusters.add_cluster", lib_command_arguments
        )

        # The lib command fetches the newest file and saves it locally when
        # conflict is detected. Running the lib command second time will add
        # the cluster to the newest config, possibly resolving the conflict.
        # This is how the original Ruby handler behaved.
        if not result.success and any(
            rep.message.code == reports.codes.PCS_CFGSYNC_CONFLICT_REPEAT_ACTION
            for rep in result.reports
        ):
            result = await self._run_library_command(
                "manage_clusters.add_cluster", lib_command_arguments
            )

        if not result.success:
            raise self._error(reports_to_str(result.reports))
