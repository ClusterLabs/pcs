from __future__ import (
    absolute_import,
    division,
    print_function,
)

import json
import base64

from pcs.test.tools import fixture
from pcs.common import report_codes
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.pcs_unittest import TestCase, mock
from pcs.lib.commands.remote_node import node_add_remote

class AddRemote(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.host = "remote-candidate"

    def test_fails_when_remote_node_is_offline(self):
        error_msg = "Could not resolve host: remote-candidate"
        (self.config
            .runner.cib.load()
            .corosync_conf.load(node_name_list=["node-1", "node-2"])
            .runner.pcmk.load_agent(agent_name="ocf:pacemaker:remote")
            .http.add_communication(
                "node_available",
                [dict(label=self.host)],
                action="remote/node_available",
                was_connected=False,
                errno='6',
                error_msg_template=error_msg,
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(
                self.env_assist.get_env(),
                self.host,
                node_name="node-candidate",
                operations=[],
                meta_attributes={},
                instance_attributes={}
            ),
            [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.host,
                    reason=error_msg,
                    command="remote/node_available",
                    force_code=report_codes.SKIP_OFFLINE_NODES
                )
            ]
        )

    def test_success(self):
        pcmk_authkey_content = b"password"
        (self.config
            .runner.cib.load()
            .corosync_conf.load(node_name_list=["node-1", "node-2"])
            .runner.pcmk.load_agent(agent_name="ocf:pacemaker:remote")
            .http.add_communication(
                "node_available",
                [dict(label=self.host)],
                action="remote/node_available",
                output=json.dumps({"node_available": True})
            )
            .fs.exists("/etc/pacemaker/authkey", return_value=True)
            .fs.open(
                "/etc/pacemaker/authkey",
                return_value=mock.mock_open(read_data=pcmk_authkey_content)(),
            )
            .http.add_communication(
                "put_file",
                [dict(label=self.host)],
                action="remote/put_file",
                param_list=[(
                    "data_json",
                    json.dumps({
                        "pacemaker_remote authkey": {
                            "type": "pcmk_remote_authkey",
                            "data":
                                base64
                                    .b64encode(pcmk_authkey_content)
                                    .decode("utf-8")
                            ,
                            "rewrite_existing": True
                        }
                    })
                )],
                output=json.dumps({
                    "files": {
                        "pacemaker_remote authkey": {
                            "code": "written",
                            "message": "",
                        }
                    }
                })
            )
            .http.add_communication(
                "enable_start_pacemaker_remote",
                [dict(label=self.host)],
                action="remote/manage_services",
                param_list=[(
                    "data_json",
                    json.dumps({
                        "pacemaker_remote enable": {
                            "type": "service_command",
                            "service": "pacemaker_remote",
                            "command": "enable",
                        },
                        "pacemaker_remote start": {
                            "type": "service_command",
                            "service": "pacemaker_remote",
                            "command": "start",
                        },
                    })
                )],
                output=json.dumps({
                    "actions": {
                        "pacemaker_remote enable": {
                            "code": "success",
                            "message": "",
                        },
                        "pacemaker_remote start": {
                            "code": "success",
                            "message": "",
                        }
                    }
                })
            )
            .env.push_cib(resources=
                """
                <resources>
                    <primitive class="ocf" id="node-candidate"
                        provider="pacemaker" type="remote"
                    >
                        <instance_attributes
                            id="node-candidate-instance_attributes"
                        >
                            <nvpair
                                id="node-candidate-instance_attributes-server"
                                name="server" value="remote-candidate"
                            />
                        </instance_attributes>
                        <operations>
                            <op id="node-candidate-migrate_from-interval-0s"
                                interval="0s" name="migrate_from" timeout="60"
                            />
                            <op id="node-candidate-migrate_to-interval-0s"
                                interval="0s" name="migrate_to" timeout="60"
                            />
                            <op id="node-candidate-monitor-interval-60s"
                                interval="60s" name="monitor" timeout="30"
                            />
                            <op id="node-candidate-reload-interval-0s"
                              interval="0s" name="reload" timeout="60"
                            />
                            <op id="node-candidate-start-interval-0s"
                                interval="0s" name="start" timeout="60"
                            />
                            <op id="node-candidate-stop-interval-0s"
                                interval="0s" name="stop" timeout="60"
                            />
                        </operations>
                    </primitive>
                </resources>
                """
            )
        )
        node_add_remote(
            self.env_assist.get_env(),
            self.host,
            node_name="node-candidate",
            operations=[],
            meta_attributes={},
            instance_attributes={}
        )
        self.env_assist.assert_reports([
            fixture.info(
                report_codes.FILES_DISTRIBUTION_STARTED,
                #python 3 has dict_keys so list is not the right structure
                file_list={"pacemaker_remote authkey": None}.keys(),
                description="remote node configuration files",
                node_list=[self.host],
            ),
            fixture.info(
                report_codes.FILE_DISTRIBUTION_SUCCESS,
                file_description="pacemaker_remote authkey",
                node=self.host,
            ),
            fixture.info(
                report_codes.SERVICE_COMMANDS_ON_NODES_STARTED,
                #python 3 has dict_keys so list is not the right structure
                action_list={
                    "pacemaker_remote start": None,
                    "pacemaker_remote enable": None,
                }.keys(),
                description="start of service pacemaker_remote",
                node_list=[self.host],
            ),
            fixture.info(
                report_codes.SERVICE_COMMAND_ON_NODE_SUCCESS,
                service_command_description="pacemaker_remote enable",
                node=self.host,
            ),
            fixture.info(
                report_codes.SERVICE_COMMAND_ON_NODE_SUCCESS,
                service_command_description="pacemaker_remote start",
                node=self.host,
            ),
        ])
