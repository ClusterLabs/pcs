from pcs.daemon.app.api_v0_tools import reports_to_str
from pcs.daemon.app.ui_manage.base_handler import BaseAjaxProtectedManageHandler


class RemoveClusterHandler(BaseAjaxProtectedManageHandler):
    """
    Input format:

    Request parameters prefixed by "clusterid-" followed by the name of cluster:
    Example:
        clusterid-cluster1=<any_value>
        clusterid-cluster2=<any_value>

    The actual values don't matter; only the parameter names are used to
    extract cluster names.
    """

    async def _handle_request(self) -> None:
        cluster_names = [
            key.removeprefix("clusterid-")
            for key in self.request.arguments
            if key.startswith("clusterid-")
        ]

        result = await self._run_library_command(
            "manage_clusters.remove_clusters",
            {"cluster_names": cluster_names},
        )

        if not result.success:
            raise self._error(reports_to_str(result.reports))
