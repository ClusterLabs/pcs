from functools import partial
from unittest import TestCase

from pcs.common.host import Destination
from pcs.common.reports import codes as report_codes
from pcs.lib.commands.remote_node import (
    node_remove_guest as node_remove_guest_orig,
)

from pcs_test.tier0.lib.commands.remote_node.fixtures_add import (
    FAIL_HTTP_KWARGS,
    report_manage_services_connection_failed,
)
from pcs_test.tier0.lib.commands.remote_node.fixtures_remove import (
    EnvConfigMixin,
    base_reports_for_host,
    report_authkey_remove_failed,
    report_pcmk_remote_disable_failed,
    report_pcmk_remote_stop_failed,
    report_remove_file_connection_failed,
)
from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

REMOTE_HOST = "remote-host"
REMOTE_DEST_LIST = [Destination("remote-addr", 2224)]
NODE_NAME = "node-name"
NODE_DEST_LIST = [Destination("node-addr", 2224)]
VIRTUAL_MACHINE_ID = "virtual_machine_id"


def node_remove_guest(env, node_identifier=REMOTE_HOST, **kwargs):
    node_remove_guest_orig(env, node_identifier, **kwargs)


REPORTS = base_reports_for_host(NODE_NAME)

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

get_env_tools = partial(
    get_env_tools, local_extensions={"local": EnvConfigMixin}
)


class RemoveGuest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests(
            {
                NODE_NAME: NODE_DEST_LIST,
            }
        )

    def find_by(self, identifier):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES)
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME, dest_list=NODE_DEST_LIST
        )
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
        )
        self.config.env.push_cib(remove=GUEST_NVPAIR_XPATHS)
        self.config.runner.pcmk.remove_node(NODE_NAME)

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
        self.config.env.set_known_hosts_dests(
            {
                NODE_NAME: NODE_DEST_LIST,
            }
        )

    def test_success_with_wait(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        wait = 10
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES)
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME, dest_list=NODE_DEST_LIST
        )
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
        )
        self.config.env.push_cib(remove=GUEST_NVPAIR_XPATHS, wait=wait)
        self.config.runner.pcmk.remove_node(NODE_NAME)

        node_remove_guest(self.env_assist.get_env(), wait=wait)
        self.env_assist.assert_reports(REPORTS)

    def test_can_skip_all_offline(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES)
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME, dest_list=NODE_DEST_LIST, **FAIL_HTTP_KWARGS
        )
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
            **FAIL_HTTP_KWARGS,
        )
        self.config.env.push_cib(remove=GUEST_NVPAIR_XPATHS)
        self.config.runner.pcmk.remove_node(NODE_NAME)

        node_remove_guest(self.env_assist.get_env(), skip_offline_nodes=True)
        my_reports = REPORTS.copy()
        my_reports.replace(
            "pcmk_remote_disable_success",
            report_manage_services_connection_failed(NODE_NAME).to_warn(),
        )
        my_reports.remove("pcmk_remote_stop_success")
        my_reports.replace(
            "authkey_remove_success",
            report_remove_file_connection_failed(NODE_NAME).to_warn(),
        )
        self.env_assist.assert_reports(my_reports)

    def test_fail_when_identifier_not_found(self):
        (self.config.runner.cib.load(resources=FIXTURE_RESOURCES))
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_guest(
                self.env_assist.get_env(), node_identifier="NOEXISTENT"
            ),
            [
                fixture.error(
                    report_codes.NODE_NOT_FOUND,
                    node="NOEXISTENT",
                    searched_types=["guest"],
                )
            ],
            expected_in_processor=False,
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
    """.format(VIRTUAL_MACHINE_ID, REMOTE_HOST, NODE_NAME, "B-HOST", "B-NAME")

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(resources=self.fixture_multi_resources)
        self.report_multiple_results = fixture.error(
            report_codes.MULTIPLE_RESULTS_FOUND,
            force_code=report_codes.FORCE,
            result_identifier_list=[
                VIRTUAL_MACHINE_ID,
                REMOTE_HOST,
                "C",
            ],
            result_type="resource",
            search_description=REMOTE_HOST,
        )
        self.dest_list_b = [Destination("B-ADDR", 2224)]
        self.config.env.set_known_hosts_dests(
            {
                NODE_NAME: NODE_DEST_LIST,
                REMOTE_HOST: REMOTE_DEST_LIST,
                "B-NAME": self.dest_list_b,
            }
        )

    def test_fail(self):
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_guest(
                self.env_assist.get_env(), node_identifier=REMOTE_HOST
            )
        )
        self.env_assist.assert_reports([self.report_multiple_results])

    def test_force(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.destroy_pacemaker_remote(
            communication_list=[
                dict(label="B-NAME", dest_list=self.dest_list_b),
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST),
                dict(label=REMOTE_HOST, dest_list=REMOTE_DEST_LIST),
            ],
        )
        self.config.local.remove_authkey(
            communication_list=[
                dict(label="B-NAME", dest_list=self.dest_list_b),
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST),
                dict(label=REMOTE_HOST, dest_list=REMOTE_DEST_LIST),
            ],
        )
        self.config.env.push_cib(
            remove=[
                ".//meta_attributes[@id='A-M']/nvpair[@name='remote-addr']",
                ".//meta_attributes[@id='A-M']/nvpair[@name='remote-node']",
                ".//meta_attributes[@id='B-M']/nvpair[@name='remote-addr']",
                ".//meta_attributes[@id='B-M']/nvpair[@name='remote-node']",
                ".//meta_attributes[@id='C-M']/nvpair[@name='remote-addr']",
                ".//meta_attributes[@id='C-M']/nvpair[@name='remote-node']",
            ]
        )
        self.config.runner.pcmk.remove_node(
            "B-NAME", name="runner.pcmk.remove_node3"
        )
        self.config.runner.pcmk.remove_node(
            NODE_NAME, name="runner.pcmk.remove_node2"
        )
        self.config.runner.pcmk.remove_node(REMOTE_HOST)

        node_remove_guest(
            self.env_assist.get_env(),
            node_identifier=REMOTE_HOST,
            allow_remove_multiple_nodes=True,
        )
        my_reports = REPORTS.copy()
        my_reports.replace(
            "pcmk_remote_disable_stop_started",
            REPORTS["pcmk_remote_disable_stop_started"].adapt(
                node_list=["B-NAME", NODE_NAME, REMOTE_HOST]
            ),
        )
        my_reports.append(
            REPORTS["pcmk_remote_disable_success"].adapt(node="B-NAME")
        )
        my_reports.append(
            REPORTS["pcmk_remote_stop_success"].adapt(node="B-NAME")
        )
        my_reports.append(
            REPORTS["pcmk_remote_disable_success"].adapt(node=REMOTE_HOST)
        )
        my_reports.append(
            REPORTS["pcmk_remote_stop_success"].adapt(node=REMOTE_HOST)
        )
        my_reports.replace(
            "authkey_remove_started",
            REPORTS["authkey_remove_started"].adapt(
                node_list=["B-NAME", NODE_NAME, REMOTE_HOST]
            ),
        )
        my_reports.append(
            REPORTS["authkey_remove_success"].adapt(node="B-NAME")
        )
        my_reports.append(
            REPORTS["authkey_remove_success"].adapt(node=REMOTE_HOST)
        )
        my_reports.append(self.report_multiple_results.to_warn())
        self.env_assist.assert_reports(my_reports)


class AuthkeyRemove(TestCase):
    def setUp(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES)
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME, dest_list=NODE_DEST_LIST
        )
        self.config.env.set_known_hosts_dests(
            {
                NODE_NAME: NODE_DEST_LIST,
            }
        )

    def test_fails_when_offline(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
            **FAIL_HTTP_KWARGS,
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_guest(self.env_assist.get_env())
        )
        my_reports = REPORTS.copy()
        my_reports.replace(
            "authkey_remove_success",
            report_remove_file_connection_failed(NODE_NAME),
        )
        self.env_assist.assert_reports(my_reports)

    def test_fails_when_remotely_fails(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
            result={
                "code": "unexpected",
                "message": "Access denied",
            },
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_guest(self.env_assist.get_env())
        )
        my_reports = REPORTS.copy()
        my_reports.replace(
            "authkey_remove_success",
            report_authkey_remove_failed(NODE_NAME),
        )
        self.env_assist.assert_reports(my_reports)

    def test_forceable_when_remotely_fail(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
            result={
                "code": "unexpected",
                "message": "Access denied",
            },
        )
        self.config.env.push_cib(remove=GUEST_NVPAIR_XPATHS)
        self.config.runner.pcmk.remove_node(NODE_NAME)

        node_remove_guest(
            self.env_assist.get_env(), allow_pacemaker_remote_service_fail=True
        )
        my_reports = REPORTS.copy()
        my_reports.replace(
            "authkey_remove_success",
            report_authkey_remove_failed(NODE_NAME).to_warn(),
        )
        self.env_assist.assert_reports(my_reports)


class PcmkRemoteServiceDestroy(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests(
            {
                NODE_NAME: NODE_DEST_LIST,
            }
        )
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES)

    def test_fails_when_offline(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME, dest_list=NODE_DEST_LIST, **FAIL_HTTP_KWARGS
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_guest(self.env_assist.get_env())
        )
        my_reports = REPORTS[:"pcmk_remote_disable_success"]
        my_reports.append(report_manage_services_connection_failed(NODE_NAME))
        self.env_assist.assert_reports(my_reports)

    def test_fails_when_remotely_fails(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME,
            dest_list=NODE_DEST_LIST,
            result={
                "code": "fail",
                "message": "Action failed",
            },
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_guest(self.env_assist.get_env())
        )
        my_reports = REPORTS[:"pcmk_remote_disable_success"]
        my_reports.append(report_pcmk_remote_disable_failed(NODE_NAME))
        my_reports.append(report_pcmk_remote_stop_failed(NODE_NAME))
        self.env_assist.assert_reports(my_reports)

    def test_forceable_when_remotely_fail(self):
        # Instance of 'Config' has no 'local' member
        # pylint: disable=no-member
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME,
            dest_list=NODE_DEST_LIST,
            result={
                "code": "fail",
                "message": "Action failed",
            },
        )
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
        )
        self.config.env.push_cib(remove=GUEST_NVPAIR_XPATHS)
        self.config.runner.pcmk.remove_node(NODE_NAME)

        node_remove_guest(
            self.env_assist.get_env(), allow_pacemaker_remote_service_fail=True
        )
        my_reports = REPORTS.copy()
        my_reports.replace(
            "pcmk_remote_disable_success",
            report_pcmk_remote_disable_failed(NODE_NAME).to_warn(),
        )
        my_reports.replace(
            "pcmk_remote_stop_success",
            report_pcmk_remote_stop_failed(NODE_NAME).to_warn(),
        )
        self.env_assist.assert_reports(my_reports)
