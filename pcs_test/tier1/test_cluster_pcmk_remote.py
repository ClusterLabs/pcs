from textwrap import dedent

from pcs.common.str_tools import format_list, format_plural

from pcs_test.tier1.cib_resource.common import ResourceTest
from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.misc import ParametrizedTestMetaClass, write_data_to_tmpfile
from pcs_test.tools.misc import get_test_resource as rc

ERRORS_HAVE_OCCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)

NOT_STOPPING_RESOURCE_NOT_LIVE_CLUSTER = (
    "Warning: Resources are not going to be stopped before deletion because the"
    " command does not run on a live cluster\n"
)


def fixture_nolive_add_report(node_name):
    return dedent(
        f"""\
        Unable to check if there is a conflict with nodes set in corosync because the command does not run on a live cluster (e.g. -f was used)
        Distribution of 'pacemaker authkey' to '{node_name}' was skipped because the command does not run on a live cluster (e.g. -f was used). Please, distribute the file(s) manually.
        Running action(s) 'pacemaker_remote enable', 'pacemaker_remote start' on '{node_name}' was skipped because the command does not run on a live cluster (e.g. -f was used). Please, run the action(s) manually.
        """
    )


def fixture_nolive_remove_remote_report(host_list):
    return dedent(
        """\
        Warning: Not checking if {resources} {hosts} {are} stopped before deletion because the command does not run on a live cluster. Deleting unstopped resources may result in orphaned resources being present in the cluster.
        Running action(s) 'pacemaker_remote disable', 'pacemaker_remote stop' on {hosts} was skipped because the command does not run on a live cluster (e.g. -f was used). Please, run the action(s) manually.
        Removing 'pacemaker authkey' from {hosts} was skipped because the command does not run on a live cluster (e.g. -f was used). Please, remove the file(s) manually.
        """
    ).format(
        resources=format_plural(host_list, "resource"),
        hosts=", ".join("'{0}'".format(host) for host in host_list),
        are=format_plural(host_list, "is"),
    )


def fixture_nolive_remove_guest_report(host_list):
    return dedent(
        """\
        Running action(s) 'pacemaker_remote disable', 'pacemaker_remote stop' on {hosts} was skipped because the command does not run on a live cluster (e.g. -f was used). Please, run the action(s) manually.
        Removing 'pacemaker authkey' from {hosts} was skipped because the command does not run on a live cluster (e.g. -f was used). Please, remove the file(s) manually.
        """
    ).format(
        hosts=", ".join("'{0}'".format(host) for host in host_list),
    )


def fixture_nolive_node_remove(host_list):
    return dedent(
        """\
        Warning: Skipping removal of {node} {node_list} from pacemaker because the command does not run on a live cluster
        """.format(
            node=format_plural(host_list, "node"),
            node_list=format_list(host_list),
        )
    )


class RemoteTest(ResourceTest):
    corosync_conf = rc("corosync.conf")

    def setUp(self):
        super().setUp()
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        self.pcs_runner.mock_settings = get_mock_settings()


class NodeAddRemote(RemoteTest):
    def test_fail_on_duplicit_address_specification(self):
        self.assert_pcs_fail(
            "cluster node add-remote remote-node ADDRESS server=DIFFERENT".split(),
            "Unable to check if there is a conflict with nodes set in corosync "
            "because the command does not run on a live cluster (e.g. -f "
            "was used)\n"
            "Error: invalid resource option 'server', allowed options"
            " are: 'port', 'reconnect_interval', 'trace_file', 'trace_ra'\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_on_unknown_instance_attribute_not_offer_server(self):
        self.assert_pcs_fail(
            "cluster node add-remote remote-node ADDRESS abcd=efgh".split(),
            "Unable to check if there is a conflict with nodes set in corosync "
            "because the command does not run on a live cluster (e.g. -f "
            "was used)\n"
            "Error: invalid resource option 'abcd', allowed options"
            " are: 'port', 'reconnect_interval', 'trace_file', 'trace_ra', "
            "use --force to override\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_on_bad_commandline_usage(self):
        self.assert_pcs_fail(
            "cluster node add-remote".split(),
            stderr_start="\nUsage: pcs cluster node add-remote...",
        )

    def test_success(self):
        self.assert_effect(
            "cluster node add-remote node-name node-addr".split(),
            """<resources>
                <primitive class="ocf" id="node-name" provider="pacemaker"
                    type="remote"
                >
                    <instance_attributes id="node-name-instance_attributes">
                        <nvpair id="node-name-instance_attributes-server"
                            name="server" value="node-addr"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="node-name-migrate_from-interval-0s"
                            interval="0s" name="migrate_from" timeout="60s"
                        />
                        <op id="node-name-migrate_to-interval-0s" interval="0s"
                            name="migrate_to" timeout="60s"
                        />
                        <op id="node-name-monitor-interval-60s" interval="60s"
                            name="monitor" timeout="30s"
                        />
                        <op id="node-name-reload-interval-0s" interval="0s"
                            name="reload" timeout="60s"
                        />
                        <op id="node-name-reload-agent-interval-0s"
                            interval="0s" name="reload-agent" timeout="60s"
                        />
                        <op id="node-name-start-interval-0s" interval="0s"
                            name="start" timeout="60s"
                        />
                        <op id="node-name-stop-interval-0s" interval="0s"
                            name="stop" timeout="60s"
                        />
                    </operations>
                </primitive>
            </resources>""",
            stderr_full=fixture_nolive_add_report("node-name"),
        )

    def test_success_no_default_ops(self):
        self.assert_effect(
            "cluster node add-remote node-name node-addr --no-default-ops".split(),
            """<resources>
                <primitive class="ocf" id="node-name" provider="pacemaker"
                    type="remote"
                >
                    <instance_attributes id="node-name-instance_attributes">
                        <nvpair id="node-name-instance_attributes-server"
                            name="server" value="node-addr"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="node-name-monitor-interval-60s" interval="60s"
                            name="monitor" timeout="30s"
                        />
                    </operations>
                </primitive>
            </resources>""",
            stderr_full=fixture_nolive_add_report("node-name"),
        )

    def test_fail_when_server_already_used(self):
        self.assert_effect(
            "cluster node add-remote A node-addr --no-default-ops".split(),
            """<resources>
                <primitive class="ocf" id="A" provider="pacemaker"
                    type="remote"
                >
                    <instance_attributes id="A-instance_attributes">
                        <nvpair id="A-instance_attributes-server" name="server"
                            value="node-addr"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="A-monitor-interval-60s" interval="60s"
                            name="monitor" timeout="30s"
                        />
                    </operations>
                </primitive>
            </resources>""",
            stderr_full=fixture_nolive_add_report("A"),
        )
        self.assert_pcs_fail(
            "cluster node add-remote B node-addr".split(),
            "Unable to check if there is a conflict with nodes set in corosync "
            "because the command does not run on a live cluster (e.g. -f "
            "was used)\n"
            "Error: 'node-addr' already exists\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_when_server_already_used_as_guest(self):
        self.pcs_runner.corosync_conf_opt = None
        self.assert_pcs_success(
            "resource create G ocf:pcsmock:minimal --no-default-ops".split(),
        )
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        self.assert_pcs_success(
            "cluster node add-guest node-name G remote-addr=node-addr".split(),
            stderr_full=fixture_nolive_add_report("node-name"),
        )
        self.assert_pcs_fail(
            "cluster node add-remote B node-addr".split(),
            "Unable to check if there is a conflict with nodes set in corosync "
            "because the command does not run on a live cluster (e.g. -f "
            "was used)\n"
            "Error: 'node-addr' already exists\n" + ERRORS_HAVE_OCCURRED,
        )


class NodeAddGuest(RemoteTest):
    def create_resource(self):
        self.pcs_runner.corosync_conf_opt = None
        self.assert_effect(
            "resource create G ocf:pcsmock:minimal --no-default-ops".split(),
            """<resources>
                <primitive class="ocf" id="G" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="G-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )
        self.pcs_runner.corosync_conf_opt = self.corosync_conf

    def test_fail_on_bad_commandline_usage(self):
        self.assert_pcs_fail(
            "cluster node add-guest".split(),
            stderr_start="\nUsage: pcs cluster node add-guest...",
        )

    def test_fail_when_option_remote_node_specified(self):
        self.create_resource()
        self.assert_pcs_fail(
            "cluster node add-guest node-name G remote-node=node-name".split(),
            stderr_regexp=(
                ".*Error: invalid guest option 'remote-node', allowed options "
                "are: 'remote-addr', 'remote-connect-timeout', 'remote-port'.*"
            ),
        )

    def test_fail_when_resource_has_already_remote_node_meta(self):
        self.pcs_runner.corosync_conf_opt = None
        self.assert_pcs_success(
            (
                "resource create already-guest-node ocf:pcsmock:minimal "
                "meta remote-node=some --force"
            ).split(),
            stderr_full=(
                "Warning: this command is not sufficient for creating a guest node,"
                " use 'pcs cluster node add-guest'\n"
            ),
        )
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        self.assert_pcs_fail(
            "cluster node add-guest node-name already-guest-node "
            "remote-addr=a".split(),
            "Unable to check if there is a conflict with nodes set in corosync "
            "because the command does not run on a live cluster (e.g. -f "
            "was used)\n"
            "Error: the resource 'already-guest-node' is already a guest node\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_on_combined_reasons(self):
        self.assert_pcs_fail(
            "cluster node add-guest node-name G a=b remote-addr=a".split(),
            "Unable to check if there is a conflict with nodes set in corosync "
            "because the command does not run on a live cluster (e.g. -f "
            "was used)\n"
            "Error: invalid guest option 'a', allowed options are:"
            " 'remote-addr', 'remote-connect-timeout', 'remote-port'\n"
            "Error: resource 'G' does not exist\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_when_disallowed_option_appear(self):
        self.create_resource()
        self.assert_pcs_fail(
            "cluster node add-guest node-name G a=b remote-addr=a".split(),
            "Unable to check if there is a conflict with nodes set in corosync "
            "because the command does not run on a live cluster (e.g. -f "
            "was used)\n"
            "Error: invalid guest option 'a', allowed options are:"
            " 'remote-addr', 'remote-connect-timeout', 'remote-port'\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_when_invalid_interval_appear(self):
        self.create_resource()
        self.assert_pcs_fail(
            (
                "cluster node add-guest node-name G remote-connect-timeout=A "
                "remote-addr=a"
            ).split(),
            "Unable to check if there is a conflict with nodes set in corosync "
            "because the command does not run on a live cluster (e.g. -f "
            "was used)\n"
            "Error: 'A' is not a valid remote-connect-timeout value, use time"
            " interval (e.g. 1, 2s, 3m, 4h, ...)\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_when_invalid_port_appear(self):
        self.create_resource()
        self.assert_pcs_fail(
            (
                "cluster node add-guest node-name G remote-port=70000 "
                "remote-addr=a"
            ).split(),
            "Unable to check if there is a conflict with nodes set in corosync "
            "because the command does not run on a live cluster (e.g. -f "
            "was used)\n"
            "Error: '70000' is not a valid remote-port value, use a port number"
            " (1..65535)\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_when_guest_node_conflicts_with_existing_id(self):
        self.create_resource()
        self.pcs_runner.corosync_conf_opt = None
        self.assert_pcs_success(
            "resource create CONFLICT ocf:pcsmock:minimal".split()
        )
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        self.assert_pcs_fail(
            "cluster node add-guest CONFLICT G remote-addr=a".split(),
            "Unable to check if there is a conflict with nodes set in corosync "
            "because the command does not run on a live cluster (e.g. -f "
            "was used)\n"
            "Error: Cannot set name of the guest node to 'CONFLICT' because "
            "that ID already exists in the cluster configuration.\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_when_guest_node_conflicts_with_existing_guest(self):
        self.create_resource()
        self.pcs_runner.corosync_conf_opt = None
        self.assert_pcs_success("resource create H ocf:pcsmock:minimal".split())
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        self.assert_pcs_success(
            "cluster node add-guest node-name G remote-addr=a".split(),
            stderr_full=fixture_nolive_add_report("node-name"),
        )
        self.assert_pcs_fail(
            "cluster node add-guest node-name H remote-addr=b".split(),
            "Unable to check if there is a conflict with nodes set in corosync "
            "because the command does not run on a live cluster (e.g. -f "
            "was used)\n"
            "Error: Cannot set name of the guest node to 'node-name' because "
            "that ID already exists in the cluster configuration.\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_when_guest_node_conflicts_with_existing_remote(self):
        self.create_resource()
        self.pcs_runner.corosync_conf_opt = None
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote server=node-addr --force".split(),
            stderr_full=(
                "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
            ),
        )
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        self.assert_pcs_fail(
            "cluster node add-guest node-name G remote-addr=node-addr".split(),
            "Unable to check if there is a conflict with nodes set in corosync "
            "because the command does not run on a live cluster (e.g. -f "
            "was used)\n"
            "Error: Node address 'node-addr' is already used by existing "
            "nodes; please, use other address\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_when_guest_node_name_conflicts_with_existing_remote(self):
        self.create_resource()
        self.pcs_runner.corosync_conf_opt = None
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote server=node-addr --force".split(),
            stderr_full=(
                "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
            ),
        )
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        self.assert_pcs_fail(
            "cluster node add-guest R G remote-addr=a".split(),
            "Unable to check if there is a conflict with nodes set in corosync "
            "because the command does not run on a live cluster (e.g. -f "
            "was used)\n"
            "Error: Cannot set name of the guest node to 'R' because that ID "
            "already exists in the cluster configuration.\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_success(self):
        self.create_resource()
        self.assert_effect(
            "cluster node add-guest node-name G remote-addr=node-addr".split(),
            """<resources>
                <primitive class="ocf" id="G" provider="pcsmock" type="minimal">
                    <meta_attributes id="G-meta_attributes">
                        <nvpair id="G-meta_attributes-remote-addr"
                            name="remote-addr" value="node-addr"
                        />
                        <nvpair id="G-meta_attributes-remote-node"
                            name="remote-node" value="node-name"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="G-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
            stderr_full=fixture_nolive_add_report("node-name"),
        )

    def test_success_when_guest_node_matches_with_existing_guest(self):
        # This test belongs to pcs_test/tier0/test_resource.py as it tests
        # "resource update". But due to some fixtures it is more practical to
        # keep it here.
        self.create_resource()
        self.assert_pcs_success(
            "cluster node add-guest node-name G remote-addr=a".split(),
            stderr_full=fixture_nolive_add_report("node-name"),
        )
        self.pcs_runner.corosync_conf_opt = None
        self.assert_pcs_success(
            "resource update G meta remote-node=node-name".split()
        )

    def test_success_with_options(self):
        self.create_resource()
        self.assert_effect(
            (
                "cluster node add-guest node-name G remote-port=3121 "
                "remote-addr=node-addr remote-connect-timeout=80s"
            ).split(),
            """<resources>
                <primitive class="ocf" id="G" provider="pcsmock" type="minimal">
                    <meta_attributes id="G-meta_attributes">
                        <nvpair id="G-meta_attributes-remote-addr"
                            name="remote-addr" value="node-addr"
                        />
                        <nvpair id="G-meta_attributes-remote-connect-timeout"
                            name="remote-connect-timeout" value="80s"
                        />
                        <nvpair id="G-meta_attributes-remote-node"
                            name="remote-node" value="node-name"
                        />
                        <nvpair id="G-meta_attributes-remote-port"
                            name="remote-port" value="3121"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="G-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
            stderr_full=fixture_nolive_add_report("node-name"),
        )


class NodeDeleteRemoveRemote(RemoteTest):
    command = None

    def fixture_remote_node(self):
        self.pcs_runner.corosync_conf_opt = None
        self.assert_effect(
            (
                "resource create NODE-NAME ocf:pacemaker:remote "
                "server=NODE-HOST --no-default-ops --force"
            ).split(),
            """<resources>
                <primitive class="ocf" id="NODE-NAME" provider="pacemaker"
                    type="remote"
                >
                    <instance_attributes id="NODE-NAME-instance_attributes">
                        <nvpair id="NODE-NAME-instance_attributes-server"
                            name="server" value="NODE-HOST"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="NODE-NAME-monitor-interval-60s" interval="60s"
                            name="monitor" timeout="30s"
                        />
                    </operations>
                </primitive>
            </resources>""",
            stderr_full=(
                "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
            ),
        )
        self.pcs_runner.corosync_conf_opt = self.corosync_conf

    def fixture_multiple_remote_nodes(self):
        # bypass pcs validation mechanisms (including expected future
        # validation)
        write_data_to_tmpfile(
            """
            <cib epoch="557" num_updates="122" admin_epoch="0"
                validate-with="pacemaker-1.2" crm_feature_set="3.0.6"
                update-origin="rh7-3" update-client="crmd"
                cib-last-written="Thu Aug 23 16:49:17 2012"
                have-quorum="0" dc-uuid="2"
            >
              <configuration>
                <crm_config/>
                <nodes>
                </nodes>
                <resources>
                    <primitive class="ocf" id="NODE-NAME"
                        provider="pacemaker" type="remote"
                    >
                        <instance_attributes id="ia1">
                            <nvpair id="nvp1" name="server" value="HOST-A"/>
                        </instance_attributes>
                    </primitive>
                    <primitive class="ocf" id="HOST-A"
                        provider="pacemaker" type="remote"
                    >
                        <instance_attributes id="ia2">
                            <nvpair id="nvp2" name="server" value="HOST-B"/>
                        </instance_attributes>
                    </primitive>
                </resources>
                <constraints/>
              </configuration>
              <status/>
            </cib>
            """,
            self.temp_cib,
        )

    def _test_usage(self):
        self.assert_pcs_fail(
            ["cluster", "node", self.command],
            stderr_start=f"\nUsage: pcs cluster node {self.command}...",
        )

    def _test_fail_when_node_does_not_exists(self):
        self.assert_pcs_fail(
            ["cluster", "node", self.command, "not-existent"],
            NOT_STOPPING_RESOURCE_NOT_LIVE_CLUSTER
            + "Error: remote node 'not-existent' does not appear to exist in"
            " configuration\n" + ERRORS_HAVE_OCCURRED,
        )

    def _test_success_remove_by_host(self):
        self.fixture_remote_node()
        self.assert_effect(
            ["cluster", "node", self.command, "NODE-HOST"],
            "<resources/>",
            stderr_full=(
                NOT_STOPPING_RESOURCE_NOT_LIVE_CLUSTER
                + fixture_nolive_remove_remote_report(["NODE-NAME"])
                + "Removing resource: 'NODE-NAME'\n"
                + fixture_nolive_node_remove(["NODE-NAME"])
            ),
        )

    def _test_success_remove_by_node_name(self):
        self.fixture_remote_node()
        self.assert_effect(
            ["cluster", "node", self.command, "NODE-NAME"],
            "<resources/>",
            stderr_full=(
                NOT_STOPPING_RESOURCE_NOT_LIVE_CLUSTER
                + fixture_nolive_remove_remote_report(["NODE-NAME"])
                + "Removing resource: 'NODE-NAME'\n"
                + fixture_nolive_node_remove(["NODE-NAME"])
            ),
        )

    def _test_refuse_on_duplicit(self):
        self.fixture_multiple_remote_nodes()
        self.assert_pcs_fail(
            ["cluster", "node", self.command, "HOST-A"],
            NOT_STOPPING_RESOURCE_NOT_LIVE_CLUSTER
            + "Error: more than one resource for 'HOST-A' found: "
            "'HOST-A', 'NODE-NAME', use --force to override\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def _test_success_remove_multiple_nodes(self):
        self.fixture_multiple_remote_nodes()
        self.assert_effect(
            ["cluster", "node", self.command, "HOST-A", "--force"],
            "<resources/>",
            stderr_full=(
                NOT_STOPPING_RESOURCE_NOT_LIVE_CLUSTER
                + "Warning: more than one resource for 'HOST-A' found: "
                "'HOST-A', 'NODE-NAME'\n"
                + fixture_nolive_remove_remote_report(["HOST-A", "NODE-NAME"])
                + "Removing resources: 'HOST-A', 'NODE-NAME'\n"
                + fixture_nolive_node_remove(["HOST-A", "NODE-NAME"])
            ),
        )


class NodeDeleteRemote(
    NodeDeleteRemoveRemote, metaclass=ParametrizedTestMetaClass
):
    command = "delete-remote"


class NodeRemoveRemote(
    NodeDeleteRemoveRemote, metaclass=ParametrizedTestMetaClass
):
    command = "remove-remote"


class NodeDeleteRemoveGuest(RemoteTest):
    command = None

    def fixture_guest_node(self):
        self.pcs_runner.corosync_conf_opt = None
        self.assert_effect(
            (
                "resource create NODE-ID ocf:pcsmock:minimal --no-default-ops "
                "meta remote-node=NODE-NAME remote-addr=NODE-HOST --force"
            ).split(),
            """<resources>
                <primitive class="ocf" id="NODE-ID" provider="pcsmock"
                    type="minimal"
                >
                    <meta_attributes id="NODE-ID-meta_attributes">
                        <nvpair id="NODE-ID-meta_attributes-remote-addr"
                            name="remote-addr" value="NODE-HOST"
                        />
                        <nvpair id="NODE-ID-meta_attributes-remote-node"
                            name="remote-node" value="NODE-NAME"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="NODE-ID-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
            stderr_full=(
                "Warning: this command is not sufficient for creating a guest node"
                ", use 'pcs cluster node add-guest'\n"
            ),
        )
        self.pcs_runner.corosync_conf_opt = self.corosync_conf

    def _test_usage(self):
        self.assert_pcs_fail(
            ["cluster", "node", self.command],
            stderr_start=f"\nUsage: pcs cluster node {self.command}...",
        )

    def _test_fail_when_node_does_not_exists(self):
        self.assert_pcs_fail(
            ["cluster", "node", self.command, "not-existent", "--force"],
            "Error: guest node 'not-existent' does not appear to exist in"
            " configuration\n" + ERRORS_HAVE_OCCURRED,
        )

    def assert_remove_by_identifier(self, identifier):
        self.fixture_guest_node()
        self.assert_effect(
            ["cluster", "node", self.command, identifier],
            """<resources>
                <primitive class="ocf" id="NODE-ID" provider="pcsmock"
                    type="minimal"
                >
                    <meta_attributes id="NODE-ID-meta_attributes" />
                    <operations>
                        <op id="NODE-ID-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
            stderr_full=fixture_nolive_remove_guest_report(["NODE-NAME"])
            + fixture_nolive_node_remove(["NODE-NAME"]),
        )

    def _test_success_remove_by_node_name(self):
        self.assert_remove_by_identifier("NODE-NAME")

    def _test_success_remove_by_resource_id(self):
        self.assert_remove_by_identifier("NODE-ID")

    def _test_success_remove_by_resource_host(self):
        self.assert_remove_by_identifier("NODE-HOST")


class NodeDeleteGuest(
    NodeDeleteRemoveGuest, metaclass=ParametrizedTestMetaClass
):
    command = "delete-guest"


class NodeRemoveGuest(
    NodeDeleteRemoveGuest, metaclass=ParametrizedTestMetaClass
):
    command = "remove-guest"
