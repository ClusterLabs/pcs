from functools import partial

from pcs.common import report_codes, env_file_role_codes
from pcs.lib.commands.remote_node import node_add_remote as node_add_remote_orig
from pcs.lib.commands.test.remote_node.fixtures_add import(
    EnvConfigMixin,
    REPORTS as FIXTURE_REPORTS,
    EXTRA_REPORTS as FIXTURE_EXTRA_REPORTS,
    FAIL_HTTP_KWARGS,
)
from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.pcs_unittest import TestCase, mock


REMOTE_HOST = "remote-host"
NODE_NAME = "node-name"
NODE_1 = "node-1"
NODE_2 = "node-2"

def node_add_remote(
    env, host=None, node_name=None, operations=None, meta_attributes=None,
    instance_attributes=None, **kwargs
):
    operations = operations or []
    meta_attributes = meta_attributes or {}
    instance_attributes = instance_attributes or {}
    host = host or REMOTE_HOST
    node_name = node_name or NODE_NAME

    node_add_remote_orig(
        env, host, node_name, operations, meta_attributes, instance_attributes,
        **kwargs
    )

class LocalConfig(EnvConfigMixin):
    def load_cluster_configs(self, cluster_node_list):
        (self.config
            .runner.cib.load()
            .corosync_conf.load(node_name_list=cluster_node_list)
            .runner.pcmk.load_agent(agent_name="ocf:pacemaker:remote")
        )

get_env_tools = partial(get_env_tools, local_extensions={"local": LocalConfig})

REPORTS = (FIXTURE_REPORTS
    .adapt("authkey_distribution_started", node_list=[REMOTE_HOST])
    .adapt("authkey_distribution_success", node=REMOTE_HOST)
    .adapt("pcmk_remote_start_enable_started", node_list=[REMOTE_HOST])
    .adapt("pcmk_remote_enable_success", node=REMOTE_HOST)
    .adapt("pcmk_remote_start_success", node=REMOTE_HOST)
)
EXTRA_REPORTS = (FIXTURE_EXTRA_REPORTS.adapt_multi(
    [
        "manage_services_connection_failed",
        "manage_services_connection_failed_warn",
        "check_availability_connection_failed",
        "check_availability_connection_failed_warn",
        "put_file_connection_failed",
        "put_file_connection_failed_warn",
        "pcmk_remote_enable_failed",
        "pcmk_remote_enable_failed_warn",
        "pcmk_remote_start_failed",
        "pcmk_remote_start_failed_warn",
        "authkey_distribution_failed",
        "authkey_distribution_failed_warn",
    ],
    node=REMOTE_HOST
))


FIXTURE_RESOURCES = """
    <resources>
        <primitive class="ocf" id="node-name" provider="pacemaker"
            type="remote"
        >
            <instance_attributes id="node-name-instance_attributes">
                <nvpair
                    id="node-name-instance_attributes-server"
                    name="server" value="remote-host"
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
        node_add_remote(self.env_assist.get_env())
        self.env_assist.assert_reports(REPORTS)

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
                        <primitive class="ocf" id="remote-host"
                            provider="pacemaker" type="remote"
                        >
                            <operations>
                                <op id="remote-host-migrate_from-interval-0s"
                                    interval="0s" name="migrate_from" timeout="60"
                                />
                                <op id="remote-host-migrate_to-interval-0s"
                                    interval="0s" name="migrate_to" timeout="60"
                                />
                                <op id="remote-host-monitor-interval-60s"
                                    interval="60s" name="monitor" timeout="30"
                                />
                                <op id="remote-host-reload-interval-0s"
                                  interval="0s" name="reload" timeout="60"
                                />
                                <op id="remote-host-start-interval-0s"
                                    interval="0s" name="start" timeout="60"
                                />
                                <op id="remote-host-stop-interval-0s"
                                    interval="0s" name="stop" timeout="60"
                                />
                            </operations>
                        </primitive>
                    </resources>
                """
            )
        )
        node_add_remote(self.env_assist.get_env(), node_name=REMOTE_HOST)
        self.env_assist.assert_reports(REPORTS)

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
            lambda: node_add_remote(self.env_assist.get_env()),
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
        node_add_remote(self.env_assist.get_env())
        generate_key.assert_called_once_with()
        self.env_assist.assert_reports(
            REPORTS
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
        pcmk_authkey_content = b"password"
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, **FAIL_HTTP_KWARGS)
            .local.authkey_exists(return_value=True)
            .local.open_authkey(pcmk_authkey_content)
            .local.distribute_authkey(
                communication_list=[dict(label=REMOTE_HOST)],
                pcmk_authkey_content=pcmk_authkey_content,
                **FAIL_HTTP_KWARGS
            )
            .local.run_pacemaker_remote(REMOTE_HOST, **FAIL_HTTP_KWARGS)
            .env.push_cib(resources=FIXTURE_RESOURCES)
        )
        node_add_remote(self.env_assist.get_env(), skip_offline_nodes=True)
        self.env_assist.assert_reports(
            REPORTS.select(
                "authkey_distribution_started",
                "pcmk_remote_start_enable_started",
            )
            +
            EXTRA_REPORTS.select(
                "check_availability_connection_failed_warn",
                "put_file_connection_failed_warn",
                "manage_services_connection_failed_warn",
            )
        )

    def test_fails_when_remote_node_is_not_prepared(self):
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, result=False)
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env()),
            [
                fixture.error(
                    report_codes.CANNOT_ADD_NODE_IS_IN_CLUSTER,
                    node=REMOTE_HOST,
                )
            ]
        )

    def test_fails_when_remote_node_returns_invalid_output(self):
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, output="INVALID_OUTPUT")
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env()),
            [
                fixture.error(
                    report_codes.INVALID_RESPONSE_FORMAT,
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
            ),
            [
                fixture.error(
                    report_codes.FILE_IO_ERROR,
                    file_role=env_file_role_codes.PACEMAKER_AUTHKEY,
                    file_path=LocalConfig.PCMK_AUTHKEY_PATH,
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
                host=NODE_1,
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
        node_add_remote(self.env_assist.get_env(), wait=self.wait)
        self.env_assist.assert_reports(
            REPORTS
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
            lambda: node_add_remote(self.env_assist.get_env(), wait=self.wait),
            [
                fixture.error(
                    report_codes.RESOURCE_DOES_NOT_RUN,
                    resource_id=NODE_NAME,
                )
            ]
        )
        self.env_assist.assert_reports(REPORTS)

class AddRemotePcmkRemoteService(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, result=True)
            .local.push_existing_authkey_to_remote(REMOTE_HOST)
        )

    def test_fails_when_offline(self):
        (self.config
            .local.run_pacemaker_remote(label=REMOTE_HOST, **FAIL_HTTP_KWARGS)
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env())
        )

        self.env_assist.assert_reports(
            REPORTS[:"pcmk_remote_enable_success"]
            +
            EXTRA_REPORTS.select("manage_services_connection_failed")
        )

    def test_fail_when_remotely_fail(self):
        (self.config
            .local.run_pacemaker_remote(REMOTE_HOST, result={
                "code": "fail",
                "message": "Action failed",
            })
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            REPORTS[:"pcmk_remote_enable_success"] + EXTRA_REPORTS.select(
                "pcmk_remote_enable_failed",
                "pcmk_remote_start_failed",
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
            allow_pacemaker_remote_service_fail=True
        )

        self.env_assist.assert_reports(
            REPORTS[:"pcmk_remote_enable_success"] + EXTRA_REPORTS.select(
                "pcmk_remote_enable_failed_warn",
                "pcmk_remote_start_failed_warn",
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
        pcmk_authkey_content = b"password"
        (self.config
            .local.authkey_exists(return_value=True)
            .local.open_authkey(pcmk_authkey_content)
            .local.distribute_authkey(
                communication_list=[dict(label=REMOTE_HOST)],
                pcmk_authkey_content=pcmk_authkey_content,
                **FAIL_HTTP_KWARGS
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            REPORTS[:"authkey_distribution_success"]
            +
            EXTRA_REPORTS.only(
                "manage_services_connection_failed",
                command="remote/put_file",
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
            lambda: node_add_remote(self.env_assist.get_env())
        )

        self.env_assist.assert_reports(
            REPORTS[:"authkey_distribution_success"]
            +
            EXTRA_REPORTS.select("authkey_distribution_failed")
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
            allow_incomplete_distribution=True,
        )

        self.env_assist.assert_reports(
            REPORTS.remove("authkey_distribution_success")
            +
            EXTRA_REPORTS.select("authkey_distribution_failed_warn")
        )
