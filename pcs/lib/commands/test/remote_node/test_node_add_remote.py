from __future__ import (
    absolute_import,
    division,
    print_function,
)

import base64
from functools import partial
import json

from pcs.test.tools import fixture
from pcs.common import report_codes
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.pcs_unittest import TestCase, mock
from pcs.lib.commands.remote_node import node_add_remote as node_add_remote_original

PCMK_AUTHKEY_PATH = "/etc/pacemaker/authkey"
REMOTE_HOST = "remote-candidate"
NODE_NAME = "node-candidate"
NODE_1 = "node-1"
NODE_2 = "node-2"


def node_add_remote(
    env, host, node_name, operations=None, meta_attributes=None,
    instance_attributes=None, **kwargs
):
    operations = operations or []
    meta_attributes = meta_attributes or {}
    instance_attributes = instance_attributes or {}

    node_add_remote_original(
        env, host, node_name, operations, meta_attributes, instance_attributes,
        **kwargs
    )


class LocalConfig(object):
    def __init__(self, call_collection, wrap_helper, config):
        self.__calls = call_collection
        self.config = config

    def distribute_authkey(
        self, communication_list, pcmk_authkey_content, result=None
    ):
        result = result if result is not None else {
            "code": "written",
            "message": "",
        }
        self.config.http.put_file(
            communication_list=communication_list,
            files={
                "pacemaker_remote authkey": {
                    "type": "pcmk_remote_authkey",
                    "data": base64
                        .b64encode(pcmk_authkey_content)
                        .decode("utf-8")
                    ,
                    "rewrite_existing": True
                }
            },
            results={"pacemaker_remote authkey": result}
        )

    def run_pacemaker_remote(self, label, result=None):
        result = result if result is not None else {
            "code": "success",
            "message": "",
        }
        self.config.http.manage_services(
            communication_list=[dict(label=label)],
            action_map={
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
            },
            results={
                "pacemaker_remote enable": result,
                "pacemaker_remote start": result
            }
        )

    def check_node_availability(self, label, result=True, **kwargs):
        if "output" not in kwargs:
            kwargs["output"] = json.dumps({"node_available": result})

        self.config.http.place_multinode_call(
            "node_available",
            communication_list=[dict(label=label)],
            action="remote/node_available",
            **kwargs
        )

    def authkey_exists(self, return_value):
        self.config.fs.exists(PCMK_AUTHKEY_PATH, return_value=return_value)

    def push_existing_authkey_to_remote(
        self, remote_host, distribution_result=None
    ):
        pcmk_authkey_content = b"password"
        (self.config
            .local.authkey_exists(return_value=True)
            .fs.open(
                PCMK_AUTHKEY_PATH,
                return_value=mock.mock_open(read_data=pcmk_authkey_content)(),
            )
            .local.distribute_authkey(
                communication_list=[dict(label=remote_host)],
                pcmk_authkey_content=pcmk_authkey_content,
                result=distribution_result
            )
         )

    def load_cluster_configs(self, cluster_node_list):
        (self.config
            .runner.cib.load()
            .corosync_conf.load(node_name_list=cluster_node_list)
            .runner.pcmk.load_agent(agent_name="ocf:pacemaker:remote")
        )

def fixture_authkey_distribution_started_info(node_list):
    return [
        fixture.info(
            report_codes.FILES_DISTRIBUTION_STARTED,
            #python 3 has dict_keys so list is not the right structure
            file_list={"pacemaker_remote authkey": None}.keys(),
            description="remote node configuration files",
            node_list=node_list,
        ),
    ]

def fixture_authkey_distribution_info(node_list):
    return(
        fixture_authkey_distribution_started_info(node_list)
        +
        [
            fixture.info(
                report_codes.FILE_DISTRIBUTION_SUCCESS,
                file_description="pacemaker_remote authkey",
                node=node,
            ) for node in node_list
        ]
    )

def fixture_pcmk_remote_run_started(node):
    return [
        fixture.info(
            report_codes.SERVICE_COMMANDS_ON_NODES_STARTED,
            #python 3 has dict_keys so list is not the right structure
            action_list={
                "pacemaker_remote start": None,
                "pacemaker_remote enable": None,
            }.keys(),
            description="start of service pacemaker_remote",
            node_list=[node],
        )
    ]


def fixture_pcmk_remote_run(node):
    return (
        fixture_pcmk_remote_run_started(node)
        +
        [
            fixture.info(
                report_codes.SERVICE_COMMAND_ON_NODE_SUCCESS,
                service_command_description="pacemaker_remote enable",
                node=node,
            ),
            fixture.info(
                report_codes.SERVICE_COMMAND_ON_NODE_SUCCESS,
                service_command_description="pacemaker_remote start",
                node=node,
            ),
        ]
    )

def fixture_turn_node_to_remote_full_info(remote_host):
    return (
        fixture_authkey_distribution_info([remote_host])
        +
        fixture_pcmk_remote_run(remote_host)
    )

get_env_tools = partial(
    get_env_tools,
    local_extensions={"local": LocalConfig}
)
FIXTURE_RESOURCES = """
    <resources>
        <primitive class="ocf" id="node-candidate" provider="pacemaker"
            type="remote"
        >
            <instance_attributes id="node-candidate-instance_attributes">
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

class AddRemote(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_success_base(self):
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, result=True)
            .local.push_existing_authkey_to_remote(REMOTE_HOST)
            .local.run_pacemaker_remote(REMOTE_HOST)
            .env.push_cib(resources=FIXTURE_RESOURCES)
        )
        node_add_remote(
            self.env_assist.get_env(),
            REMOTE_HOST,
            node_name=NODE_NAME,
        )
        self.env_assist.assert_reports(
            fixture_turn_node_to_remote_full_info(REMOTE_HOST)
        )

    @mock.patch("pcs.lib.commands.remote_node.generate_key")
    def test_success_generated_authkey(self, generate_key):
        generate_key.return_value = b"password"
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, result=True)
            .local.authkey_exists(return_value=False)
            .local.distribute_authkey(
                communication_list=[
                    dict(label=NODE_1),
                    dict(label=NODE_2),
                    dict(label=REMOTE_HOST),
                ],
                pcmk_authkey_content=generate_key.return_value,
            )
            .local.run_pacemaker_remote(REMOTE_HOST)
            .env.push_cib(resources=FIXTURE_RESOURCES)
        )
        node_add_remote(
            self.env_assist.get_env(),
            REMOTE_HOST,
            node_name=NODE_NAME,
        )
        generate_key.assert_called_once_with()
        self.env_assist.assert_reports(
            fixture_authkey_distribution_info([NODE_1, NODE_2, REMOTE_HOST])
            +
            fixture_pcmk_remote_run(REMOTE_HOST)
        )

    def test_fail_run_pcmk_remote(self):
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, result=True)
            .local.push_existing_authkey_to_remote(REMOTE_HOST)
            .local.run_pacemaker_remote(REMOTE_HOST, result={
                "code": "fail",
                "message": "Action failed",
            })
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(
                self.env_assist.get_env(),
                REMOTE_HOST,
                node_name=NODE_NAME,
            )
        )

        self.env_assist.assert_reports(
            fixture_authkey_distribution_info([REMOTE_HOST])
            +
            fixture_pcmk_remote_run_started(REMOTE_HOST)
            +
            [
                fixture.error(
                    report_codes.SERVICE_COMMAND_ON_NODE_ERROR,
                    node=REMOTE_HOST,
                    reason="Operation failed.",
                    service_command_description="pacemaker_remote enable",
                    force_code=report_codes.SKIP_ACTION_ON_NODES_ERRORS
                ),
                fixture.error(
                    report_codes.SERVICE_COMMAND_ON_NODE_ERROR,
                    node=REMOTE_HOST,
                    reason="Operation failed.",
                    service_command_description="pacemaker_remote start",
                    force_code=report_codes.SKIP_ACTION_ON_NODES_ERRORS
                )
            ]
        )

    def test_skipable_fail_run_pcmk_remote(self):
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, result=True)
            .local.push_existing_authkey_to_remote(REMOTE_HOST)
            .local.run_pacemaker_remote(REMOTE_HOST, result={
                "code": "fail",
                "message": "Action failed",
            })
            .env.push_cib(resources=FIXTURE_RESOURCES)
        )
        node_add_remote(
            self.env_assist.get_env(),
            REMOTE_HOST,
            node_name=NODE_NAME,
            allow_pacemaker_remote_service_fail=True
        )

        self.env_assist.assert_reports(
            fixture_authkey_distribution_info([REMOTE_HOST])
            +
            fixture_pcmk_remote_run_started(REMOTE_HOST)
            +
            [
                fixture.warn(
                    report_codes.SERVICE_COMMAND_ON_NODE_ERROR,
                    node=REMOTE_HOST,
                    reason="Operation failed.",
                    service_command_description="pacemaker_remote enable",
                ),
                fixture.warn(
                    report_codes.SERVICE_COMMAND_ON_NODE_ERROR,
                    node=REMOTE_HOST,
                    reason="Operation failed.",
                    service_command_description="pacemaker_remote start",
                )
            ]
        )

    def test_fail_autkey_distribution(self):
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, result=True)
            .local.push_existing_authkey_to_remote(
                REMOTE_HOST,
                distribution_result={
                    "code": "conflict",
                    "message": "",
                }
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(
                self.env_assist.get_env(),
                REMOTE_HOST,
                node_name=NODE_NAME,
            )
        )

        self.env_assist.assert_reports(
            fixture_authkey_distribution_started_info([REMOTE_HOST])
            +
            [
                fixture.error(
                    report_codes.FILE_DISTRIBUTION_ERROR,
                    node=REMOTE_HOST,
                    reason="File already exists",
                    file_description="pacemaker_remote authkey",
                    force_code=report_codes.SKIP_FILE_DISTRIBUTION_ERRORS
                ),
            ]
        )

    def test_fails_when_remote_node_is_offline(self):
        error_msg = "Could not resolve host: remote-candidate"
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(
                REMOTE_HOST,
                output="",
                was_connected=False,
                errno='6',
                error_msg_template=error_msg,
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(
                self.env_assist.get_env(),
                REMOTE_HOST,
                node_name=NODE_NAME,
            ),
            [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=REMOTE_HOST,
                    reason=error_msg,
                    command="remote/node_available",
                    force_code=report_codes.SKIP_OFFLINE_NODES
                )
            ]
        )

class WithWait(TestCase):
    def setUp(self):
        self. wait = 1
        self.env_assist, self.config = get_env_tools(self)
        (self.config
            .runner.pcmk.can_wait()
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, result=True)
            .local.push_existing_authkey_to_remote(REMOTE_HOST)
            .local.run_pacemaker_remote(REMOTE_HOST)
            .env.push_cib(resources=FIXTURE_RESOURCES, wait=self.wait)
         )

    def test_success_when_resource_started(self):
        (self.config
            .runner.pcmk.load_state(raw_resources=dict(
                resource_id=NODE_NAME,
                resource_agent="ocf::pacemaker:remote",
                node_name=NODE_1,
            ))
        )
        node_add_remote(
            self.env_assist.get_env(),
            REMOTE_HOST,
            node_name=NODE_NAME,
            wait=self.wait
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.RESOURCE_RUNNING_ON_NODES,
                    roles_with_nodes={"Started": [NODE_1]},
                    resource_id=NODE_NAME
                ),
            ]
            +
            fixture_turn_node_to_remote_full_info(REMOTE_HOST)
        )

    def test_fail_when_resource_not_started(self):
        (self.config
            .runner.pcmk.load_state(raw_resources=dict(
                resource_id=NODE_NAME,
                resource_agent="ocf::pacemaker:remote",
                node_name=NODE_1,
                failed="true",
            ))
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(
                self.env_assist.get_env(),
                REMOTE_HOST,
                node_name=NODE_NAME,
                wait=self.wait
            ),
            [
                fixture.error(
                    report_codes.RESOURCE_DOES_NOT_RUN,
                    resource_id=NODE_NAME,
                )
            ]
        )
        self.env_assist.assert_reports(
            fixture_turn_node_to_remote_full_info(REMOTE_HOST)
        )
