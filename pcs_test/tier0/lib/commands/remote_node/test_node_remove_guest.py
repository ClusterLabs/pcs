# pylint: disable=no-member
from functools import partial
from unittest import TestCase

from pcs_test.tier0.lib.commands.remote_node.fixtures_add import (
    FAIL_HTTP_KWARGS,
)
from pcs_test.tier0.lib.commands.remote_node.fixtures_remove import(
    EnvConfigMixin,
    REPORTS as FIXTURE_REPORTS,
    EXTRA_REPORTS as FIXTURE_EXTRA_REPORTS,
)
from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from pcs.common import report_codes
from pcs.common.host import Destination
from pcs.lib.commands.remote_node import(
    node_remove_guest as node_remove_guest_orig
)


REMOTE_HOST = "remote-host"
REMOTE_DEST_LIST = [Destination("remote-addr", 2224)]
NODE_NAME = "node-name"
NODE_DEST_LIST = [Destination("node-addr", 2224)]
VIRTUAL_MACHINE_ID = "virtual_machine_id"

def node_remove_guest(env, node_identifier=REMOTE_HOST, **kwargs):
    node_remove_guest_orig(env, node_identifier, **kwargs)

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

FIXTURE_RESOURCES = """
    <resources>
        <primitive class="ocf" id="{0}"
            provider="heartbeat" type="VirtualDomain"
        >
            <meta_attributes id="virtual_machine_id-meta_attributes">
                <nvpair id="virtual_machine_id-meta_attributes-remote-addr"
                    name="remote-addr" value="{1}"
                />
                <nvpair id="virtual_machine_id-meta_attributes-remote-node"
                    name="remote-node" value="{2}"
                />
             </meta_attributes>
        </primitive>
    </resources>
""".format(VIRTUAL_MACHINE_ID, REMOTE_HOST, NODE_NAME)

GUEST_NVPAIR_XPATHS = [
    ".//primitive/meta_attributes/nvpair[@name='remote-addr']",
    ".//primitive/meta_attributes/nvpair[@name='remote-node']",
]

get_env_tools = partial(get_env_tools, local_extensions={
    "local": EnvConfigMixin
})

class RemoveGuest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests({
            NODE_NAME: NODE_DEST_LIST,
        })

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
            .env.push_cib(remove=GUEST_NVPAIR_XPATHS)
            .runner.pcmk.remove_node(NODE_NAME)
        )
        node_remove_guest(self.env_assist.get_env(), node_identifier=identifier)
        self.env_assist.assert_reports(REPORTS)

    def test_success_base(self):
        self.find_by(REMOTE_HOST)

    def test_can_find_by_node_name(self):
        self.find_by(NODE_NAME)

    def test_can_find_by_resource_id(self):
        self.find_by(VIRTUAL_MACHINE_ID)


class RemoveGuestOthers(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests({
            NODE_NAME: NODE_DEST_LIST,
        })

    def test_success_with_wait(self):
        wait = 10
        (self.config
            .runner.pcmk.can_wait()
            .runner.cib.load(resources=FIXTURE_RESOURCES)
            .local.destroy_pacemaker_remote(
                label=NODE_NAME, dest_list=NODE_DEST_LIST
            )
            .local.remove_authkey(
                communication_list=[
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
            )
            .env.push_cib(remove=GUEST_NVPAIR_XPATHS, wait=wait)
            .runner.pcmk.remove_node(NODE_NAME)
        )
        node_remove_guest(self.env_assist.get_env(), wait=wait)
        self.env_assist.assert_reports(REPORTS)

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
            .env.push_cib(remove=GUEST_NVPAIR_XPATHS)
            .runner.pcmk.remove_node(NODE_NAME)
        )
        node_remove_guest(self.env_assist.get_env(), skip_offline_nodes=True)
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
        ))

    def test_fail_when_identifier_not_found(self):
        (self.config
            .runner.cib.load(resources=FIXTURE_RESOURCES)
         )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_guest(
                self.env_assist.get_env(),
                node_identifier="NOEXISTENT"
            ),
            [
                fixture.error(
                    report_codes.NODE_NOT_FOUND,
                    node="NOEXISTENT",
                    searched_types="guest",
                )
            ],
            expected_in_processor=False
        )

class MultipleResults(TestCase):
    fixture_multi_resources = """
        <resources>
            <primitive class="ocf" id="{0}"
                provider="heartbeat" type="VirtualDomain"
            >
                <meta_attributes id="A-M">
                    <nvpair id="A-M-RAddr" name="remote-addr" value="{1}"/>
                    <nvpair id="A-M-RNode" name="remote-node" value="{2}"/>
                 </meta_attributes>
            </primitive>

            <primitive class="ocf" id="{1}"
                provider="heartbeat" type="VirtualDomain"
            >
                <meta_attributes id="B-M">
                    <nvpair id="B-M-RAddr" name="remote-addr" value="{3}"/>
                    <nvpair id="B-M-RNode" name="remote-node" value="{4}"/>
                 </meta_attributes>
            </primitive>

            <primitive class="ocf" id="C"
                provider="heartbeat" type="VirtualDomain"
            >
                <meta_attributes id="C-M">
                    <nvpair id="C-M-RAddr" name="remote-addr" value="{2}"/>
                    <nvpair id="C-M-RNode" name="remote-node" value="{1}"/>
                 </meta_attributes>
            </primitive>
        </resources>
    """.format(
        VIRTUAL_MACHINE_ID, REMOTE_HOST, NODE_NAME, "B-HOST", "B-NAME"
    )

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(resources=self.fixture_multi_resources)
        self.multiple_result_reports = (fixture.ReportStore()
            .error(
                "multiple_result_found",
                report_codes.MULTIPLE_RESULTS_FOUND,
                result_identifier_list=[
                    VIRTUAL_MACHINE_ID,
                    REMOTE_HOST,
                    "C",
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
        self.dest_list_b = [Destination("B-ADDR", 2224)]
        self.config.env.set_known_hosts_dests({
            NODE_NAME: NODE_DEST_LIST,
            REMOTE_HOST: REMOTE_DEST_LIST,
            "B-NAME": self.dest_list_b,
        })

    def test_fail(self):
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_guest(
                self.env_assist.get_env(),
                node_identifier=REMOTE_HOST
            )
        )
        self.env_assist.assert_reports(
            self.multiple_result_reports.select("multiple_result_found").reports
        )

    def test_force(self):
        (self.config
            .local.destroy_pacemaker_remote(
                communication_list=[
                    dict(label="B-NAME", dest_list=self.dest_list_b),
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST),
                    dict(label=REMOTE_HOST, dest_list=REMOTE_DEST_LIST),
                ],
            )
            .local.remove_authkey(
                communication_list=[
                    dict(label="B-NAME", dest_list=self.dest_list_b),
                    dict(label=NODE_NAME, dest_list=NODE_DEST_LIST),
                    dict(label=REMOTE_HOST, dest_list=REMOTE_DEST_LIST),
                ],
            )
            .env.push_cib(remove=[
                ".//meta_attributes[@id='A-M']/nvpair[@name='remote-addr']",
                ".//meta_attributes[@id='A-M']/nvpair[@name='remote-node']",
                ".//meta_attributes[@id='B-M']/nvpair[@name='remote-addr']",
                ".//meta_attributes[@id='B-M']/nvpair[@name='remote-node']",
                ".//meta_attributes[@id='C-M']/nvpair[@name='remote-addr']",
                ".//meta_attributes[@id='C-M']/nvpair[@name='remote-node']",
            ])
            .runner.pcmk.remove_node("B-NAME", name="runner.pcmk.remove_node3")
            .runner.pcmk.remove_node(NODE_NAME, name="runner.pcmk.remove_node2")
            .runner.pcmk.remove_node(REMOTE_HOST)
        )
        node_remove_guest(
            self.env_assist.get_env(),
            node_identifier=REMOTE_HOST,
            allow_remove_multiple_nodes=True
        )
        self.env_assist.assert_reports(
            REPORTS
                .adapt(
                    "pcmk_remote_disable_stop_started",
                    node_list=["B-NAME", NODE_NAME, REMOTE_HOST]
                )
                .copy(
                    "pcmk_remote_disable_success",
                    "pcmk_remote_disable_success_b_name",
                    node="B-NAME",
                )
                .copy(
                    "pcmk_remote_stop_success",
                    "pcmk_remote_stop_success_b_name",
                    node="B-NAME",
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
                    node_list=["B-NAME", NODE_NAME, REMOTE_HOST]
                )
                .copy(
                    "authkey_remove_success",
                    "authkey_remove_success_b_name",
                    node="B-NAME",
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
        (self.config
            .runner.cib.load(resources=FIXTURE_RESOURCES)
            .local.destroy_pacemaker_remote(
                label=NODE_NAME, dest_list=NODE_DEST_LIST
            )
        )
        self.config.env.set_known_hosts_dests({
            NODE_NAME: NODE_DEST_LIST,
        })

    def test_fails_when_offline(self):
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
            **FAIL_HTTP_KWARGS
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_guest(self.env_assist.get_env())
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
            lambda: node_remove_guest(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            REPORTS.remove("authkey_remove_success")
            +
            EXTRA_REPORTS.select("authkey_remove_failed")
        )

    def test_forceable_when_remotely_fail(self):
        (self.config
            .local.remove_authkey(
                communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
                ],
                result={
                    "code": "unexpected",
                    "message": "Access denied",
                }
            )
            .env.push_cib(remove=GUEST_NVPAIR_XPATHS)
            .runner.pcmk.remove_node(NODE_NAME)
        )
        node_remove_guest(
            self.env_assist.get_env(),
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
        self.config.env.set_known_hosts_dests({
            NODE_NAME: NODE_DEST_LIST,
        })
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES)

    def test_fails_when_offline(self):
        (self.config
            .local.destroy_pacemaker_remote(
                label=NODE_NAME,
                dest_list=NODE_DEST_LIST,
                **FAIL_HTTP_KWARGS
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_guest(self.env_assist.get_env())
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
            lambda: node_remove_guest(self.env_assist.get_env())
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
            .env.push_cib(remove=GUEST_NVPAIR_XPATHS)
            .runner.pcmk.remove_node(NODE_NAME)
        )
        node_remove_guest(
            self.env_assist.get_env(),
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
