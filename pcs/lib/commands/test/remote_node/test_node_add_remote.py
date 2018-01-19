from __future__ import (
    absolute_import,
    division,
    print_function,
)

import base64
import json
from functools import partial

from pcs.common import report_codes, env_file_role_codes
from pcs.lib.commands.remote_node import(
    node_add_remote as node_add_remote_original
)
from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.pcs_unittest import TestCase, mock


PCMK_AUTHKEY_PATH = "/etc/pacemaker/authkey"
REMOTE_HOST = "remote-candidate"
NODE_NAME = "node-name"
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
        self, communication_list, pcmk_authkey_content, result=None, **kwargs
    ):
        if kwargs.get("was_connected", True):
            result = result if result is not None else {
                "code": "written",
                "message": "",
            }

            kwargs["results"] = {
                "pacemaker_remote authkey": result
            }
        elif result is not None:
            raise AssertionError(
                "Keyword 'result' makes no sense with 'was_connected=False'"
            )
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
            **kwargs
        )

    def run_pacemaker_remote(self, label, result=None, **kwargs):
        if kwargs.get("was_connected", True):
            result = result if result is not None else {
                "code": "success",
                "message": "",
            }

            kwargs["results"] = {
                "pacemaker_remote enable": result,
                "pacemaker_remote start": result
            }
        elif result is not None:
            raise AssertionError(
                "Keyword 'result' makes no sense with 'was_connected=False'"
            )

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
            **kwargs
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

    def open_authkey(self, pcmk_authkey_content="", fail=False):
        kwargs = {}
        if fail:
            kwargs["side_effect"] = EnvironmentError("open failed")
        else:
            kwargs["return_value"] = mock.mock_open(
                read_data=pcmk_authkey_content
            )()

        self.config.fs.open(
            PCMK_AUTHKEY_PATH,
            **kwargs
        )


    def push_existing_authkey_to_remote(
        self, remote_host, distribution_result=None
    ):
        pcmk_authkey_content = b"password"
        (self.config
            .local.authkey_exists(return_value=True)
            .local.open_authkey(pcmk_authkey_content)
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

get_env_tools = partial(get_env_tools, local_extensions={"local": LocalConfig})

FIXTURE_REPORTS = (fixture.ReportStore()
    .info(
        "authkey_distribution_started" ,
        report_codes.FILES_DISTRIBUTION_STARTED,
        #python 3 has dict_keys so list is not the right structure
        file_list={"pacemaker_remote authkey": None}.keys(),
        description="remote node configuration files",
        node_list=[REMOTE_HOST],
    )
    .info(
        "authkey_distribution_success",
        report_codes.FILE_DISTRIBUTION_SUCCESS,
        file_description="pacemaker_remote authkey",
        node=REMOTE_HOST,
    )
    .info(
        "pcmk_remote_start_enable_started",
        report_codes.SERVICE_COMMANDS_ON_NODES_STARTED,
        #python 3 has dict_keys so list is not the right structure
        action_list={
            "pacemaker_remote start": None,
            "pacemaker_remote enable": None,
        }.keys(),
        description="start of service pacemaker_remote",
        node_list=[REMOTE_HOST],
    )
    .info(
        "pcmk_remote_enable_success",
        report_codes.SERVICE_COMMAND_ON_NODE_SUCCESS,
        service_command_description="pacemaker_remote enable",
        node=REMOTE_HOST,
    )
    .info(
        "pcmk_remote_start_success",
        report_codes.SERVICE_COMMAND_ON_NODE_SUCCESS,
        service_command_description="pacemaker_remote start",
        node=REMOTE_HOST,
    )
)

FIXTURE_RESOURCES = """
    <resources>
        <primitive class="ocf" id="node-name" provider="pacemaker"
            type="remote"
        >
            <instance_attributes id="node-name-instance_attributes">
                <nvpair
                    id="node-name-instance_attributes-server"
                    name="server" value="remote-candidate"
                />
            </instance_attributes>
            <operations>
                <op id="node-name-migrate_from-interval-0s"
                    interval="0s" name="migrate_from" timeout="60"
                />
                <op id="node-name-migrate_to-interval-0s"
                    interval="0s" name="migrate_to" timeout="60"
                />
                <op id="node-name-monitor-interval-60s"
                    interval="60s" name="monitor" timeout="30"
                />
                <op id="node-name-reload-interval-0s"
                  interval="0s" name="reload" timeout="60"
                />
                <op id="node-name-start-interval-0s"
                    interval="0s" name="start" timeout="60"
                />
                <op id="node-name-stop-interval-0s"
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
        self.env_assist.assert_reports(FIXTURE_REPORTS)

    def test_success_base_host_as_name(self):
        #validation and creation of resource is covered in resource create tests
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, result=True)
            .local.push_existing_authkey_to_remote(REMOTE_HOST)
            .local.run_pacemaker_remote(REMOTE_HOST)
            .env.push_cib(
                resources="""
                    <resources>
                        <primitive class="ocf" id="remote-candidate"
                            provider="pacemaker" type="remote"
                        >
                            <operations>
                                <op id="remote-candidate-migrate_from-interval-0s"
                                    interval="0s" name="migrate_from" timeout="60"
                                />
                                <op id="remote-candidate-migrate_to-interval-0s"
                                    interval="0s" name="migrate_to" timeout="60"
                                />
                                <op id="remote-candidate-monitor-interval-60s"
                                    interval="60s" name="monitor" timeout="30"
                                />
                                <op id="remote-candidate-reload-interval-0s"
                                  interval="0s" name="reload" timeout="60"
                                />
                                <op id="remote-candidate-start-interval-0s"
                                    interval="0s" name="start" timeout="60"
                                />
                                <op id="remote-candidate-stop-interval-0s"
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
            REMOTE_HOST,
            node_name=REMOTE_HOST,
        )
        self.env_assist.assert_reports(FIXTURE_REPORTS)

    def test_node_name_conflict_report_is_unique(self):
        (self.config
            .runner.cib.load(
                resources="""
                    <resources>
                        <primitive class="ocf" id="node-name"
                            provider="pacemaker" type="remote"
                        />
                    </resources>
                """
            )
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .runner.pcmk.load_agent(agent_name="ocf:pacemaker:remote")
        )

        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(
                self.env_assist.get_env(),
                REMOTE_HOST,
                node_name=NODE_NAME,
            ),
            [
                fixture.error(
                    report_codes.ID_ALREADY_EXISTS,
                    id=NODE_NAME,
                )
            ]
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
            FIXTURE_REPORTS
                .adapt(
                    "authkey_distribution_started",
                    node_list=[NODE_1, NODE_2, REMOTE_HOST]
                )
                .copy(
                    "authkey_distribution_success",
                    "authkey_distribution_success_node1",
                    node=NODE_1,
                )
                .copy(
                    "authkey_distribution_success",
                    "authkey_distribution_success_node2",
                    node=NODE_2,
                )
        )

    def test_can_skip_all_offline(self):
        fail_http_kwargs = dict(
            output="",
            was_connected=False,
            errno='6',
            error_msg_template="Could not resolve host",
        )
        pcmk_authkey_content = b"password"
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, **fail_http_kwargs)
            .local.authkey_exists(return_value=True)
            .local.open_authkey(pcmk_authkey_content)
            .local.distribute_authkey(
                communication_list=[dict(label=REMOTE_HOST)],
                pcmk_authkey_content=pcmk_authkey_content,
                **fail_http_kwargs
            )
            .local.run_pacemaker_remote(REMOTE_HOST, **fail_http_kwargs)
            .env.push_cib(resources=FIXTURE_RESOURCES)
        )
        node_add_remote(
            self.env_assist.get_env(),
            REMOTE_HOST,
            node_name=NODE_NAME,
            skip_offline_nodes=True
        )
        self.env_assist.assert_reports(
            FIXTURE_REPORTS
                .remove(
                    "authkey_distribution_success",
                    "pcmk_remote_enable_success",
                    "pcmk_remote_start_success",
                )
                .warn(
                    "check_availability_connection_failed",
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=REMOTE_HOST,
                    command="remote/node_available",
                )
                .copy(
                    "check_availability_connection_failed",
                    "put_file_connection_failed",
                    command="remote/put_file",
                )
                .copy(
                    "check_availability_connection_failed",
                    "manage_services_connection_failed",
                    command="remote/manage_services",
                )
        )

    def test_fails_when_remote_node_is_not_prepared(self):
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, result=False)
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(
                self.env_assist.get_env(),
                REMOTE_HOST,
                node_name=NODE_NAME,
            ),
            [
                fixture.error(
                    report_codes.CANNOT_ADD_NODE_IS_IN_CLUSTER,
                    node=REMOTE_HOST,
                )
            ]
        )

    def test_open_failed(self):
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, result=True)
            .local.authkey_exists(return_value=True)
            .local.open_authkey(fail=True)
        )

        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(
                self.env_assist.get_env(),
                REMOTE_HOST,
                node_name=NODE_NAME,
                allow_incomplete_distribution=True,
            ),
            [
                fixture.error(
                    report_codes.FILE_IO_ERROR,
                    file_role=env_file_role_codes.PACEMAKER_AUTHKEY,
                    file_path=PCMK_AUTHKEY_PATH,
                    operation="read",
                )
            ],
            expected_in_processor=False
        )

    def test_validate_host_already_exists(self):
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
        )
        #more validation tests in pcs/lib/cib/test/test_resource_remote_node.py
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(
                self.env_assist.get_env(),
                NODE_1,
                node_name=NODE_NAME,
                allow_incomplete_distribution=True,
            ),
            [
                fixture.error(
                    report_codes.ID_ALREADY_EXISTS,
                    id=NODE_1
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
            FIXTURE_REPORTS
                .info(
                    "resource_running",
                    report_codes.RESOURCE_RUNNING_ON_NODES,
                    roles_with_nodes={"Started": [NODE_1]},
                    resource_id=NODE_NAME
                )
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
            FIXTURE_REPORTS
        )

class AddRemotePcmkRemoteService(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, result=True)
            .local.push_existing_authkey_to_remote(REMOTE_HOST)
        )

    def test_fails_when_offline(self):
        offline_error_msg = "Could not resolve host"
        (self.config
            .local.run_pacemaker_remote(
                label=REMOTE_HOST,
                output="",
                was_connected=False,
                errno='6',
                error_msg_template=offline_error_msg,
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
            FIXTURE_REPORTS[:"pcmk_remote_enable_success"]
                .error(
                    "manage_services_connection_failed",
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=REMOTE_HOST,
                    reason=offline_error_msg,
                    command="remote/manage_services",
                   force_code=report_codes.SKIP_OFFLINE_NODES
                )
        )

    def test_fail_when_remotely_fail(self):
        (self.config
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
            FIXTURE_REPORTS[:"pcmk_remote_enable_success"]
                .error(
                    "pcmk_remote_enable_failed",
                    report_codes.SERVICE_COMMAND_ON_NODE_ERROR,
                    node=REMOTE_HOST,
                    reason="Operation failed.",
                    service_command_description="pacemaker_remote enable",
                    force_code=report_codes.SKIP_ACTION_ON_NODES_ERRORS,
                )
                .copy(
                    "pcmk_remote_enable_failed",
                    "pcmk_remote_start_failed",
                    service_command_description="pacemaker_remote start",
                )
        )

    def test_forceable_when_remotely_fail(self):
        (self.config
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
            FIXTURE_REPORTS
                .remove(
                    "pcmk_remote_enable_success",
                    "pcmk_remote_start_success",
                )
                .warn(
                    "pcmk_remote_enable_failed",
                    report_codes.SERVICE_COMMAND_ON_NODE_ERROR,
                    node=REMOTE_HOST,
                    reason="Operation failed.",
                    service_command_description="pacemaker_remote enable",
                )
                .copy(
                    "pcmk_remote_enable_failed",
                    "pcmk_remote_start_failed",
                    service_command_description="pacemaker_remote start",
                )
        )

class AddRemoteAuthkeyDistribution(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, result=True)
        )

    def test_fails_when_offline(self):
        offline_error_msg = "Could not resolve host"
        pcmk_authkey_content = b"password"
        (self.config
            .local.authkey_exists(return_value=True)
            .local.open_authkey(pcmk_authkey_content)
            .local.distribute_authkey(
                communication_list=[dict(label=REMOTE_HOST)],
                pcmk_authkey_content=pcmk_authkey_content,
                output="",
                was_connected=False,
                errno='6',
                error_msg_template=offline_error_msg,
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
            FIXTURE_REPORTS[:"authkey_distribution_success"]
                .error(
                    "manage_services_connection_failed",
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=REMOTE_HOST,
                    reason=offline_error_msg,
                    command="remote/put_file",
                   force_code=report_codes.SKIP_OFFLINE_NODES
                )
        )

    def test_fail_when_remotely_fail(self):
        (self.config
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
            FIXTURE_REPORTS[:"authkey_distribution_success"]
                .error(
                    "authkey_distribution_failed",
                    report_codes.FILE_DISTRIBUTION_ERROR,
                    node=REMOTE_HOST,
                    reason="File already exists",
                    file_description="pacemaker_remote authkey",
                    force_code=report_codes.SKIP_FILE_DISTRIBUTION_ERRORS
                )
        )

    def test_forceable_when_remotely_fail(self):
        (self.config
            .local.push_existing_authkey_to_remote(
                REMOTE_HOST,
                distribution_result={
                    "code": "conflict",
                    "message": "",
                }
            )
            .local.run_pacemaker_remote(REMOTE_HOST)
            .env.push_cib(resources=FIXTURE_RESOURCES)
        )

        node_add_remote(
            self.env_assist.get_env(),
            REMOTE_HOST,
            node_name=NODE_NAME,
            allow_incomplete_distribution=True,
        )

        self.env_assist.assert_reports(
            FIXTURE_REPORTS
                .remove("authkey_distribution_success")
                .warn(
                    "authkey_distribution_failed",
                    report_codes.FILE_DISTRIBUTION_ERROR,
                    node=REMOTE_HOST,
                    reason="File already exists",
                )
        )
