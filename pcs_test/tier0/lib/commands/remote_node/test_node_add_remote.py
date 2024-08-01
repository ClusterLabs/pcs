from functools import partial
from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.file import RawFileError
from pcs.common.host import Destination
from pcs.lib.commands.remote_node import node_add_remote as node_add_remote_orig

from pcs_test.tier0.lib.commands.remote_node.fixtures_add import (
    FAIL_HTTP_KWARGS,
    EnvConfigMixin,
    base_reports_for_host,
    fixture_reports_new_node_unreachable,
    fixture_reports_not_live_cib,
    report_authkey_distribution_failed,
    report_manage_services_connection_failed,
    report_pcmk_remote_enable_failed,
    report_pcmk_remote_start_failed,
    report_put_file_connection_failed,
)
from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import get_test_resource as rc

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
    env,
    node_name=None,
    node_addr=None,
    operations=None,
    meta_attributes=None,
    instance_attributes=None,
    no_node_addr=False,
    **kwargs,
):
    operations = operations or []
    meta_attributes = meta_attributes or {}
    instance_attributes = instance_attributes or {}
    node_name = node_name or NODE_NAME
    node_addr = node_addr or (None if no_node_addr else "remote-host")

    node_add_remote_orig(
        env,
        node_name,
        node_addr,
        operations,
        meta_attributes,
        instance_attributes,
        **kwargs,
    )


class LocalConfig(EnvConfigMixin):
    def load_cluster_configs(self, cluster_node_list):
        self.config.runner.cib.load()
        self.config.corosync_conf.load(node_name_list=cluster_node_list)
        self.config.runner.pcmk.load_agent(agent_name="ocf:pacemaker:remote")


get_env_tools = partial(get_env_tools, local_extensions={"local": LocalConfig})

REPORTS = base_reports_for_host(NODE_NAME)


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
                    interval="0s" name="migrate_from" timeout="60s"
                />
                <op id="node-name-migrate_to-interval-0s"
                    interval="0s" name="migrate_to" timeout="60s"
                />
                <op id="node-name-monitor-interval-60s"
                    interval="60s" name="monitor" timeout="30s" {onfail}
                />
                <op id="node-name-reload-interval-0s"
                  interval="0s" name="reload" timeout="60s"
                />
                <op id="node-name-reload-agent-interval-0s" interval="0s"
                    name="reload-agent" timeout="60s"
                />
                <op id="node-name-start-interval-0s"
                    interval="0s" name="start" timeout="60s"
                />
                <op id="node-name-stop-interval-0s"
                    interval="0s" name="stop" timeout="60s"
                />
            </operations>
        </primitive>
    </resources>
"""
FIXTURE_RESOURCES = FIXTURE_RESOURCES_TEMPLATE.format(
    server="remote-host", onfail=""
)


class AddRemote(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests(KNOWN_HOSTS_DESTS)

    def _config_success_base(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        self.config.http.host.check_auth(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
        )
        self.config.local.get_host_info(NODE_NAME, NODE_DEST_LIST)
        self.config.local.push_existing_authkey_to_remote(
            NODE_NAME, NODE_DEST_LIST
        )
        self.config.local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST)
        self.config.env.push_cib(resources=FIXTURE_RESOURCES)

    def test_success_base(self):
        self._config_success_base()
        node_add_remote(self.env_assist.get_env())
        self.env_assist.assert_reports(REPORTS)

    def test_success_base_addr_same_as_name(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member

        # validation and creation of resource is covered in resource create
        # tests
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        self.config.http.host.check_auth(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
        )
        self.config.local.get_host_info(NODE_NAME, NODE_DEST_LIST)
        self.config.local.push_existing_authkey_to_remote(
            NODE_NAME, NODE_DEST_LIST
        )
        self.config.local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST)
        self.config.env.push_cib(
            resources=FIXTURE_RESOURCES_TEMPLATE.format(
                server=NODE_NAME, onfail=""
            )
        )
        node_add_remote(self.env_assist.get_env(), node_addr=NODE_NAME)
        self.env_assist.assert_reports(REPORTS)

    def test_cib_upgrade_on_onfail_demote(self):
        self._config_success_base()
        self.config.runner.cib.load(
            filename="cib-empty-3.4.xml",
            instead="runner.cib.load",
        )
        self.config.runner.cib.upgrade(before="runner.cib.load")
        self.config.runner.cib.load(
            filename="cib-empty-3.3.xml",
            name="load_cib_old_version",
            before="runner.cib.upgrade",
        )
        self.config.env.push_cib(
            resources=FIXTURE_RESOURCES_TEMPLATE.format(
                server="remote-host", onfail='on-fail="demote"'
            ),
            instead="env.push_cib",
        )
        node_add_remote(
            self.env_assist.get_env(),
            operations=[
                {
                    "name": "monitor",
                    "timeout": "30s",
                    "interval": "60s",
                    "on-fail": "demote",
                }
            ],
        )
        self.env_assist.assert_reports(
            fixture.ReportSequenceBuilder(REPORTS.copy()).info(
                reports.codes.CIB_UPGRADE_SUCCESSFUL
            )
        )

    def test_node_name_conflict_report_is_unique(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive class="ocf" id="node-name"
                        provider="pacemaker" type="Dummy"
                    />
                </resources>
            """
        )
        self.config.corosync_conf.load(node_name_list=[NODE_1, NODE_2])
        self.config.runner.pcmk.load_agent(agent_name="ocf:pacemaker:remote")

        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env()), []
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ID_ALREADY_EXISTS,
                    id=NODE_NAME,
                )
            ]
        )

    @mock.patch("pcs.lib.commands.remote_node.generate_binary_key")
    def test_success_generated_authkey(self, generate_binary_key):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        generate_binary_key.return_value = b"password"
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        self.config.http.host.check_auth(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
        )
        self.config.local.get_host_info(NODE_NAME, NODE_DEST_LIST)
        self.config.local.authkey_exists(return_value=False)
        self.config.local.distribute_authkey(
            communication_list=[
                dict(label=NODE_1, dest_list=NODE_1_DEST_LIST),
                dict(label=NODE_2, dest_list=NODE_2_DEST_LIST),
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST),
            ],
            pcmk_authkey_content=generate_binary_key.return_value,
        )
        self.config.local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST)
        self.config.env.push_cib(resources=FIXTURE_RESOURCES)

        node_add_remote(self.env_assist.get_env())
        generate_binary_key.assert_called_once_with(random_bytes_count=256)
        my_reports = REPORTS.copy()
        my_reports.replace(
            "authkey_distribution_started",
            REPORTS["authkey_distribution_started"].adapt(
                node_list=[NODE_1, NODE_2, NODE_NAME],
            ),
        )
        my_reports.append(
            REPORTS["authkey_distribution_success"].adapt(node=NODE_1),
        )
        my_reports.append(
            REPORTS["authkey_distribution_success"].adapt(node=NODE_2),
        )
        self.env_assist.assert_reports(my_reports)

    def test_new_offline(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        self.config.http.host.check_auth(
            communication_list=[
                dict(
                    label=NODE_NAME,
                    dest_list=NODE_DEST_LIST,
                    **FAIL_HTTP_KWARGS,
                )
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env()), []
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                    node=NODE_NAME,
                    command="remote/check_auth",
                    reason="Could not resolve host",
                )
            ]
        )

    def test_can_skip_new_offline(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        pcmk_authkey_content = b"password"
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        self.config.http.host.check_auth(
            communication_list=[
                dict(
                    label=NODE_NAME,
                    dest_list=NODE_DEST_LIST,
                    **FAIL_HTTP_KWARGS,
                )
            ],
        )
        self.config.local.authkey_exists(return_value=True)
        self.config.local.open_authkey(pcmk_authkey_content)
        self.config.env.push_cib(resources=FIXTURE_RESOURCES)

        node_add_remote(self.env_assist.get_env(), skip_offline_nodes=True)
        self.env_assist.assert_reports(
            fixture_reports_new_node_unreachable(NODE_NAME, omitting=True)
        )

    @mock.patch("pcs.lib.commands.remote_node.generate_binary_key")
    def test_can_skip_all_offline(self, generate_binary_key):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        generate_binary_key.return_value = b"password"
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        self.config.http.host.check_auth(
            communication_list=[
                dict(
                    label=NODE_NAME,
                    dest_list=NODE_DEST_LIST,
                    **FAIL_HTTP_KWARGS,
                )
            ],
        )
        self.config.local.authkey_exists(return_value=False)
        self.config.local.distribute_authkey(
            communication_list=[
                dict(label=NODE_1, dest_list=NODE_1_DEST_LIST),
                dict(label=NODE_2, dest_list=NODE_2_DEST_LIST),
            ],
            pcmk_authkey_content=generate_binary_key.return_value,
            **FAIL_HTTP_KWARGS,
        )
        self.config.env.push_cib(resources=FIXTURE_RESOURCES)

        node_add_remote(self.env_assist.get_env(), skip_offline_nodes=True)
        self.env_assist.assert_reports(
            fixture_reports_new_node_unreachable(NODE_NAME, omitting=True)
            + [
                fixture.info(
                    reports.codes.FILES_DISTRIBUTION_STARTED,
                    file_list=["pacemaker authkey"],
                    node_list=[NODE_1, NODE_2],
                ),
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=NODE_1,
                    command="remote/put_file",
                    reason="Could not resolve host",
                ),
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=NODE_2,
                    command="remote/put_file",
                    reason="Could not resolve host",
                ),
            ]
        )

    def test_fails_when_remote_node_is_not_prepared(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        self.config.http.host.check_auth(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
        )
        self.config.local.get_host_info(
            NODE_NAME,
            NODE_DEST_LIST,
            output=dict(
                services=dict(
                    pacemaker_remote=dict(
                        installed=False, enabled=False, running=False
                    ),
                    pacemaker=dict(installed=True, enabled=False, running=True),
                    corosync=dict(installed=True, enabled=False, running=True),
                ),
                cluster_configuration_exists=True,
            ),
        )

        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env()), []
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.SERVICE_NOT_INSTALLED,
                    node=NODE_NAME,
                    service_list=["pacemaker_remote"],
                ),
                fixture.error(
                    reports.codes.HOST_ALREADY_IN_CLUSTER_SERVICES,
                    host_name=NODE_NAME,
                    service_list=["corosync", "pacemaker"],
                ),
                fixture.error(
                    reports.codes.HOST_ALREADY_IN_CLUSTER_CONFIG,
                    host_name=NODE_NAME,
                ),
            ]
        )

    def test_fails_when_remote_node_returns_invalid_output(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        self.config.http.host.check_auth(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
        )
        self.config.local.get_host_info(
            NODE_NAME, NODE_DEST_LIST, output="INVALID_OUTPUT"
        )

        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env()), []
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_RESPONSE_FORMAT,
                    node=NODE_NAME,
                )
            ]
        )

    def test_open_failed(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        self.config.http.host.check_auth(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
        )
        self.config.local.get_host_info(NODE_NAME, NODE_DEST_LIST)
        self.config.local.authkey_exists(return_value=True)
        self.config.local.open_authkey(fail=True)

        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(
                self.env_assist.get_env(),
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PACEMAKER_AUTHKEY,
                    file_path=settings.pacemaker_authkey_file,
                    operation=RawFileError.ACTION_READ,
                    reason="open failed",
                )
            ],
        )

    def test_validate_addr_already_exists(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        # more validation tests in pcs/lib/cib/test/test_resource_remote_node.py
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(
                self.env_assist.get_env(),
                node_addr=NODE_1,
            ),
            [],
        )
        self.env_assist.assert_reports(
            [fixture.error(reports.codes.ID_ALREADY_EXISTS, id=NODE_1)]
        )

    def test_unknown_host(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.env.set_known_hosts_dests(
            {
                NODE_1: NODE_1_DEST_LIST,
                NODE_2: NODE_2_DEST_LIST,
            }
        )
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env()), []
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND,
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                    host_list=[NODE_NAME],
                )
            ]
        )

    def test_unknown_host_skip_offline(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        pcmk_authkey_content = b"password"
        self.config.env.set_known_hosts_dests(
            {
                NODE_1: NODE_1_DEST_LIST,
                NODE_2: NODE_2_DEST_LIST,
            }
        )
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        self.config.local.authkey_exists(return_value=True)
        self.config.local.open_authkey(pcmk_authkey_content)
        self.config.env.push_cib(resources=FIXTURE_RESOURCES)

        node_add_remote(self.env_assist.get_env(), skip_offline_nodes=True)
        self.env_assist.assert_reports(
            fixture_reports_new_node_unreachable(NODE_NAME)
        )

    @mock.patch("pcs.lib.commands.remote_node.generate_binary_key")
    def test_unknown_host_skip_offline_authkey_distribution(
        self, generate_binary_key
    ):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        generate_binary_key.return_value = b"password"
        self.config.env.set_known_hosts_dests(
            {
                NODE_1: NODE_1_DEST_LIST,
                NODE_2: NODE_2_DEST_LIST,
            }
        )
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        self.config.local.authkey_exists(return_value=False)
        self.config.local.distribute_authkey(
            communication_list=[
                dict(label=NODE_1, dest_list=NODE_1_DEST_LIST),
                dict(label=NODE_2, dest_list=NODE_2_DEST_LIST),
            ],
            pcmk_authkey_content=generate_binary_key.return_value,
        )
        self.config.env.push_cib(resources=FIXTURE_RESOURCES)

        node_add_remote(self.env_assist.get_env(), skip_offline_nodes=True)
        generate_binary_key.assert_called_once_with(random_bytes_count=256)
        self.env_assist.assert_reports(
            fixture_reports_new_node_unreachable(NODE_NAME)
            + [
                fixture.info(
                    reports.codes.FILES_DISTRIBUTION_STARTED,
                    file_list=["pacemaker authkey"],
                    node_list=[NODE_1, NODE_2],
                ),
                fixture.info(
                    reports.codes.FILE_DISTRIBUTION_SUCCESS,
                    file_description="pacemaker authkey",
                    node=NODE_1,
                ),
                fixture.info(
                    reports.codes.FILE_DISTRIBUTION_SUCCESS,
                    file_description="pacemaker authkey",
                    node=NODE_2,
                ),
            ]
        )

    def test_some_node_names_missing(self):
        self._config_success_base()
        self.config.env.set_known_hosts_dests(
            {
                "rh7-1": [Destination("rh7-1", 2224)],
                "rh7-2": [Destination("rh7-2", 2224)],
                NODE_NAME: NODE_DEST_LIST,
            }
        )
        self.config.corosync_conf.load(
            filename="corosync-some-node-names.conf",
            instead="corosync_conf.load",
        )

        node_add_remote(self.env_assist.get_env())
        self.env_assist.assert_reports(
            fixture.ReportSequenceBuilder(REPORTS.copy()).warn(
                reports.codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                fatal=False,
            )
        )

    def test_all_node_names_missing(self):
        self._config_success_base()
        self.config.corosync_conf.load(
            filename="corosync-no-node-names.conf", instead="corosync_conf.load"
        )
        node_add_remote(self.env_assist.get_env())
        self.env_assist.assert_reports(
            fixture.ReportSequenceBuilder(REPORTS.copy()).warn(
                reports.codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                fatal=False,
            )
        )


class NotLive(TestCase):
    # pylint: disable=no-member
    def setUp(self):
        self.tmp_file = "/fake/tmp_file"
        self.cmd_env = dict(CIB_file=self.tmp_file)
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests(KNOWN_HOSTS_DESTS)
        with open(rc("cib-empty.xml")) as cib_file:
            self.config.env.set_cib_data(
                cib_file.read(), cib_tempfile=self.tmp_file
            )

    def test_addr_specified(self):
        self.config.runner.cib.load(env=self.cmd_env)
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:remote", env=self.cmd_env
        )
        self.config.env.push_cib(resources=FIXTURE_RESOURCES)
        node_add_remote(self.env_assist.get_env())
        self.env_assist.assert_reports(fixture_reports_not_live_cib(NODE_NAME))

    def test_addr_not_specified(self):
        self.config.runner.cib.load(env=self.cmd_env)
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:remote", env=self.cmd_env
        )
        self.config.env.push_cib(
            resources=FIXTURE_RESOURCES_TEMPLATE.format(
                server=NODE_ADDR_PCSD, onfail=""
            )
        )
        node_add_remote(self.env_assist.get_env(), no_node_addr=True)
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=NODE_NAME,
                    address=NODE_ADDR_PCSD,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                ),
            ]
            + fixture_reports_not_live_cib(NODE_NAME)
        )

    def test_unknown_host_addr_not_specified(self):
        self.config.env.set_known_hosts_dests({})
        self.config.runner.cib.load(env=self.cmd_env)
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:remote", env=self.cmd_env
        )
        self.config.env.push_cib(
            resources=FIXTURE_RESOURCES_TEMPLATE.format(
                server=NODE_NAME, onfail=""
            ),
        )
        node_add_remote(self.env_assist.get_env(), no_node_addr=True)
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=NODE_NAME,
                    address=NODE_NAME,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_HOST_NAME
                    ),
                ),
            ]
            + fixture_reports_not_live_cib(NODE_NAME)
        )

    def test_unknown_host_addr_specified(self):
        self.config.env.set_known_hosts_dests({})
        server_value = "addr"
        self.config.runner.cib.load(env=self.cmd_env)
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:pacemaker:remote", env=self.cmd_env
        )
        self.config.env.push_cib(
            resources=FIXTURE_RESOURCES_TEMPLATE.format(
                server=server_value, onfail=""
            )
        )
        node_add_remote(self.env_assist.get_env(), node_addr=server_value)
        self.env_assist.assert_reports(fixture_reports_not_live_cib(NODE_NAME))

    def test_wait(self):
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env(), wait=1),
            [fixture.error(reports.codes.WAIT_FOR_IDLE_NOT_LIVE_CLUSTER)],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(
            [fixture.deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED)]
        )


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class WithWait(TestCase):
    def setUp(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.wait = 1
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests(KNOWN_HOSTS_DESTS)
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        self.config.http.host.check_auth(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
        )
        self.config.local.get_host_info(NODE_NAME, NODE_DEST_LIST)
        self.config.local.push_existing_authkey_to_remote(
            NODE_NAME, NODE_DEST_LIST
        )
        self.config.local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST)
        self.config.env.push_cib(resources=FIXTURE_RESOURCES, wait=self.wait)

    def test_success_when_resource_started(self):
        self.config.runner.pcmk.load_state(
            resources=f"""
                <resources>
                    <resource
                        id="{NODE_NAME}"
                        resource_agent="ocf::pacemaker:remote"
                    >
                        <node name="{NODE_1}" id="1" cached="false"/>
                    </resource>
                </resources>
            """
        )
        node_add_remote(self.env_assist.get_env(), wait=self.wait)
        self.env_assist.assert_reports(
            fixture.ReportSequenceBuilder(REPORTS.copy())
            .info(
                reports.codes.RESOURCE_RUNNING_ON_NODES,
                roles_with_nodes={"Started": [NODE_1]},
                resource_id=NODE_NAME,
            )
            .deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED)
        )

    def test_fail_when_resource_not_started(self):
        self.config.runner.pcmk.load_state(
            resources=f"""
                <resources>
                    <resource
                        id="{NODE_NAME}"
                        resource_agent="ocf::pacemaker:remote"
                        failed="true"
                    >
                        <node name="{NODE_1}" id="1" cached="false"/>
                    </resource>
                </resources>
            """
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env(), wait=self.wait)
        )
        self.env_assist.assert_reports(
            fixture.ReportSequenceBuilder(REPORTS.copy())
            .error(
                reports.codes.RESOURCE_DOES_NOT_RUN,
                resource_id=NODE_NAME,
            )
            .deprecation(reports.codes.RESOURCE_WAIT_DEPRECATED)
        )


class AddRemotePcmkRemoteService(TestCase):
    def setUp(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests(KNOWN_HOSTS_DESTS)
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        self.config.http.host.check_auth(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
        )
        self.config.local.get_host_info(NODE_NAME, NODE_DEST_LIST)
        self.config.local.push_existing_authkey_to_remote(
            NODE_NAME, NODE_DEST_LIST
        )

    def test_fails_when_offline(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.run_pacemaker_remote(
            NODE_NAME, NODE_DEST_LIST, **FAIL_HTTP_KWARGS
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env())
        )

        my_reports = REPORTS[:"pcmk_remote_enable_success"]
        my_reports.append(report_manage_services_connection_failed(NODE_NAME))
        self.env_assist.assert_reports(my_reports)

    def test_fail_when_remotely_fail(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.run_pacemaker_remote(
            NODE_NAME,
            NODE_DEST_LIST,
            result={
                "code": "fail",
                "message": "Action failed",
            },
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env())
        )
        my_reports = REPORTS[:"pcmk_remote_enable_success"]
        my_reports.append(report_pcmk_remote_enable_failed(NODE_NAME))
        my_reports.append(report_pcmk_remote_start_failed(NODE_NAME))
        self.env_assist.assert_reports(my_reports)

    def test_forceable_when_remotely_fail(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.run_pacemaker_remote(
            NODE_NAME,
            NODE_DEST_LIST,
            result={
                "code": "fail",
                "message": "Action failed",
            },
        ).env.push_cib(resources=FIXTURE_RESOURCES)
        node_add_remote(
            self.env_assist.get_env(), allow_pacemaker_remote_service_fail=True
        )

        my_reports = REPORTS[:"pcmk_remote_enable_success"]
        my_reports.append(report_pcmk_remote_enable_failed(NODE_NAME).to_warn())
        my_reports.append(report_pcmk_remote_start_failed(NODE_NAME).to_warn())
        self.env_assist.assert_reports(my_reports)


class AddRemoteAuthkeyDistribution(TestCase):
    def setUp(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests(KNOWN_HOSTS_DESTS)
        self.config.local.load_cluster_configs(
            cluster_node_list=[NODE_1, NODE_2]
        )
        self.config.http.host.check_auth(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
        )
        self.config.local.get_host_info(NODE_NAME, NODE_DEST_LIST)

    def test_fails_when_offline(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        pcmk_authkey_content = b"password"
        self.config.local.authkey_exists(return_value=True)
        self.config.local.open_authkey(pcmk_authkey_content)
        self.config.local.distribute_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
            pcmk_authkey_content=pcmk_authkey_content,
            **FAIL_HTTP_KWARGS,
        )

        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env())
        )
        my_reports = REPORTS[:"authkey_distribution_success"]
        my_reports.append(report_put_file_connection_failed(NODE_NAME))
        self.env_assist.assert_reports(my_reports)

    def test_fail_when_remotely_fail(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.push_existing_authkey_to_remote(
            NODE_NAME,
            NODE_DEST_LIST,
            distribution_result={
                "code": "conflict",
                "message": "",
            },
        )

        self.env_assist.assert_raise_library_error(
            lambda: node_add_remote(self.env_assist.get_env())
        )

        my_reports = REPORTS[:"authkey_distribution_success"]
        my_reports.append(report_authkey_distribution_failed(NODE_NAME))
        self.env_assist.assert_reports(my_reports)

    def test_forceable_when_remotely_fail(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.push_existing_authkey_to_remote(
            NODE_NAME,
            NODE_DEST_LIST,
            distribution_result={
                "code": "conflict",
                "message": "",
            },
        )
        self.config.local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST)
        self.config.env.push_cib(resources=FIXTURE_RESOURCES)

        node_add_remote(
            self.env_assist.get_env(),
            allow_incomplete_distribution=True,
        )

        my_reports = REPORTS.copy()
        my_reports.replace(
            "authkey_distribution_success",
            report_authkey_distribution_failed(NODE_NAME).to_warn(),
        )
        self.env_assist.assert_reports(my_reports)
