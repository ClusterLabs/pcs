from functools import partial
from unittest import TestCase

from pcs.common import reports
from pcs.common.host import Destination
from pcs.common.reports import codes as report_codes
from pcs.lib.commands.remote_node import (
    node_remove_remote as node_remove_remote_orig,
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

NODE_NAME = "node-name"
NODE_DEST_LIST = [Destination("node-addr", 2224)]
REMOTE_HOST = "remote-host"
REMOTE_DEST_LIST = [Destination("remote-addr", 2224)]
NODE_1 = "node-1"
NODE_2 = "node-2"


def node_remove_remote(env, *args, node_identifier=REMOTE_HOST, **kwargs):
    node_remove_remote_orig(env, node_identifier, *args, **kwargs)


FIXTURE_RESOURCES_CIB = """
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

FIXTURE_RESOURCES_STATE_STARTED = f"""
    <resources>
        <resource id="{NODE_NAME}" managed="true" role="Started"/>
    </resources>
"""

FIXTURE_RESOURCES_STATE_STOPPED = f"""
    <resources>
        <resource id="{NODE_NAME}" managed="true" role="Stopped"/>
    </resources>
"""


REPORTS = fixture.ReportSequenceBuilder().info(
    report_codes.CIB_REMOVE_RESOURCES,
    id_list=[NODE_NAME],
    _name="cib_remove_resources",
).fixtures + base_reports_for_host(NODE_NAME)


get_env_tools = partial(
    get_env_tools, local_extensions={"local": EnvConfigMixin}
)


class RemoveRemote(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests(
            {
                NODE_NAME: NODE_DEST_LIST,
            }
        )

    def find_by(self, identifier):
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES_CIB)
        self.config.runner.pcmk.load_state(
            resources=FIXTURE_RESOURCES_STATE_STOPPED
        )
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME, dest_list=NODE_DEST_LIST
        )
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
        )
        self.config.env.push_cib(resources="<resources/>")
        self.config.runner.pcmk.remove_node(NODE_NAME)

        node_remove_remote(
            self.env_assist.get_env(), node_identifier=identifier
        )
        self.env_assist.assert_reports(REPORTS)

    def test_success_base(self):
        self.find_by(REMOTE_HOST)

    def test_can_find_by_node_name(self):
        self.find_by(NODE_NAME)


class RemoveRemoteOthers(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests(
            {
                NODE_NAME: NODE_DEST_LIST,
            }
        )

    def test_can_skip_all_offline(self):
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES_CIB)
        self.config.runner.pcmk.load_state(
            resources=FIXTURE_RESOURCES_STATE_STOPPED
        )
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME, dest_list=NODE_DEST_LIST, **FAIL_HTTP_KWARGS
        )
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
            **FAIL_HTTP_KWARGS,
        )
        self.config.env.push_cib(resources="<resources/>")
        self.config.runner.pcmk.remove_node(NODE_NAME)

        node_remove_remote(
            self.env_assist.get_env(), [reports.codes.SKIP_OFFLINE_NODES]
        )
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
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES_CIB)
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_remote(
                self.env_assist.get_env(), node_identifier="NOEXISTENT"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.NODE_NOT_FOUND,
                    node="NOEXISTENT",
                    searched_types=["remote"],
                )
            ]
        )

    def test_fails_when_some_started(self):
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES_CIB)
        self.config.runner.pcmk.load_state(
            resources=FIXTURE_RESOURCES_STATE_STARTED
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_remote(
                self.env_assist.get_env(), node_identifier=REMOTE_HOST
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.CANNOT_REMOVE_RESOURCES_NOT_STOPPED,
                    resource_id_list=[NODE_NAME],
                    force_code=report_codes.FORCE,
                )
            ]
        )

    def test_some_started_force(self):
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES_CIB)
        self.config.runner.pcmk.load_state(
            resources=FIXTURE_RESOURCES_STATE_STARTED
        )
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME, dest_list=NODE_DEST_LIST
        )
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
        )
        self.config.env.push_cib(resources="<resources/>")
        self.config.runner.pcmk.remove_node(NODE_NAME)
        node_remove_remote(
            self.env_assist.get_env(),
            node_identifier=REMOTE_HOST,
            force_flags=[reports.codes.FORCE],
        )

        self.env_assist.assert_reports(
            fixture.ReportSequenceBuilder()
            .warn(
                reports.codes.CANNOT_REMOVE_RESOURCES_NOT_STOPPED,
                resource_id_list=[NODE_NAME],
            )
            .fixtures
            + REPORTS
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
    """.format(NODE_NAME, REMOTE_HOST, "OTHER-REMOTE")

    fixture_multi_resources_state = f"""
        <resources>
            <resource id="{NODE_NAME}" managed="true" role="Stopped"/>
            <resource id="{REMOTE_HOST}" managed="true" role="Stopped"/>
        </resources>
    """

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(resources=self.fixture_multi_resources)
        self.report_multiple_results = fixture.error(
            report_codes.MULTIPLE_RESULTS_FOUND,
            force_code=report_codes.FORCE,
            result_identifier_list=[
                NODE_NAME,
                REMOTE_HOST,
            ],
            result_type="resource",
            search_description=REMOTE_HOST,
        )
        self.config.env.set_known_hosts_dests(
            {
                NODE_NAME: NODE_DEST_LIST,
                REMOTE_HOST: REMOTE_DEST_LIST,
            }
        )

    def test_fail(self):
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_remote(
                self.env_assist.get_env(), node_identifier=REMOTE_HOST
            )
        )
        self.env_assist.assert_reports([self.report_multiple_results])

    def test_force(self):
        self.config.runner.pcmk.load_state(
            resources=self.fixture_multi_resources_state
        )
        self.config.local.destroy_pacemaker_remote(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST),
                dict(label=REMOTE_HOST, dest_list=REMOTE_DEST_LIST),
            ]
        )
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST),
                dict(label=REMOTE_HOST, dest_list=REMOTE_DEST_LIST),
            ],
        )
        self.config.env.push_cib(resources="<resources/>")
        self.config.runner.pcmk.remove_node(
            NODE_NAME, name="remove_node.node_name"
        )
        self.config.runner.pcmk.remove_node(
            REMOTE_HOST, name="remove_node.remote_host"
        )

        node_remove_remote(
            self.env_assist.get_env(),
            node_identifier=REMOTE_HOST,
            force_flags=[reports.codes.FORCE],
        )
        my_reports = REPORTS.copy()
        my_reports.replace(
            "cib_remove_resources",
            REPORTS["cib_remove_resources"].adapt(
                id_list=[NODE_NAME, REMOTE_HOST]
            ),
        )
        my_reports.replace(
            "pcmk_remote_disable_stop_started",
            REPORTS["pcmk_remote_disable_stop_started"].adapt(
                node_list=[NODE_NAME, REMOTE_HOST]
            ),
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
                node_list=[NODE_NAME, REMOTE_HOST]
            ),
        )
        my_reports.append(
            REPORTS["authkey_remove_success"].adapt(node=REMOTE_HOST)
        )
        my_reports.append(self.report_multiple_results.to_warn())
        self.env_assist.assert_reports(my_reports)


class AuthkeyRemove(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_hosts_dests(
            {
                NODE_NAME: NODE_DEST_LIST,
            }
        )
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES_CIB)
        self.config.runner.pcmk.load_state(
            resources=FIXTURE_RESOURCES_STATE_STOPPED
        )

    def test_fails_when_offline(self):
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME, dest_list=NODE_DEST_LIST
        )
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
            **FAIL_HTTP_KWARGS,
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_remote(self.env_assist.get_env())
        )
        my_reports = REPORTS.copy()
        my_reports.remove("cib_remove_resources")
        my_reports.replace(
            "authkey_remove_success",
            report_remove_file_connection_failed(NODE_NAME),
        )
        self.env_assist.assert_reports(my_reports)

    def test_fails_when_remotely_fails(self):
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME, dest_list=NODE_DEST_LIST
        )
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
            lambda: node_remove_remote(self.env_assist.get_env())
        )
        my_reports = REPORTS.copy()
        my_reports.remove("cib_remove_resources")
        my_reports.replace(
            "authkey_remove_success",
            report_authkey_remove_failed(NODE_NAME),
        )
        self.env_assist.assert_reports(my_reports)

    def test_forceable_when_remotely_fail(self):
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME, dest_list=NODE_DEST_LIST
        )
        self.config.local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
            result={
                "code": "unexpected",
                "message": "Access denied",
            },
        )
        self.config.env.push_cib(resources="<resources/>")
        self.config.runner.pcmk.remove_node(NODE_NAME)

        node_remove_remote(self.env_assist.get_env(), [reports.codes.FORCE])
        my_reports = REPORTS.copy()
        my_reports.replace(
            "authkey_remove_success",
            report_authkey_remove_failed(NODE_NAME).to_warn(),
        )
        self.env_assist.assert_reports(my_reports)


class PcmkRemoteServiceDestroy(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(resources=FIXTURE_RESOURCES_CIB)
        self.config.runner.pcmk.load_state(
            resources=FIXTURE_RESOURCES_STATE_STOPPED
        )
        self.config.env.set_known_hosts_dests(
            {
                NODE_NAME: NODE_DEST_LIST,
            }
        )

    def test_fails_when_offline(self):
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME, dest_list=NODE_DEST_LIST, **FAIL_HTTP_KWARGS
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_remote(self.env_assist.get_env())
        )
        my_reports = REPORTS[:"pcmk_remote_disable_success"]
        my_reports.remove("cib_remove_resources")
        my_reports.append(report_manage_services_connection_failed(NODE_NAME))
        self.env_assist.assert_reports(my_reports)

    def test_fails_when_remotely_fails(self):
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME,
            dest_list=NODE_DEST_LIST,
            result={
                "code": "fail",
                "message": "Action failed",
            },
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_remove_remote(self.env_assist.get_env())
        )
        my_reports = REPORTS[:"pcmk_remote_disable_success"]
        my_reports.remove("cib_remove_resources")
        my_reports.append(report_pcmk_remote_disable_failed(NODE_NAME))
        my_reports.append(report_pcmk_remote_stop_failed(NODE_NAME))
        self.env_assist.assert_reports(my_reports)

    def test_forceable_when_remotely_fail(self):
        self.config.local.destroy_pacemaker_remote(
            label=NODE_NAME,
            dest_list=NODE_DEST_LIST,
            result={
                "code": "fail",
                "message": "Action failed",
            },
        ).local.remove_authkey(
            communication_list=[
                dict(label=NODE_NAME, dest_list=NODE_DEST_LIST)
            ],
        )
        self.config.env.push_cib(resources="<resources/>")
        self.config.runner.pcmk.remove_node(NODE_NAME)

        node_remove_remote(self.env_assist.get_env(), [reports.codes.FORCE])
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
