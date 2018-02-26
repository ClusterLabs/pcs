from functools import partial
from unittest import mock, TestCase

from pcs.common import report_codes
from pcs.lib.commands.remote_node import node_add_guest as node_add_guest_orig
from pcs.lib.commands.test.remote_node.fixtures_add import(
    EnvConfigMixin,
    REPORTS as FIXTURE_REPORTS,
    EXTRA_REPORTS as FIXTURE_EXTRA_REPORTS,
    FAIL_HTTP_KWARGS,
)
from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools


NODE_NAME = "node-name"
REMOTE_HOST = "remote-host"
VIRTUAL_MACHINE_ID = "virtual_machine_id"
NODE_1 = "node-1"
NODE_2 = "node-2"

def node_add_guest(
    env, node_name=NODE_NAME, resource_id=VIRTUAL_MACHINE_ID, options=None,
    **kwargs
):
    options = options or {"remote-addr": REMOTE_HOST}
    node_add_guest_orig(env, node_name, resource_id, options, **kwargs)

FIXTURE_RESOURCES = """
    <resources>
        <primitive class="ocf" id="{0}"
            provider="heartbeat" type="VirtualDomain"
        />
    </resources>
""".format(VIRTUAL_MACHINE_ID)

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
    def load_cib(self):
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES)

    def push_cib(self, wait=False, meta_attributes=FIXTURE_META_ATTRIBUTES):
        self.config.env.push_cib(
            append={
                 './/resources/primitive[@id="{0}"]'
                    .format(VIRTUAL_MACHINE_ID): meta_attributes
                ,
            },
            wait=wait
        )

get_env_tools = partial(get_env_tools, local_extensions={"local": LocalConfig})

def base_reports_for_host(host=REMOTE_HOST):
    return (
        FIXTURE_REPORTS
            .adapt("authkey_distribution_started", node_list=[host])
            .adapt("authkey_distribution_success", node=host)
            .adapt("pcmk_remote_start_enable_started", node_list=[host])
            .adapt("pcmk_remote_enable_success", node=host)
            .adapt("pcmk_remote_start_success", node=host)
    )

REPORTS = base_reports_for_host()

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

class AddGuest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(
            [NODE_1, NODE_2, REMOTE_HOST, NODE_NAME]
        )

    def test_success_base(self):
        (self.config
            .local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST)
            .local.push_existing_authkey_to_remote(REMOTE_HOST)
            .local.run_pacemaker_remote(REMOTE_HOST)
            .local.push_cib()
        )
        node_add_guest(self.env_assist.get_env())
        self.env_assist.assert_reports(REPORTS)


    @mock.patch("pcs.lib.commands.remote_node.generate_key")
    def test_success_generated_authkey(self, generate_key):
        generate_key.return_value = b"password"
        (self.config
            .local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
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
            .local.push_cib()
        )
        node_add_guest(self.env_assist.get_env())
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
            .local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST, **FAIL_HTTP_KWARGS)
            .local.authkey_exists(return_value=True)
            .local.open_authkey(pcmk_authkey_content)
            .local.distribute_authkey(
                communication_list=[dict(label=REMOTE_HOST)],
                pcmk_authkey_content=pcmk_authkey_content,
                **FAIL_HTTP_KWARGS
            )
            .local.run_pacemaker_remote(REMOTE_HOST, **FAIL_HTTP_KWARGS)
            .local.push_cib()
        )
        node_add_guest(self.env_assist.get_env(), skip_offline_nodes=True)
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

    def test_changed_options(self):
        meta_attributes="""
            <meta_attributes id="virtual_machine_id-meta_attributes">
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
        (self.config
            .local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .local.check_node_availability(NODE_NAME)
            .local.push_existing_authkey_to_remote(NODE_NAME)
            .local.run_pacemaker_remote(NODE_NAME)
            .local.push_cib(meta_attributes=meta_attributes)
        )
        node_add_guest(self.env_assist.get_env(), options={
            #remote-addr is ommited here
            "remote-port": 1234,
            "remote-connect-timeout": 20
        })
        self.env_assist.assert_reports(base_reports_for_host(NODE_NAME))

    def test_noexistent_resource(self):
        (self.config
            .local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_guest(
                self.env_assist.get_env(),
                resource_id="NOEXISTENT"
            ),
            [
                fixture.error(
                    report_codes.ID_NOT_FOUND,
                    expected_types=["primitive"],
                    context_type="resources",
                    id="NOEXISTENT",
                    context_id=""
                )
            ],
        )

    def test_validate_values(self):
        (self.config
            .local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_guest(
                self.env_assist.get_env(),
                node_name="*name",
                options={
                    "remote-addr": "*addr",
                    "remote-port": "abc",
                    "remote-connect-timeout": "def",
                }
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="remote-connect-timeout",
                    option_value="def",
                    allowed_values="time interval (e.g. 1, 2s, 3m, 4h, ...)"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="remote-port",
                    option_value="abc",
                    allowed_values="a port number (1-65535)"
                )
            ]
        )

class WithWait(TestCase):
    def setUp(self):
        self.wait = 1
        self.env_assist, self.config = get_env_tools(self)
        (self.config
            .env.set_known_nodes([NODE_1, NODE_2, REMOTE_HOST, NODE_NAME])
            .runner.pcmk.can_wait()
            .local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST)
            .local.push_existing_authkey_to_remote(REMOTE_HOST)
            .local.run_pacemaker_remote(REMOTE_HOST)
            .local.push_cib(wait=self.wait)
        )

    def test_success_when_resource_started(self):
        (self.config
            .runner.pcmk.load_state(raw_resources=dict(
                resource_id=VIRTUAL_MACHINE_ID,
                resource_agent="ocf::pacemaker:remote",
                node_name=NODE_1,
            ))
        )
        node_add_guest(self.env_assist.get_env(), wait=self.wait)
        self.env_assist.assert_reports(
            REPORTS
                .info(
                    "resource_running",
                    report_codes.RESOURCE_RUNNING_ON_NODES,
                    roles_with_nodes={"Started": [NODE_1]},
                    resource_id=VIRTUAL_MACHINE_ID
                )
        )

    def test_fail_when_resource_not_started(self):
        (self.config
            .runner.pcmk.load_state(raw_resources=dict(
                resource_id=VIRTUAL_MACHINE_ID,
                resource_agent="ocf::pacemaker:remote",
                node_name=NODE_1,
                failed="true",
            ))
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_guest(self.env_assist.get_env(), wait=self.wait),
            [
                fixture.error(
                    report_codes.RESOURCE_DOES_NOT_RUN,
                    resource_id=VIRTUAL_MACHINE_ID,
                )
            ]
        )
        self.env_assist.assert_reports(REPORTS)

class RemoteService(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        (self.config
            .env.set_known_nodes([NODE_1, NODE_2, REMOTE_HOST, NODE_NAME])
            .local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST)
            .local.push_existing_authkey_to_remote(REMOTE_HOST)
        )
    def test_fails_when_offline(self):
        (self.config
            .local.run_pacemaker_remote(label=REMOTE_HOST, **FAIL_HTTP_KWARGS)
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_add_guest(self.env_assist.get_env()),
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
            lambda: node_add_guest(self.env_assist.get_env()),
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
            .local.push_cib()
        )
        node_add_guest(
            self.env_assist.get_env(),
            allow_pacemaker_remote_service_fail=True
        )

        self.env_assist.assert_reports(
            REPORTS[:"pcmk_remote_enable_success"] + EXTRA_REPORTS.select(
                "pcmk_remote_enable_failed_warn",
                "pcmk_remote_start_failed_warn",
            )
        )

class AuthkeyDistribution(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        (self.config
            .env.set_known_nodes([NODE_1, NODE_2, REMOTE_HOST, NODE_NAME])
            .local.load_cib()
            .corosync_conf.load(node_name_list=[NODE_1, NODE_2])
            .local.check_node_availability(REMOTE_HOST)
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
            lambda: node_add_guest(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            REPORTS[:"authkey_distribution_success"] + EXTRA_REPORTS.only(
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
            lambda: node_add_guest(self.env_assist.get_env())
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
            .local.push_cib()
        )

        node_add_guest(
            self.env_assist.get_env(),
            allow_incomplete_distribution=True,
        )

        self.env_assist.assert_reports(
            REPORTS.remove("authkey_distribution_success")
            +
            EXTRA_REPORTS.select("authkey_distribution_failed_warn")
        )
