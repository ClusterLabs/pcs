from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import get_test_resource as rc

from pcs.common.reports import codes as report_codes
from pcs.lib.commands.cluster import node_clear


def _read_file(name):
    with open(rc(name)) as a_file:
        return a_file.read()

class NodeClear(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_requires_live_cib(self):
        (self.config
            .env.set_cib_data("<cib />")
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_clear(self.env_assist.get_env(), "nodeX"),
            [
                fixture.error(
                    report_codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=["CIB"],
                ),
            ],
            expected_in_processor=False
        )

    def test_requires_live_corosync(self):
        (self.config
            .env.set_corosync_conf_data(_read_file("corosync.conf"))
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_clear(self.env_assist.get_env(), "nodeX"),
            [
                fixture.error(
                    report_codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=["COROSYNC_CONF"],
                ),
            ],
            expected_in_processor=False
        )

    def test_requires_live(self):
        (self.config
            .env.set_corosync_conf_data(_read_file("corosync.conf"))
            .env.set_cib_data("<cib />")
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_clear(self.env_assist.get_env(), "nodeX"),
            [
                fixture.error(
                    report_codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=["CIB", "COROSYNC_CONF"],
                ),
            ],
            expected_in_processor=False
        )

    def test_success(self):
        (self.config
            .corosync_conf.load()
            .runner.cib.load(filename="cib-empty.xml")
            .runner.pcmk.remove_node("nodeX")
        )
        node_clear(self.env_assist.get_env(), "nodeX")

    def test_failure(self):
        (self.config
            .corosync_conf.load()
            .runner.cib.load(filename="cib-empty.xml")
            .runner.pcmk.remove_node("nodeX", stderr="some error", returncode=1)
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_clear(self.env_assist.get_env(), "nodeX"),
            [
                fixture.error(
                    report_codes.NODE_REMOVE_IN_PACEMAKER_FAILED,
                    node_list_to_remove=["nodeX"],
                    node="",
                    reason="some error"
                ),
            ],
            expected_in_processor=False
        )

    def test_existing_node_cib(self):
        resources = """
            <resources>
                <primitive class="ocf" provider="pacemaker" type="remote"
                    id="node-R"
                >
                </primitive>
            </resources>
        """
        (self.config
            .corosync_conf.load()
            .runner.cib.load(resources=resources)
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_clear(self.env_assist.get_env(), "node-R")
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.NODE_TO_CLEAR_IS_STILL_IN_CLUSTER,
                force_code=report_codes.FORCE_CLEAR_CLUSTER_NODE,
                node="node-R",
            ),
        ])

    def test_existing_node_corosync(self):
        (self.config
            .corosync_conf.load()
            .runner.cib.load(filename="cib-empty.xml")
        )
        self.env_assist.assert_raise_library_error(
            lambda: node_clear(self.env_assist.get_env(), "rh7-2")
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.NODE_TO_CLEAR_IS_STILL_IN_CLUSTER,
                force_code=report_codes.FORCE_CLEAR_CLUSTER_NODE,
                node="rh7-2",
            ),
        ])

    def test_exisitng_node_forced(self):
        (self.config
            .corosync_conf.load()
            .runner.cib.load(filename="cib-empty.xml")
            .runner.pcmk.remove_node("rh7-1")
        )
        node_clear(
            self.env_assist.get_env(), "rh7-1", allow_clear_cluster_node=True
        )
        self.env_assist.assert_reports([
            fixture.warn(
                report_codes.NODE_TO_CLEAR_IS_STILL_IN_CLUSTER,
                node="rh7-1",
            ),
        ])

    def test_some_node_names_missing(self):
        (self.config
            .corosync_conf.load(filename="corosync-some-node-names.conf")
            .runner.cib.load(filename="cib-empty.xml")
            .runner.pcmk.remove_node("nodeX")
        )
        node_clear(self.env_assist.get_env(), "nodeX")
        self.env_assist.assert_reports([
            fixture.warn(
                report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                fatal=False,
            ),
        ])

    def test_all_node_names_missing(self):
        (self.config
            .corosync_conf.load(filename="corosync-no-node-names.conf")
            .runner.cib.load(filename="cib-empty.xml")
            .runner.pcmk.remove_node("nodeX")
        )
        node_clear(self.env_assist.get_env(), "nodeX")
        self.env_assist.assert_reports([
            fixture.warn(
                report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                fatal=False,
            ),
        ])
