from functools import partial
import json
from unittest import TestCase

from pcs.common import report_codes
from pcs.lib.commands.sbd import get_cluster_sbd_status
from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools


warn_unable_to_get_sbd_status = partial(
    fixture.warn,
    report_codes.UNABLE_TO_GET_SBD_STATUS,
)

class GetClusterSbdStatus(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_default_different_results_on_different_nodes(self):
        node_name_list = ["node-1", "node-2", "node-3", "node-4", "node-5"]
        (self.config
            .env.set_known_nodes(node_name_list)
            .runner.corosync.version()
            .corosync_conf.load(node_name_list=node_name_list)
            .http.add_communication(
                "check_sbd",
                [
                    dict(
                        label="node-1",
                        output='{"notauthorized":"true"}',
                        response_code=401,
                    ),
                    dict(
                        label="node-2",
                        was_connected=False,
                        errno=6,
                        error_msg="Could not resolve host: node-2;"
                            " Name or service not known"
                        ,
                    ),
                    dict(
                        label="node-3",
                        output=json.dumps({
                            "sbd":{
                                "installed": True,
                                "enabled": False,
                                "running":False
                            },
                            "watchdog":{
                                "path":"",
                                "exist":False
                            },
                            "device_list":[]
                        }),
                        response_code=200,
                    ),
                    dict(
                        label="node-4",
                        output=json.dumps({
                            "watchdog":{
                                "path":"",
                                "exist":False
                            },
                            "device_list":[]
                        }),
                        response_code=200,
                    ),
                    dict(
                        label="node-5",
                        output="invalid json",
                        response_code=200,
                    ),
                ],
                action="remote/check_sbd",
                param_list=[("watchdog", ""), ("device_list", "[]")],
            )
        )

        default_status = {
            'running': None,
            'enabled': None,
            'installed': None,
        }
        self.assertEqual(
            get_cluster_sbd_status(self.env_assist.get_env()),
            [
                {
                    'node': 'node-3',
                    'status': {
                        'running': False,
                        'enabled': False,
                        'installed': True,
                    }
                },
                {
                    'node': 'node-1',
                    'status': default_status
                },
                {
                    'node': 'node-2',
                    'status': default_status
                },
                {
                    'node': 'node-4',
                    'status': default_status
                },
                {
                    'node': 'node-5',
                    'status': default_status
                },
            ]
        )
        self.env_assist.assert_reports([
            fixture.warn(
                report_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED,
                node="node-1",
                reason="HTTP error: 401",
                command="remote/check_sbd",
            ),
            warn_unable_to_get_sbd_status(node="node-1", reason=""),
            fixture.warn(
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                node="node-2",
                reason=
                    "Could not resolve host: node-2; Name or service not known"
                ,
                command="remote/check_sbd",
            ),
            warn_unable_to_get_sbd_status(node="node-2", reason=""),
            warn_unable_to_get_sbd_status(node="node-4", reason="'sbd'"),
            warn_unable_to_get_sbd_status(
                node="node-5",
                #the reason differs in python3
                #reason="No JSON object could be decoded",
            ),
        ])
