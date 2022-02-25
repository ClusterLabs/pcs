from functools import partial
from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common import reports
from pcs.common.host import Destination
from pcs.lib.commands.remote_node import node_add_guest as node_add_guest_orig

from pcs_test.tier0.lib.commands.remote_node.fixtures_add import (
    EXTRA_REPORTS as FIXTURE_EXTRA_REPORTS,
)
from pcs_test.tier0.lib.commands.remote_node.fixtures_add import (
    FAIL_HTTP_KWARGS,
)
from pcs_test.tier0.lib.commands.remote_node.fixtures_add import (
    REPORTS as FIXTURE_REPORTS,
)
from pcs_test.tier0.lib.commands.remote_node.fixtures_add import (
    EnvConfigMixin,
    fixture_reports_new_node_unreachable,
    fixture_reports_not_live_cib,
)
from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.xml import XmlManipulation

NODE_NAME = "node-name"
NODE_ADDR_PCSD = "node-addr"
NODE_DEST_LIST = [Destination(NODE_ADDR_PCSD, 2224)]
REMOTE_HOST = "remote-host"
VIRTUAL_MACHINE_ID = "virtual_machine_id"
NODE_1 = "node-1"
NODE_1_DEST_LIST = [Destination("node-1-addr", 2224)]
NODE_2 = "node-2"
NODE_2_DEST_LIST = [Destination("node-2-addr", 2224)]
KNOWN_HOSTS_DESTS = {
    NODE_NAME: NODE_DEST_LIST,
    NODE_1: NODE_1_DEST_LIST,
    NODE_2: NODE_2_DEST_LIST,
}


def node_add_guest(
    env,
    node_name=NODE_NAME,
    resource_id=VIRTUAL_MACHINE_ID,
    options=None,
    **kwargs,
):
    options = options or {"remote-addr": REMOTE_HOST}
    node_add_guest_orig(env, node_name, resource_id, options, **kwargs)


FIXTURE_RESOURCES = """
    <resources>
        <primitive class="ocf" id="{0}"
            provider="heartbeat" type="VirtualDomain"
        />
    </resources>
""".format(
    VIRTUAL_MACHINE_ID
)

FIXTURE_META_ATTRIBUTES = """
    <meta_attributes id="virtual_machine_id-meta_attributes">
        <nvpair id="virtual_machine_id-meta_attributes-remote-addr"
            name="remote-addr" value="remote-host"
        />
        <nvpair id="virtual_machine_id-meta_attributes-remote-node"
            name="remote-node" value="node-name"
        />
     </meta_attributes>
"""


class LocalConfig(EnvConfigMixin):
    def load_cib(self, env=None):
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES, env=env)

    def push_cib(self, wait=-1, meta_attributes=FIXTURE_META_ATTRIBUTES):
        self.config.env.push_cib(
            append={
                './/resources/primitive[@id="{0}"]'.format(
                    VIRTUAL_MACHINE_ID
                ): meta_attributes,
            },
            wait=wait,
        )


get_env_tools = partial(get_env_tools, local_extensions={"local": LocalConfig})


def base_reports_for_host(host=NODE_NAME):
    return (
        FIXTURE_REPORTS.adapt("authkey_distribution_started", node_list=[host])
        .adapt("authkey_distribution_success", node=host)
        .adapt("pcmk_remote_start_enable_started", node_list=[host])
        .adapt("pcmk_remote_enable_success", node=host)
        .adapt("pcmk_remote_start_success", node=host)
    )


REPORTS = base_reports_for_host()

EXTRA_REPORTS = FIXTURE_EXTRA_REPORTS.adapt_multi(
    [
        "manage_services_connection_failed",
        "manage_services_connection_failed_warn",
        "put_file_connection_failed",
        "put_file_connection_failed_warn",
        "pcmk_remote_enable_failed",
        "pcmk_remote_enable_failed_warn",
        "pcmk_remote_start_failed",
        "pcmk_remote_start_failed_warn",
        "authkey_distribution_failed",
        "authkey_distribution_failed_warn",
    ],
    node=NODE_NAME,
)


class AddGuest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests(KNOWN_HOSTS_DESTS)

    def _config_success_base(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        (
            self.config.local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
            .local.get_host_info(NODE_NAME, NODE_DEST_LIST)
            .local.push_existing_authkey_to_remote(NODE_NAME, NODE_DEST_LIST)
            .local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST)
            .local.push_cib()
        )

    def test_success_base(self):
        self._config_success_base()
        node_add_guest(self.env_assist.get_env())
        self.env_assist.assert_reports(REPORTS)

    @mock.patch("pcs.lib.commands.remote_node.generate_binary_key")
    def test_success_generated_authkey(self, generate_binary_key):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        generate_binary_key.return_value = b"password"
        (
            self.config.local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
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
            .local.push_cib()
        )
        node_add_guest(self.env_assist.get_env())
        generate_binary_key.assert_called_once_with(random_bytes_count=256)
        self.env_assist.assert_reports(
            REPORTS.adapt(
                "authkey_distribution_started",
                node_list=[NODE_1, NODE_2, NODE_NAME],
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
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        (
            self.config.local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(
                        label=NODE_NAME,
                        dest_list=NODE_DEST_LIST,
                        **FAIL_HTTP_KWARGS,
                    )
                ],
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_guest(self.env_assist.get_env()), []
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
        (
            self.config.local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(
                        label=NODE_NAME,
                        dest_list=NODE_DEST_LIST,
                        **FAIL_HTTP_KWARGS,
                    )
                ],
            )
            .local.authkey_exists(return_value=True)
            .local.open_authkey(pcmk_authkey_content)
            .local.push_cib()
        )
        node_add_guest(self.env_assist.get_env(), skip_offline_nodes=True)
        self.env_assist.assert_reports(
            fixture_reports_new_node_unreachable(NODE_NAME, omitting=True)
        )

    @mock.patch("pcs.lib.commands.remote_node.generate_binary_key")
    def test_can_skip_all_offline(self, generate_binary_key):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        generate_binary_key.return_value = b"password"
        (
            self.config.local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(
                        label=NODE_NAME,
                        dest_list=NODE_DEST_LIST,
                        **FAIL_HTTP_KWARGS,
                    )
                ],
            )
            .local.authkey_exists(return_value=False)
            .local.distribute_authkey(
                communication_list=[
                    dict(
                        label=NODE_1,
                        dest_list=NODE_1_DEST_LIST,
                        **FAIL_HTTP_KWARGS,
                    ),
                    dict(
                        label=NODE_2,
                        dest_list=NODE_2_DEST_LIST,
                        **FAIL_HTTP_KWARGS,
                    ),
                ],
                pcmk_authkey_content=generate_binary_key.return_value,
            )
            .local.push_cib()
        )
        node_add_guest(self.env_assist.get_env(), skip_offline_nodes=True)
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
        (
            self.config.local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
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
                ),
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_guest(self.env_assist.get_env()), []
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
        (
            self.config.local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
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
            lambda: node_add_guest(self.env_assist.get_env()), []
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_RESPONSE_FORMAT,
                    node=NODE_NAME,
                )
            ]
        )

    def test_changed_options(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        meta_attributes = """
            <meta_attributes id="virtual_machine_id-meta_attributes">
                <nvpair id="virtual_machine_id-meta_attributes-remote-addr"
                    name="remote-addr" value="node-addr"
                />
                <nvpair
                    id="virtual_machine_id-meta_attributes-remote-connect-timeout"
                    name="remote-connect-timeout" value="20"
                />
                <nvpair
                    id="virtual_machine_id-meta_attributes-remote-node"
                    name="remote-node" value="node-name"
                />
                <nvpair
                    id="virtual_machine_id-meta_attributes-remote-port"
                    name="remote-port" value="1234"
                />
            </meta_attributes>
        """
        (
            self.config.local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
            .local.get_host_info(NODE_NAME, NODE_DEST_LIST)
            .local.push_existing_authkey_to_remote(NODE_NAME, NODE_DEST_LIST)
            .local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST)
            .local.push_cib(meta_attributes=meta_attributes)
        )
        # Since options are set, the default remote-addr == REMOTE_HOST is not
        # set. Therefore, it defaults to node name which is NODE_NAME.
        node_add_guest(
            self.env_assist.get_env(),
            options={"remote-port": 1234, "remote-connect-timeout": 20},
        )
        self.env_assist.assert_reports(
            base_reports_for_host(NODE_NAME).reports
            + [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=NODE_NAME,
                    address=NODE_ADDR_PCSD,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
            ]
        )

    def test_noexistent_resource(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.load_cib().corosync_conf.load(
            node_name_list=[NODE_1, NODE_2]
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_guest(
                self.env_assist.get_env(), resource_id="NOEXISTENT"
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ID_NOT_FOUND,
                    expected_types=["primitive"],
                    context_type="resources",
                    id="NOEXISTENT",
                    context_id="",
                )
            ],
        )

    def test_validate_values(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.load_cib().corosync_conf.load(
            node_name_list=[NODE_1, NODE_2]
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_guest(
                self.env_assist.get_env(),
                options={
                    "remote-addr": "*addr",
                    "remote-port": "abc",
                    "remote-connect-timeout": "def",
                },
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="remote-connect-timeout",
                    option_value="def",
                    allowed_values="time interval (e.g. 1, 2s, 3m, 4h, ...)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="remote-port",
                    option_value="abc",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
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
        self.config.local.load_cib().corosync_conf.load(
            node_name_list=[NODE_1, NODE_2]
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_guest(self.env_assist.get_env()), []
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
        (
            self.config.local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .local.authkey_exists(return_value=True)
            .local.open_authkey(pcmk_authkey_content)
            .local.push_cib()
        )
        node_add_guest(self.env_assist.get_env(), skip_offline_nodes=True)
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
        (
            self.config.local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .local.authkey_exists(return_value=False)
            .local.distribute_authkey(
                communication_list=[
                    dict(label=NODE_1, dest_list=NODE_1_DEST_LIST),
                    dict(label=NODE_2, dest_list=NODE_2_DEST_LIST),
                ],
                pcmk_authkey_content=generate_binary_key.return_value,
            )
            .local.push_cib()
        )
        node_add_guest(self.env_assist.get_env(), skip_offline_nodes=True)
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
        (
            self.config.env.set_known_hosts_dests(
                {
                    "rh7-1": [Destination("rh7-1", 2224)],
                    "rh7-2": [Destination("rh7-2", 2224)],
                    NODE_NAME: NODE_DEST_LIST,
                }
            ).corosync_conf.load(
                filename="corosync-some-node-names.conf",
                instead="corosync_conf.load",
            )
        )

        node_add_guest(self.env_assist.get_env())
        self.env_assist.assert_reports(
            REPORTS.warn(
                "missing_node_names_in_corosync",
                reports.codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                fatal=False,
            )
        )

    def test_all_node_names_missing(self):
        self._config_success_base()
        self.config.corosync_conf.load(
            filename="corosync-no-node-names.conf", instead="corosync_conf.load"
        )
        node_add_guest(self.env_assist.get_env())
        self.env_assist.assert_reports(
            REPORTS.warn(
                "missing_node_names_in_corosync",
                reports.codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                fatal=False,
            )
        )


class NotLive(TestCase):
    def setUp(self):
        self.tmp_file = "/fake/tmp_file"
        self.cmd_env = dict(CIB_file=self.tmp_file)
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests(KNOWN_HOSTS_DESTS)
        cib_xml_man = XmlManipulation.from_file(rc("cib-empty.xml"))
        cib_xml_man.append_to_first_tag_name(
            "resources",
            """
                <primitive class="ocf" id="{0}"
                    provider="heartbeat" type="VirtualDomain"
                />
            """.format(
                VIRTUAL_MACHINE_ID
            ),
        )
        self.config.env.set_cib_data(
            str(cib_xml_man), cib_tempfile=self.tmp_file
        )

    def test_addr_specified(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.load_cib(env=self.cmd_env)
        self.config.local.push_cib()
        node_add_guest(self.env_assist.get_env())
        self.env_assist.assert_reports(fixture_reports_not_live_cib(NODE_NAME))

    def test_addr_not_specified(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        meta_attributes = """
            <meta_attributes id="virtual_machine_id-meta_attributes">
                <nvpair id="virtual_machine_id-meta_attributes-remote-addr"
                    name="remote-addr" value="node-addr"
                />
                <nvpair
                    id="virtual_machine_id-meta_attributes-remote-node"
                    name="remote-node" value="node-name"
                />
                <nvpair
                    id="virtual_machine_id-meta_attributes-remote-port"
                    name="remote-port" value="99"
                />
            </meta_attributes>
        """
        self.config.local.load_cib(env=self.cmd_env)
        self.config.local.push_cib(meta_attributes=meta_attributes)
        node_add_guest(self.env_assist.get_env(), options={"remote-port": "99"})
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
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        meta_attributes = """
            <meta_attributes id="virtual_machine_id-meta_attributes">
                <nvpair id="virtual_machine_id-meta_attributes-remote-addr"
                    name="remote-addr" value="node-name"
                />
                <nvpair
                    id="virtual_machine_id-meta_attributes-remote-node"
                    name="remote-node" value="node-name"
                />
                <nvpair
                    id="virtual_machine_id-meta_attributes-remote-port"
                    name="remote-port" value="99"
                />
            </meta_attributes>
        """
        self.config.env.set_known_hosts_dests({})
        self.config.local.load_cib(env=self.cmd_env)
        self.config.local.push_cib(meta_attributes=meta_attributes)
        node_add_guest(self.env_assist.get_env(), options={"remote-port": "99"})
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
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        meta_attributes = """
            <meta_attributes id="virtual_machine_id-meta_attributes">
                <nvpair id="virtual_machine_id-meta_attributes-remote-addr"
                    name="remote-addr" value="aa"
                />
                <nvpair
                    id="virtual_machine_id-meta_attributes-remote-node"
                    name="remote-node" value="node-name"
                />
            </meta_attributes>
        """
        self.config.env.set_known_hosts_dests({})
        self.config.local.load_cib(env=self.cmd_env)
        self.config.local.push_cib(meta_attributes=meta_attributes)
        node_add_guest(self.env_assist.get_env(), options={"remote-addr": "aa"})
        self.env_assist.assert_reports(fixture_reports_not_live_cib(NODE_NAME))

    def test_validate_values(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.load_cib(env=self.cmd_env)
        self.env_assist.assert_raise_library_error(
            lambda: node_add_guest(
                self.env_assist.get_env(),
                options={
                    "remote-addr": "*addr",
                    "remote-port": "abc",
                    "remote-connect-timeout": "def",
                },
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.COROSYNC_NODE_CONFLICT_CHECK_SKIPPED,
                    reason_type="not_live_cib",
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="remote-connect-timeout",
                    option_value="def",
                    allowed_values="time interval (e.g. 1, 2s, 3m, 4h, ...)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="remote-port",
                    option_value="abc",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_wait(self):
        self.env_assist.assert_raise_library_error(
            lambda: node_add_guest(self.env_assist.get_env(), wait=1),
            [
                fixture.error(
                    reports.codes.WAIT_FOR_IDLE_NOT_LIVE_CLUSTER,
                ),
            ],
            expected_in_processor=False,
        )


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class WithWait(TestCase):
    def setUp(self):
        self.wait = 1
        self.env_assist, self.config = get_env_tools(self)
        (
            self.config.env.set_known_hosts_dests(KNOWN_HOSTS_DESTS)
            .local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
            .local.get_host_info(NODE_NAME, NODE_DEST_LIST)
            .local.push_existing_authkey_to_remote(NODE_NAME, NODE_DEST_LIST)
            .local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST)
            .local.push_cib(wait=self.wait)
        )

    def test_success_when_resource_started(self):
        self.config.runner.pcmk.load_state(
            resources=f"""
                <resources>
                    <resource
                        id="{VIRTUAL_MACHINE_ID}"
                        resource_agent="ocf::pacemaker:remote"
                    >
                        <node name="{NODE_1}" id="1" cached="false"/>
                    </resource>
                </resources>
            """
        )
        node_add_guest(self.env_assist.get_env(), wait=self.wait)
        self.env_assist.assert_reports(
            REPORTS.info(
                "resource_running",
                reports.codes.RESOURCE_RUNNING_ON_NODES,
                roles_with_nodes={"Started": [NODE_1]},
                resource_id=VIRTUAL_MACHINE_ID,
            )
        )

    def test_fail_when_resource_not_started(self):
        self.config.runner.pcmk.load_state(
            resources=f"""
                <resources>
                    <resource
                        id="{VIRTUAL_MACHINE_ID}"
                        resource_agent="ocf::pacemaker:remote"
                        failed="true"
                    >
                        <node name="{NODE_1}" id="1" cached="false"/>
                    </resource>
                </resources>
            """
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_guest(self.env_assist.get_env(), wait=self.wait)
        )
        self.env_assist.assert_reports(
            REPORTS.reports
            + [
                fixture.error(
                    reports.codes.RESOURCE_DOES_NOT_RUN,
                    resource_id=VIRTUAL_MACHINE_ID,
                )
            ]
        )


class RemoteService(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        (
            self.config.env.set_known_hosts_dests(KNOWN_HOSTS_DESTS)
            .local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
            .local.get_host_info(NODE_NAME, NODE_DEST_LIST)
            .local.push_existing_authkey_to_remote(NODE_NAME, NODE_DEST_LIST)
        )

    def test_fails_when_offline(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.run_pacemaker_remote(
            NODE_NAME, NODE_DEST_LIST, **FAIL_HTTP_KWARGS
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_guest(self.env_assist.get_env()),
        )

        self.env_assist.assert_reports(
            REPORTS[:"pcmk_remote_enable_success"]
            + EXTRA_REPORTS.select("manage_services_connection_failed")
        )

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
            lambda: node_add_guest(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            REPORTS[:"pcmk_remote_enable_success"]
            + EXTRA_REPORTS.select(
                "pcmk_remote_enable_failed",
                "pcmk_remote_start_failed",
            )
        )

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
        ).local.push_cib()
        node_add_guest(
            self.env_assist.get_env(), allow_pacemaker_remote_service_fail=True
        )

        self.env_assist.assert_reports(
            REPORTS[:"pcmk_remote_enable_success"]
            + EXTRA_REPORTS.select(
                "pcmk_remote_enable_failed_warn",
                "pcmk_remote_start_failed_warn",
            )
        )


class AuthkeyDistribution(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        (
            self.config.env.set_known_hosts_dests(KNOWN_HOSTS_DESTS)
            .local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .http.host.check_auth(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
            .local.get_host_info(NODE_NAME, NODE_DEST_LIST)
        )

    def test_fails_when_offline(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        pcmk_authkey_content = b"password"
        (
            self.config.local.authkey_exists(return_value=True)
            .local.open_authkey(pcmk_authkey_content)
            .local.distribute_authkey(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
                pcmk_authkey_content=pcmk_authkey_content,
                **FAIL_HTTP_KWARGS,
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_guest(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            REPORTS[:"authkey_distribution_success"]
            + EXTRA_REPORTS.only(
                "manage_services_connection_failed",
                command="remote/put_file",
            )
        )

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
            lambda: node_add_guest(self.env_assist.get_env())
        )

        self.env_assist.assert_reports(
            REPORTS[:"authkey_distribution_success"]
            + EXTRA_REPORTS.select("authkey_distribution_failed")
        )

    def test_forceable_when_remotely_fail(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        (
            self.config.local.push_existing_authkey_to_remote(
                NODE_NAME,
                NODE_DEST_LIST,
                distribution_result={
                    "code": "conflict",
                    "message": "",
                },
            )
            .local.run_pacemaker_remote(NODE_NAME, NODE_DEST_LIST)
            .local.push_cib()
        )

        node_add_guest(
            self.env_assist.get_env(),
            allow_incomplete_distribution=True,
        )

        self.env_assist.assert_reports(
            REPORTS.remove("authkey_distribution_success")
            + EXTRA_REPORTS.select("authkey_distribution_failed_warn")
        )
