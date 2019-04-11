from functools import partial
from unittest import mock, TestCase

from pcs_test.tier0.lib.commands.remote_node.fixtures_add import(
    EnvConfigMixin,
    REPORTS as FIXTURE_REPORTS,
    EXTRA_REPORTS as FIXTURE_EXTRA_REPORTS,
    FAIL_HTTP_KWARGS,
    fixture_reports_not_live_cib,
    fixture_reports_new_node_unreachable,
)
from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import get_test_resource as rc

from pcs import settings
from pcs.common import report_codes, env_file_role_codes
from pcs.common.host import Destination
from pcs.lib.commands.remote_node import node_add_remote as node_add_remote_orig


NODE_NAME = "node-name"
NODE_ADDR_PCSD = "node-addr"
NODE_DEST_LIST = [Destination(NODE_ADDR_PCSD, 2224)]
NODE_1 = "node-1"
NODE_1_DEST_LIST = [Destination("node-1-addr", 2224)]
NODE_2 = "node-2"
NODE_2_DEST_LIST = [Destination("node-2-addr", 2224)]
KNOWN_HOSTS_DESTS = {
    NODE_NAME: NODE_DEST_LIST,
    NODE_1: NODE_1_DEST_LIST,
    NODE_2: NODE_2_DEST_LIST,
}

def node_add_remote(
    env, node_name=None, node_addr=None, operations=None, meta_attributes=None,
    instance_attributes=None, no_node_addr=False, **kwargs
):
    operations = operations or []
    meta_attributes = meta_attributes or {}
    instance_attributes = instance_attributes or {}
    node_name = node_name or NODE_NAME
    node_addr = node_addr or (None if no_node_addr else "remote-host")

    node_add_remote_orig(
        env, node_name, node_addr, operations, meta_attributes,
        instance_attributes, **kwargs
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
    .adapt("authkey_distribution_started", node_list=[NODE_NAME])
    .adapt("authkey_distribution_success", node=NODE_NAME)
    .adapt("pcmk_remote_start_enable_started", node_list=[NODE_NAME])
    .adapt("pcmk_remote_enable_success", node=NODE_NAME)
    .adapt("pcmk_remote_start_success", node=NODE_NAME)
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
    node=NODE_NAME
))


FIXTURE_RESOURCES_TEMPLATE = """
    <resources>
        <primitive class="ocf" id="node-name" provider="pacemaker"
            type="remote"
        >
            <instance_attributes id="node-name-instance_attributes">
                <nvpair
                    id="node-name-instance_attributes-server"
                    name="server" value="{server}"
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
FIXTURE_RESOURCES = FIXTURE_RESOURCES_TEMPLATE.format(server="remote-host")

class AddRemote(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests(KNOWN_HOSTS_DESTS)

    def _config_success_base(self):
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
            .local.get_host_info(NODE_NAME, NODE_DEST_LIST)
            .local.push_existing_authkey_to_remote(NODE_NAME, NODE_DEST_LIST)
            .local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST)
            .env.push_cib(resources=FIXTURE_RESOURCES)
        )

    def test_success_base(self):
        self._config_success_base()
        node_add_remote(self.env_assist.get_env())
        self.env_assist.assert_reports(REPORTS)

    def test_success_base_addr_same_as_name(self):
        #validation and creation of resource is covered in resource create tests
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
            .local.get_host_info(NODE_NAME, NODE_DEST_LIST)
            .local.push_existing_authkey_to_remote(NODE_NAME, NODE_DEST_LIST)
            .local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST)
            .env.push_cib(
                resources=FIXTURE_RESOURCES_TEMPLATE.format(
                    server=NODE_NAME
                )
            )
        )
        node_add_remote(self.env_assist.get_env(), node_addr=NODE_NAME)
        self.env_assist.assert_reports(REPORTS)

    def test_node_name_conflict_report_is_unique(self):
        (self.config
            .runner.cib.load(
                resources="""
                    <resources>
                        <primitive class="ocf" id="node-name"
                            provider="pacemaker" type="Dummy"
                        />
                    </resources>
                """
            )
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .runner.pcmk.load_agent(agent_name="ocf:pacemaker:remote")
        )

        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env()),
            []
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.ID_ALREADY_EXISTS,
                    id=NODE_NAME,
                )
            ]
        )

    @mock.patch("pcs.lib.commands.remote_node.generate_binary_key")
    def test_success_generated_authkey(self, generate_binary_key):
        generate_binary_key.return_value = b"password"
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
            .local.get_host_info(NODE_NAME, NODE_DEST_LIST)
            .local.authkey_exists(return_value=False)
            .local.distribute_authkey(
                communication_list=[
                    dict(label=NODE_1, dest_list=NODE_1_DEST_LIST),
                    dict(label=NODE_2, dest_list=NODE_2_DEST_LIST),
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST),
                ],
                pcmk_authkey_content=generate_binary_key.return_value,
            )
            .local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST)
            .env.push_cib(resources=FIXTURE_RESOURCES)
        )
        node_add_remote(self.env_assist.get_env())
        generate_binary_key.assert_called_once_with(random_bytes_count=384)
        self.env_assist.assert_reports(
            REPORTS
                .adapt(
                    "authkey_distribution_started",
                    node_list=[NODE_1, NODE_2, NODE_NAME]
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

    def test_new_offline(self):
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(
                        label=NODE_NAME,
                        dest_list=NODE_DEST_LIST,
                        **FAIL_HTTP_KWARGS
                    )
                ],
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env()),
            []
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                force_code=report_codes.SKIP_OFFLINE_NODES,
                node=NODE_NAME,
                command="remote/check_auth",
                reason="Could not resolve host",
            )
        ])

    def test_can_skip_new_offline(self):
        pcmk_authkey_content = b"password"
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(
                        label=NODE_NAME,
                        dest_list=NODE_DEST_LIST,
                        **FAIL_HTTP_KWARGS
                    )
                ],
            )
            .local.authkey_exists(return_value=True)
            .local.open_authkey(pcmk_authkey_content)
            .env.push_cib(resources=FIXTURE_RESOURCES)
        )
        node_add_remote(self.env_assist.get_env(), skip_offline_nodes=True)
        self.env_assist.assert_reports(
            fixture_reports_new_node_unreachable(NODE_NAME, omitting=True)
        )

    @mock.patch("pcs.lib.commands.remote_node.generate_binary_key")
    def test_can_skip_all_offline(self, generate_binary_key):
        generate_binary_key.return_value = b"password"
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(
                        label=NODE_NAME,
                        dest_list=NODE_DEST_LIST,
                        **FAIL_HTTP_KWARGS
                    )
                ],
            )
            .local.authkey_exists(return_value=False)
            .local.distribute_authkey(
                communication_list=[
                    dict(label=NODE_1, dest_list=NODE_1_DEST_LIST),
                    dict(label=NODE_2, dest_list=NODE_2_DEST_LIST),
                ],
                pcmk_authkey_content=generate_binary_key.return_value,
                **FAIL_HTTP_KWARGS
            )
            .env.push_cib(resources=FIXTURE_RESOURCES)
        )
        node_add_remote(self.env_assist.get_env(), skip_offline_nodes=True)
        self.env_assist.assert_reports(
            fixture_reports_new_node_unreachable(NODE_NAME, omitting=True)
            + [
            fixture.info(
                report_codes.FILES_DISTRIBUTION_STARTED,
                file_list=["pacemaker authkey"],
                node_list=[NODE_1, NODE_2],
            ),
            fixture.warn(
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                node=NODE_1,
                command="remote/put_file",
                reason="Could not resolve host",
            ),
            fixture.warn(
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                node=NODE_2,
                command="remote/put_file",
                reason="Could not resolve host",
            ),
        ])

    def test_fails_when_remote_node_is_not_prepared(self):
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
            .local.get_host_info(
                NODE_NAME,
                NODE_DEST_LIST,
                output=dict(
                    services=dict(
                        pacemaker_remote=dict(
                            installed=False, enabled=False, running=False
                        ),
                        pacemaker=dict(
                            installed=True, enabled=False, running=True
                        ),
                        corosync=dict(
                            installed=True, enabled=False, running=True
                        ),
                    ),
                    cluster_configuration_exists=True,
                )
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env()),
            []
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.SERVICE_NOT_INSTALLED,
                node=NODE_NAME,
                service_list=["pacemaker_remote"],
            ),
            fixture.error(
                report_codes.HOST_ALREADY_IN_CLUSTER_SERVICES,
                host_name=NODE_NAME,
                service_list=["corosync", "pacemaker"],
            ),
            fixture.error(
                report_codes.HOST_ALREADY_IN_CLUSTER_CONFIG,
                host_name=NODE_NAME,
            ),
        ])

    def test_fails_when_remote_node_returns_invalid_output(self):
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
            .local.get_host_info(
                NODE_NAME, NODE_DEST_LIST, output="INVALID_OUTPUT"
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env()),
            []
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.INVALID_RESPONSE_FORMAT,
                node=NODE_NAME,
            )
        ])

    def test_open_failed(self):
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
            .local.get_host_info(NODE_NAME, NODE_DEST_LIST)
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

    def test_validate_addr_already_exists(self):
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
        )
        #more validation tests in pcs/lib/cib/test/test_resource_remote_node.py
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(
                self.env_assist.get_env(),
                node_addr=NODE_1,
            ),
            []
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.ID_ALREADY_EXISTS,
                    id=NODE_1
                )
            ]
        )

    def test_unknown_host(self):
        self.config.env.set_known_hosts_dests({
            NODE_1: NODE_1_DEST_LIST,
            NODE_2: NODE_2_DEST_LIST,
        })
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env()),
            []
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.HOST_NOT_FOUND,
                force_code=report_codes.SKIP_OFFLINE_NODES,
                host_list=[NODE_NAME],
            )
        ])

    def test_unknown_host_skip_offline(self):
        pcmk_authkey_content = b"password"
        self.config.env.set_known_hosts_dests({
            NODE_1: NODE_1_DEST_LIST,
            NODE_2: NODE_2_DEST_LIST,
        })
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.authkey_exists(return_value=True)
            .local.open_authkey(pcmk_authkey_content)
            .env.push_cib(resources=FIXTURE_RESOURCES)
        )
        node_add_remote(self.env_assist.get_env(), skip_offline_nodes=True)
        self.env_assist.assert_reports(
            fixture_reports_new_node_unreachable(NODE_NAME)
        )

    @mock.patch("pcs.lib.commands.remote_node.generate_binary_key")
    def test_unknown_host_skip_offline_authkey_distribution(
        self, generate_binary_key
    ):
        generate_binary_key.return_value = b"password"
        self.config.env.set_known_hosts_dests({
            NODE_1: NODE_1_DEST_LIST,
            NODE_2: NODE_2_DEST_LIST,
        })
        (self.config
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .local.authkey_exists(return_value=False)
            .local.distribute_authkey(
                communication_list=[
                    dict(label=NODE_1, dest_list=NODE_1_DEST_LIST),
                    dict(label=NODE_2, dest_list=NODE_2_DEST_LIST),
                ],
                pcmk_authkey_content=generate_binary_key.return_value,
            )
            .env.push_cib(resources=FIXTURE_RESOURCES)
        )
        node_add_remote(self.env_assist.get_env(), skip_offline_nodes=True)
        generate_binary_key.assert_called_once_with(random_bytes_count=384)
        self.env_assist.assert_reports(
            fixture_reports_new_node_unreachable(NODE_NAME)
            + [
            fixture.info(
                report_codes.FILES_DISTRIBUTION_STARTED,
                file_list=["pacemaker authkey"],
                node_list=[NODE_1, NODE_2],
            ),
            fixture.info(
                report_codes.FILE_DISTRIBUTION_SUCCESS,
                file_description="pacemaker authkey",
                node=NODE_1,
            ),
            fixture.info(
                report_codes.FILE_DISTRIBUTION_SUCCESS,
                file_description="pacemaker authkey",
                node=NODE_2,
            ),
        ])

    def test_some_node_names_missing(self):
        self._config_success_base()
        (self.config
            .env.set_known_hosts_dests({
                "rh7-1": [Destination("rh7-1", 2224)],
                "rh7-2": [Destination("rh7-2", 2224)],
                NODE_NAME: NODE_DEST_LIST,
            })
            .corosync_conf.load(
                filename="corosync-some-node-names.conf",
                instead="corosync_conf.load"
            )
        )

        node_add_remote(self.env_assist.get_env())
        self.env_assist.assert_reports(
            REPORTS.warn(
                "missing_node_names_in_corosync",
                report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                fatal=False
            )
        )

    def test_all_node_names_missing(self):
        self._config_success_base()
        self.config.corosync_conf.load(
            filename="corosync-no-node-names.conf",
            instead="corosync_conf.load"
        )
        node_add_remote(self.env_assist.get_env())
        self.env_assist.assert_reports(
            REPORTS.warn(
                "missing_node_names_in_corosync",
                report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                fatal=False
            )
        )


class NotLive(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests(KNOWN_HOSTS_DESTS)
        self.config.env.set_cib_data(open(rc("cib-empty.xml")).read())

    def test_addr_specified(self):
        (self.config
            .runner.cib.load()
            .runner.pcmk.load_agent(agent_name="ocf:pacemaker:remote")
            .env.push_cib(resources=FIXTURE_RESOURCES)
        )
        node_add_remote(self.env_assist.get_env())
        self.env_assist.assert_reports(fixture_reports_not_live_cib(NODE_NAME))

    def test_addr_not_specified(self):
        (self.config
            .runner.cib.load()
            .runner.pcmk.load_agent(agent_name="ocf:pacemaker:remote")
            .env.push_cib(
                resources=FIXTURE_RESOURCES_TEMPLATE.format(
                    server=NODE_ADDR_PCSD
                )
            )
        )
        node_add_remote(self.env_assist.get_env(), no_node_addr=True)
        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST,
                    host_name=NODE_NAME,
                    address=NODE_ADDR_PCSD,
                ),
            ]
            +
            fixture_reports_not_live_cib(NODE_NAME)
        )

    def test_unknown_host_addr_not_specified(self):
        self.config.env.set_known_hosts_dests(dict())
        (self.config
            .runner.cib.load()
            .runner.pcmk.load_agent(agent_name="ocf:pacemaker:remote")
            .env.push_cib(
                resources=FIXTURE_RESOURCES_TEMPLATE.format(
                    server=NODE_NAME
                )
            )
        )
        node_add_remote(self.env_assist.get_env(), no_node_addr=True)
        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST,
                    host_name=NODE_NAME,
                    address=NODE_NAME,
                ),
            ]
            +
            fixture_reports_not_live_cib(NODE_NAME)
        )

    def test_unknown_host_addr_specified(self):
        self.config.env.set_known_hosts_dests(dict())
        (self.config
            .runner.cib.load()
            .runner.pcmk.load_agent(agent_name="ocf:pacemaker:remote")
            .env.push_cib(
                resources=FIXTURE_RESOURCES_TEMPLATE.format(
                    server="addr"
                )
            )
        )
        node_add_remote(self.env_assist.get_env(), node_addr="addr")
        self.env_assist.assert_reports(fixture_reports_not_live_cib(NODE_NAME))

    def test_wait(self):
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env(), wait=1),
            [
                fixture.error(
                    report_codes.WAIT_FOR_IDLE_NOT_LIVE_CLUSTER,
                ),
            ],
            expected_in_processor=False
        )


class WithWait(TestCase):
    def setUp(self):
        self. wait = 1
        self.env_assist, self.config = get_env_tools(self)
        (self.config
            .env.set_known_hosts_dests(KNOWN_HOSTS_DESTS)
            .runner.pcmk.can_wait()
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
            .local.get_host_info(NODE_NAME, NODE_DEST_LIST)
            .local.push_existing_authkey_to_remote(NODE_NAME, NODE_DEST_LIST)
            .local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST)
            .env.push_cib(resources=FIXTURE_RESOURCES, wait=self.wait)
         )

    def test_success_when_resource_started(self):
        (self.config
            .runner.pcmk.load_state(raw_resources=dict(
                resource_id=NODE_NAME,
                resource_agent="ocf::pacemaker:remote",
                node_name=NODE_1,
            ))
            # self.config.fs is used to mock authkey file existence. Therefore,
            # filesystem mocking is active and we need to cover it. We tell the
            # file doesn't exist, because we aren't currently mocking the
            # function which reads it:
            #   if os.path.isfile(settings.crm_mon_schema):
            #       etree.RelaxNG(file=settings.crm_mon_schema).assertValid(dom)
            .fs.isfile(settings.crm_mon_schema, return_value=False)
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
            # self.config.fs is used to mock authkey file existence. Therefore,
            # filesystem mocking is active and we need to cover it. We tell the
            # file doesn't exist, because we aren't currently mocking the
            # function which reads it:
            #   if os.path.isfile(settings.crm_mon_schema):
            #       etree.RelaxNG(file=settings.crm_mon_schema).assertValid(dom)
            .fs.isfile(settings.crm_mon_schema, return_value=False)
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
            .env.set_known_hosts_dests(KNOWN_HOSTS_DESTS)
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
            .local.get_host_info(NODE_NAME, NODE_DEST_LIST)
            .local.push_existing_authkey_to_remote(NODE_NAME, NODE_DEST_LIST)
        )

    def test_fails_when_offline(self):
        (self.config
            .local.run_pacemaker_remote(
                NODE_NAME, NODE_DEST_LIST, **FAIL_HTTP_KWARGS
            )
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
            .local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST, result={
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
            .local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST, result={
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
            .env.set_known_hosts_dests(KNOWN_HOSTS_DESTS)
            .local.load_cluster_configs(cluster_node_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
            .local.get_host_info(NODE_NAME, NODE_DEST_LIST)
        )

    def test_fails_when_offline(self):
        pcmk_authkey_content = b"password"
        (self.config
            .local.authkey_exists(return_value=True)
            .local.open_authkey(pcmk_authkey_content)
            .local.distribute_authkey(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
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
                NODE_NAME,
                NODE_DEST_LIST,
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
                NODE_NAME,
                NODE_DEST_LIST,
                distribution_result={
                    "code": "conflict",
                    "message": "",
                }
            )
            .local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST)
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
