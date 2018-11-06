from functools import partial
from unittest import mock, TestCase

from pcs.common import report_codes
from pcs.common.host import Destination
from pcs.lib.commands.remote_node import(
    node_remove_remote as node_remove_remote_orig
)
from pcs.lib.commands.test.remote_node.fixtures_add import FAIL_HTTP_KWARGS
from pcs.lib.commands.test.remote_node.fixtures_remove import(
    EnvConfigMixin,
    REPORTS as FIXTURE_REPORTS,
    EXTRA_REPORTS as FIXTURE_EXTRA_REPORTS,
)
from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools


NODE_NAME = "node-name"
NODE_DEST_LIST = [Destination("node-addr", 2224)]
REMOTE_HOST = "remote-host"
REMOTE_DEST_LIST = [Destination("remote-addr", 2224)]
NODE_1 = "node-1"
NODE_2 = "node-2"

def node_remove_remote(env, *args, node_identifier=REMOTE_HOST, **kwargs):
    node_remove_remote_orig(env, node_identifier, *args, **kwargs)

FIXTURE_RESOURCES = """
    <resources>
        <primitive class="ocf" id="{0}" provider="pacemaker" type="remote">
            <instance_attributes id="node-name-instance_attributes">
                <nvpair
                    id="node-name-instance_attributes-server"
                    name="server" value="{1}"
                />
            </instance_attributes>
        </primitive>
    </resources>
""".format(
    NODE_NAME,
    REMOTE_HOST,
)

REPORTS = (FIXTURE_REPORTS
    .adapt("pcmk_remote_disable_stop_started", node_list=[NODE_NAME])
    .adapt("pcmk_remote_disable_success", node=NODE_NAME)
    .adapt("pcmk_remote_stop_success", node=NODE_NAME)
    .adapt("authkey_remove_started", node_list=[NODE_NAME])
    .adapt("authkey_remove_success", node=NODE_NAME)
)

EXTRA_REPORTS = (FIXTURE_EXTRA_REPORTS
    .adapt_multi(
        [
            "authkey_remove_failed",
            "authkey_remove_failed_warn",
            "manage_services_connection_failed",
            "manage_services_connection_failed_warn",
            "pcmk_remote_disable_failed",
            "pcmk_remote_disable_failed_warn",
            "pcmk_remote_stop_failed",
            "pcmk_remote_stop_failed_warn",
            "remove_file_connection_failed",
            "remove_file_connection_failed_warn",
        ],
        node=NODE_NAME
    )
)

get_env_tools = partial(get_env_tools, local_extensions={
    "local": EnvConfigMixin
})

class RemoveRemote(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests({
            NODE_NAME: NODE_DEST_LIST,
        })
        self.remove_resource = mock.Mock()

    def find_by(self, identifier):
        (self.config
            .runner.cib.load(resources=FIXTURE_RESOURCES)
            .local.destroy_pacemaker_remote(
                label=NODE_NAME, dest_list=NODE_DEST_LIST
            )
            .local.remove_authkey(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
        )
        node_remove_remote(
            self.env_assist.get_env(),
            node_identifier=identifier,
            remove_resource=self.remove_resource
        )
        self.remove_resource.assert_called_once_with(
            NODE_NAME,
            is_remove_remote_context=True
        )
        self.env_assist.assert_reports(REPORTS)

    def test_success_base(self):
        self.find_by(REMOTE_HOST)

    def test_can_find_by_node_name(self):
        self.find_by(NODE_NAME)

class RemoveRemoteOthers(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.remove_resource = mock.Mock()
        self.config.env.set_known_hosts_dests({
            NODE_NAME: NODE_DEST_LIST,
        })

    def test_can_skip_all_offline(self):
        (self.config
            .runner.cib.load(resources=FIXTURE_RESOURCES)
            .local.destroy_pacemaker_remote(
                label=NODE_NAME,
                dest_list=NODE_DEST_LIST,
                **FAIL_HTTP_KWARGS
            )
            .local.remove_authkey(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
                **FAIL_HTTP_KWARGS
            )
        )
        node_remove_remote(
            self.env_assist.get_env(),
            remove_resource=self.remove_resource,
            skip_offline_nodes=True
        )
        self.remove_resource.assert_called_once_with(
            NODE_NAME,
            is_remove_remote_context=True
        )
        self.env_assist.assert_reports(
            REPORTS.remove(
                "pcmk_remote_disable_success",
                "pcmk_remote_stop_success",
                "authkey_remove_success",
            )
            +
            EXTRA_REPORTS.select(
                "manage_services_connection_failed_warn",
                "remove_file_connection_failed_warn"
            )
        )

    def test_fail_when_identifier_not_found(self):
        (self.config
            .runner.cib.load(resources=FIXTURE_RESOURCES)
         )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_remote(
                self.env_assist.get_env(),
                remove_resource=self.remove_resource,
                node_identifier="NOEXISTENT"
            ),
            [
                fixture.error(
                    report_codes.NODE_NOT_FOUND,
                    node="NOEXISTENT",
                    searched_types="remote",
                )
            ],
            expected_in_processor=False
        )

class MultipleResults(TestCase):
    fixture_multi_resources = """
        <resources>
            <primitive class="ocf" id="{0}" provider="pacemaker" type="remote">
                <instance_attributes id="node-name-instance_attributes">
                    <nvpair
                        id="node-name-instance_attributes-server"
                        name="server" value="{1}"
                    />
                </instance_attributes>
            </primitive>
            <primitive class="ocf" id="{1}" provider="pacemaker" type="remote">
                <instance_attributes id="node-name-instance_attributes">
                    <nvpair
                        id="node-name-instance_attributes-server"
                        name="server" value="{2}"
                    />
                </instance_attributes>
            </primitive>
        </resources>
    """.format(
        NODE_NAME,
        REMOTE_HOST,
        "OTHER-REMOTE"
    )
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.remove_resource = mock.Mock()
        (self.config
            .runner.cib.load(resources=self.fixture_multi_resources)
        )
        self.multiple_result_reports = (fixture.ReportStore()
            .error(
                "multiple_result_found",
                report_codes.MULTIPLE_RESULTS_FOUND,
                result_identifier_list=[
                    NODE_NAME,
                    REMOTE_HOST,
                ],
                result_type="resource",
                search_description=REMOTE_HOST,
                force_code=report_codes.FORCE_REMOVE_MULTIPLE_NODES
            )
            .as_warn(
                "multiple_result_found",
                "multiple_result_found_warn",
            )
        )
        self.config.env.set_known_hosts_dests({
            NODE_NAME: NODE_DEST_LIST,
            REMOTE_HOST: REMOTE_DEST_LIST,
        })

    def test_fail(self):
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_remote(
                self.env_assist.get_env(),
                node_identifier=REMOTE_HOST,
                remove_resource=self.remove_resource
            ),
            self.multiple_result_reports.select("multiple_result_found").reports
        )

    def test_force(self):
        (self.config
            .local.destroy_pacemaker_remote(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST),
                    dict(label=REMOTE_HOST, dest_list=REMOTE_DEST_LIST),
                ]
            )
            .local.remove_authkey(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST),
                    dict(label=REMOTE_HOST, dest_list=REMOTE_DEST_LIST),
                ],
            )
         )
        node_remove_remote(
            self.env_assist.get_env(),
            node_identifier=REMOTE_HOST,
            remove_resource=self.remove_resource,
            allow_remove_multiple_nodes=True,
        )
        self.env_assist.assert_reports(
            REPORTS
                .adapt(
                    "pcmk_remote_disable_stop_started",
                    node_list=[NODE_NAME, REMOTE_HOST]
                )
                .copy(
                    "pcmk_remote_disable_success",
                    "pcmk_remote_disable_success_remote_host",
                    node=REMOTE_HOST,
                )
                .copy(
                    "pcmk_remote_stop_success",
                    "pcmk_remote_stop_success_remote_host",
                    node=REMOTE_HOST,
                )
                .adapt(
                    "authkey_remove_started",
                    node_list=[NODE_NAME, REMOTE_HOST]
                )
                .copy(
                    "authkey_remove_success",
                    "authkey_remove_success_remote_host",
                    node=REMOTE_HOST,
                )
            +
            self.multiple_result_reports.select("multiple_result_found_warn")
        )


class AuthkeyRemove(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests({
            NODE_NAME: NODE_DEST_LIST,
        })
        (self.config
            .runner.cib.load(resources=FIXTURE_RESOURCES)
            .local.destroy_pacemaker_remote(
                label=NODE_NAME, dest_list=NODE_DEST_LIST
            )
        )
        self.remove_resource = mock.Mock()

    def test_fails_when_offline(self):
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
            **FAIL_HTTP_KWARGS
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_remote(
                self.env_assist.get_env(),
                remove_resource=self.remove_resource,
            )
        )
        self.env_assist.assert_reports(
            REPORTS.remove("authkey_remove_success")
            +
            EXTRA_REPORTS.select("remove_file_connection_failed")
        )

    def test_fails_when_remotely_fails(self):
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
            result={
                "code": "unexpected",
                "message": "Access denied",
            }
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_remote(
                self.env_assist.get_env(),
                remove_resource=self.remove_resource,
            )
        )
        self.env_assist.assert_reports(
            REPORTS.remove("authkey_remove_success")
            +
            EXTRA_REPORTS.select("authkey_remove_failed")
        )

    def test_forceable_when_remotely_fail(self):
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
            result={
                "code": "unexpected",
                "message": "Access denied",
            }
        )
        node_remove_remote(
            self.env_assist.get_env(),
            remove_resource=self.remove_resource,
            allow_pacemaker_remote_service_fail=True
        )
        self.env_assist.assert_reports(
            REPORTS.remove("authkey_remove_success")
            +
            EXTRA_REPORTS.select("authkey_remove_failed_warn")
        )

class PcmkRemoteServiceDestroy(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES)
        self.remove_resource = mock.Mock()
        self.config.env.set_known_hosts_dests({
            NODE_NAME: NODE_DEST_LIST,
        })

    def test_fails_when_offline(self):
        (self.config
            .local.destroy_pacemaker_remote(
                label=NODE_NAME,
                dest_list=NODE_DEST_LIST,
                **FAIL_HTTP_KWARGS
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_remote(
                self.env_assist.get_env(),
                remove_resource=self.remove_resource,
            )
        )
        self.env_assist.assert_reports(
            REPORTS[:"pcmk_remote_disable_success"]
            +
            EXTRA_REPORTS.select("manage_services_connection_failed")
        )

    def test_fails_when_remotely_fails(self):
        (self.config
            .local.destroy_pacemaker_remote(
                label=NODE_NAME,
                dest_list=NODE_DEST_LIST,
                result={
                    "code": "fail",
                    "message": "Action failed",
                }
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_remote(
                self.env_assist.get_env(),
                remove_resource=self.remove_resource,
            )
        )
        self.env_assist.assert_reports(
            REPORTS[:"pcmk_remote_disable_success"]
            +
            EXTRA_REPORTS.select(
                "pcmk_remote_disable_failed",
                "pcmk_remote_stop_failed",
            )
        )

    def test_forceable_when_remotely_fail(self):
        (self.config
            .local.destroy_pacemaker_remote(
                label=NODE_NAME,
                dest_list=NODE_DEST_LIST,
                result={
                    "code": "fail",
                    "message": "Action failed",
                }
            )
            .local.remove_authkey(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
        )
        node_remove_remote(
            self.env_assist.get_env(),
            remove_resource=self.remove_resource,
            allow_pacemaker_remote_service_fail=True
        )
        self.env_assist.assert_reports(
            REPORTS.remove(
                "pcmk_remote_disable_success",
                "pcmk_remote_stop_success",
            )
            +
            EXTRA_REPORTS.select(
                "pcmk_remote_disable_failed_warn",
                "pcmk_remote_stop_failed_warn",
            )
        )
