import json
from typing import Any

from tornado.web import MissingArgumentError

from pcs import settings
from pcs.common import reports
from pcs.daemon.app.api_v0_tools import reports_to_str
from pcs.daemon.app.ui_manage.base_handler import BaseAjaxProtectedManageHandler
from pcs.lib.auth.const import SUPERUSER


class ManageAuthGuiAgainstNodesHandler(BaseAjaxProtectedManageHandler):
    async def _handle_request(self) -> None:
        """
        Format of the response:

        {
            "node_auth_error": {
                "node1": 1 # unable to auth this node
                "node2": 0
            },
            "local_cluster_node_auth_error": {
                "node3": 1 # missing auth token for communication with this node
            },
            "plaintext_error": "" # other errors in plaintext format
        }
        """

        try:
            data_json = self.get_argument("data_json")
        except MissingArgumentError as e:
            raise self._error("Missing required parameter: data_json") from e

        try:
            data = json.loads(data_json)
            nodes = data.get("nodes", {})
            for node_name, node_data in nodes.items():
                node_data["username"] = SUPERUSER
                dest_list = node_data.get("dest_list", [])
                for dest in dest_list:
                    # we cannot use dest.get("addr", node_name).
                    # we want to treat empty strings the same way as missing
                    # values
                    dest["addr"] = dest.get("addr") or node_name
                    dest["port"] = (
                        dest.get("port") or settings.pcsd_default_port
                    )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise self._error("Invalid data format") from e

        result = await self._run_library_command(
            "auth.auth_hosts", {"hosts": nodes}
        )

        node_auth_error: dict[str, int] = dict.fromkeys(nodes, 1)
        local_cluster_node_auth_error: dict[str, int] = {}
        wanted_reports: list[reports.dto.ReportItemDto] = []

        for rep in result.reports:
            if rep.message.code == reports.codes.AUTHORIZATION_SUCCESSFUL:
                node_name = rep.context.node if rep.context else ""
                if node_name in node_auth_error:
                    node_auth_error[node_name] = 0
            elif rep.message.code == reports.codes.HOST_NOT_FOUND:
                # Track nodes where we couldn't sync tokens due to missing
                # local cluster tokens
                node_name_list = rep.message.payload.get("host_list", [])
                for node_name in node_name_list:
                    local_cluster_node_auth_error[node_name] = 1
            elif (
                rep.message.code
                == reports.codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED
            ):
                # Track nodes where we couldn't sync tokens due to auth
                # failure
                node_name = rep.message.payload.get("node", "")
                if node_name:
                    local_cluster_node_auth_error[node_name] = 1
            elif rep.severity.level == reports.ReportItemSeverity.ERROR:
                wanted_reports.append(rep)

        response: dict[str, Any] = {
            "node_auth_error": node_auth_error,
            "local_cluster_node_auth_error": local_cluster_node_auth_error,
            "plaintext_error": reports_to_str(wanted_reports),
        }

        self.set_status(200)
        self.write(json.dumps(response))
