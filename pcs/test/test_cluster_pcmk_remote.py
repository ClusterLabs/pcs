from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.cib_resource.common import ResourceTest
from pcs.test.tools.misc import outdent

class NodeAddRemote(ResourceTest):
    def test_fail_on_duplicit_host_specification(self):
        self.assert_pcs_fail(
            "cluster node add-remote HOST remote-node server=DIFFERENT",
            "Error: An ambiguous host specification: 'HOST', 'DIFFERENT'\n"
        )

    def test_fail_on_duplicit_host_specification_without_name(self):
        self.assert_pcs_fail(
            "cluster node add-remote HOST server=DIFFERENT",
            "Error: An ambiguous host specification: 'HOST', 'DIFFERENT'\n"
        )

    def test_fail_on_bad_commandline_usage(self):
        self.assert_pcs_fail(
            "cluster node add-remote",
            stdout_start="\nUsage: pcs cluster node add-remote..."
        )

    def test_success(self):
        self.assert_effect(
            "cluster node add-remote node-host node-name",
            """<resources>
                <primitive class="ocf" id="node-name" provider="pacemaker"
                    type="remote"
                >
                    <instance_attributes id="node-name-instance_attributes">
                        <nvpair id="node-name-instance_attributes-server"
                            name="server" value="node-host"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="node-name-monitor-interval-60s" interval="60s"
                            name="monitor" timeout="30"
                        />
                        <op id="node-name-start-interval-0s" interval="0s"
                            name="start" timeout="60"
                        />
                        <op id="node-name-stop-interval-0s" interval="0s"
                            name="stop" timeout="60"
                        />
                    </operations>
                </primitive>
            </resources>""",
            output=outdent(
                """\
                The following actions were skipped because -f was used:
                  pacemaker authkey distribution
                  start pacemaker_remote on 'node-host'
                  enable pacemaker_remote on 'node-host'
                """
            )
        )

    def test_success_no_default_ops(self):
        self.assert_effect(
            "cluster node add-remote node-host node-name --no-default-ops",
            """<resources>
                <primitive class="ocf" id="node-name" provider="pacemaker"
                    type="remote"
                >
                    <instance_attributes id="node-name-instance_attributes">
                        <nvpair id="node-name-instance_attributes-server"
                            name="server" value="node-host"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="node-name-monitor-interval-60s" interval="60s"
                            name="monitor" timeout="30"
                        />
                    </operations>
                </primitive>
            </resources>""",
            output=outdent(
                """\
                The following actions were skipped because -f was used:
                  pacemaker authkey distribution
                  start pacemaker_remote on 'node-host'
                  enable pacemaker_remote on 'node-host'
                """
            )
        )

    def test_fail_when_server_already_used(self):
        self.assert_effect(
            "cluster node add-remote node-host A --no-default-ops",
            """<resources>
                <primitive class="ocf" id="A" provider="pacemaker"
                    type="remote"
                >
                    <instance_attributes id="A-instance_attributes">
                        <nvpair id="A-instance_attributes-server" name="server"
                            value="node-host"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="A-monitor-interval-60s" interval="60s"
                            name="monitor" timeout="30"
                        />
                    </operations>
                </primitive>
            </resources>""",
            output=outdent(
                """\
                The following actions were skipped because -f was used:
                  pacemaker authkey distribution
                  start pacemaker_remote on 'node-host'
                  enable pacemaker_remote on 'node-host'
                """
            )
        )
        self.assert_pcs_fail(
            "cluster node add-remote node-host B",
            "Error: 'node-host' already exists\n"
        )

    def test_fail_when_server_already_used_as_guest(self):
        self.assert_pcs_success(
            "resource create G ocf:heartbeat:Dummy --no-default-ops",
        )
        self.assert_pcs_success(
            "cluster node add-guest node-host G",
            outdent(
                """\
                The following actions were skipped because -f was used:
                  pacemaker authkey distribution
                  start pacemaker_remote on 'node-host'
                  enable pacemaker_remote on 'node-host'
                """
            )
        )
        self.assert_pcs_fail(
            "cluster node add-remote node-host B",
            "Error: 'node-host' already exists\n"
        )

class NodeAddGuest(ResourceTest):
    def create_resource(self):
        self.assert_effect(
            "resource create G ocf:heartbeat:Dummy --no-default-ops",
            """<resources>
                <primitive class="ocf" id="G" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="G-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_fail_on_bad_commandline_usage(self):
        self.assert_pcs_fail(
            "cluster node add-guest",
            stdout_start="\nUsage: pcs cluster node add-guest..."
        )

    def test_fail_when_resource_does_not_exists(self):
        self.assert_pcs_fail(
            "cluster node add-guest some-host non-existent",
            "Error: primitive 'non-existent' does not exist\n"
        )

    def test_fail_when_option_remote_node_specified(self):
        self.assert_pcs_fail(
            "cluster node add-guest some-host node-name remote-node=node-name",
            stdout_start="Error: option 'remote-node' is not allowed\n\n"
                "Usage: pcs cluster node add-guest..."
        )

    def test_fail_when_resource_has_already_remote_node_meta(self):
        self.assert_pcs_success(
            "resource create already-guest-node ocf:heartbeat:Dummy"
                " meta remote-node=some --force"
            ,
            "Warning: this command is not sufficient for create guest node, use"
                " 'pcs cluster node add-guest'\n"
        )
        self.assert_pcs_fail(
            "cluster node add-guest some-host already-guest-node",
            "Error: the resource 'already-guest-node' is already a guest node\n"
        )

    def test_fail_on_combined_reasons(self):
        self.assert_pcs_fail(
            "cluster node add-guest node-host G a=b",
            "Error: invalid guest options option 'a', allowed options are:"
                " remote-addr, remote-connect-timeout, remote-port\n"
                "Error: primitive 'G' does not exist\n"
        )

    def test_fail_when_disallowed_option_appear(self):
        self.create_resource()
        self.assert_pcs_fail(
            "cluster node add-guest node-host G a=b",
            "Error: invalid guest options option 'a', allowed options are:"
                " remote-addr, remote-connect-timeout, remote-port\n"
        )

    def test_fail_when_invalid_interval_appear(self):
        self.create_resource()
        self.assert_pcs_fail(
            "cluster node add-guest node-host G remote-connect-timeout=A",
            "Error: 'A' is not a valid remote-connect-timeout value, use time"
                " interval (e.g. 1, 2s, 3m, 4h, ...)\n"
        )

    def test_fail_when_guest_node_conflicts_with_existing_id(self):
        self.create_resource()
        self.assert_pcs_success("resource create CONFLICT ocf:heartbeat:Dummy")
        self.assert_pcs_fail(
            "cluster node add-guest CONFLICT G",
            "Error: 'CONFLICT' already exists\n"
        )

    def test_fail_when_guest_node_conflicts_with_existing_guest(self):
        self.create_resource()
        self.assert_pcs_success("resource create H ocf:heartbeat:Dummy")
        self.assert_pcs_success(
            "cluster node add-guest node-host G",
            outdent(
                """\
                The following actions were skipped because -f was used:
                  pacemaker authkey distribution
                  start pacemaker_remote on 'node-host'
                  enable pacemaker_remote on 'node-host'
                """
            )
        )
        self.assert_pcs_fail(
            "cluster node add-guest node-host H",
            "Error: 'node-host' already exists\n"
        )

    def test_fail_when_guest_node_conflicts_with_existing_remote(self):
        self.create_resource()
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote server=node-host --force",
            "Warning: this command is not sufficient for create remote"
                " connection, use 'pcs cluster node add-remote'\n"
        )
        self.assert_pcs_fail(
            "cluster node add-guest node-host G",
            "Error: 'node-host' already exists\n"
        )

    def test_fail_when_guest_node_name_conflicts_with_existing_remote(self):
        self.create_resource()
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote server=node-host --force",
            "Warning: this command is not sufficient for create remote"
                " connection, use 'pcs cluster node add-remote'\n"
        )
        self.assert_pcs_fail(
            "cluster node add-guest another-host R",
            "Error: 'R' already exists\n"
        )

    def test_success(self):
        self.create_resource()
        self.assert_effect(
            "cluster node add-guest node-host G",
            """<resources>
                <primitive class="ocf" id="G" provider="heartbeat" type="Dummy">
                    <meta_attributes id="G-meta_attributes">
                        <nvpair id="G-meta_attributes-remote-node"
                            name="remote-node" value="node-host"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="G-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>""",
            output=outdent(
                """\
                The following actions were skipped because -f was used:
                  pacemaker authkey distribution
                  start pacemaker_remote on 'node-host'
                  enable pacemaker_remote on 'node-host'
                """
            )
        )

    def test_success_with_options(self):
        self.create_resource()
        self.assert_effect(
            "cluster node add-guest node-name G remote-port=3121"
                " remote-addr=node-host remote-connect-timeout=80s"
            ,
            """<resources>
                <primitive class="ocf" id="G" provider="heartbeat" type="Dummy">
                    <meta_attributes id="G-meta_attributes">
                        <nvpair id="G-meta_attributes-remote-addr"
                            name="remote-addr" value="node-host"
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
                        <op id="G-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>""",
            output=outdent(
                """\
                The following actions were skipped because -f was used:
                  pacemaker authkey distribution
                  start pacemaker_remote on 'node-host'
                  enable pacemaker_remote on 'node-host'
                """
            )
        )

class NodeRemoveRemote(ResourceTest):
    def test_fail_when_node_does_not_exists(self):
        self.assert_pcs_fail(
            "cluster node remove-remote not-existent",
            "Error: remote node 'not-existent' does not appear to exist in"
                " configuration\n"
        )

    def fixture_remote_node(self):
        self.assert_effect(
            "resource create NODE-NAME ocf:pacemaker:remote server=NODE-HOST"
                " --no-default-ops --force"
            ,
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
                            name="monitor" timeout="30"
                        />
                    </operations>
                </primitive>
            </resources>"""
            ,
            "Warning: this command is not sufficient for create remote"
                " connection, use 'pcs cluster node add-remote'\n"
        )

    def fixture_multiple_remote_nodes(self):
        #bypass pcs validation mechanisms (including expected future validation)
        temp_cib = open(self.temp_cib, "w")
        temp_cib.write("""
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
        """)
        temp_cib.close()

    def test_success_remove_by_host(self):
        self.fixture_remote_node()
        self.assert_effect(
            "cluster node remove-remote NODE-HOST",
            "<resources/>",
            outdent(
                """\
                Deleting Resource - NODE-NAME
                The following actions were skipped because -f was used:
                  pacemaker_remote authkey remove
                  stop pacemaker_remote on 'NODE-HOST'
                  disable pacemaker_remote on 'NODE-HOST'
                """
            )
        )

    def test_success_remove_by_node_name(self):
        self.fixture_remote_node()
        self.assert_effect(
            "cluster node remove-remote NODE-NAME",
            "<resources/>",
            outdent(
                """\
                Deleting Resource - NODE-NAME
                The following actions were skipped because -f was used:
                  pacemaker_remote authkey remove
                  stop pacemaker_remote on 'NODE-HOST'
                  disable pacemaker_remote on 'NODE-HOST'
                """
            )
        )

    def test_refuse_on_duplicit(self):
        self.fixture_multiple_remote_nodes()
        self.assert_pcs_fail(
            "cluster node remove-remote HOST-A", #
            "Error: multiple resource for 'HOST-A' found: "
                "'NODE-NAME', 'HOST-A', use --force to override\n"
        )

    def test_success_remove_multiple_nodes(self):
        self.fixture_multiple_remote_nodes()
        self.assert_effect(
            "cluster node remove-remote HOST-A --force",
            "<resources/>",
            outdent(
                """\
                Warning: multiple resource for 'HOST-A' found: 'NODE-NAME', 'HOST-A'
                Deleting Resource - NODE-NAME
                Deleting Resource - HOST-A
                The following actions were skipped because -f was used:
                  pacemaker_remote authkey remove
                  stop pacemaker_remote on 'HOST-A', 'HOST-B'
                  disable pacemaker_remote on 'HOST-A', 'HOST-B'
                """
            )
        )

class NodeRemoveGuest(ResourceTest):
    def fixture_guest_node(self):
        self.assert_effect(
            "resource create NODE-ID ocf:heartbeat:Dummy --no-default-ops"
                " meta remote-node=NODE-NAME remote-addr=NODE-HOST --force"
            ,
            """<resources>
                <primitive class="ocf" id="NODE-ID" provider="heartbeat"
                    type="Dummy"
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
                        <op id="NODE-ID-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>""",
            "Warning: this command is not sufficient for create guest node, use"
                " 'pcs cluster node add-guest'\n"
        )

    def test_fail_when_node_does_not_exists(self):
        self.assert_pcs_fail(
            "cluster node remove-guest not-existent --force",
            "Error: guest node 'not-existent' does not appear to exist in"
                " configuration\n"
        )

    def assert_remove_by_identifier(self, identifier):
        self.fixture_guest_node()
        self.assert_effect(
            "cluster node remove-guest {0}".format(identifier),
            """<resources>
                <primitive class="ocf" id="NODE-ID" provider="heartbeat"
                    type="Dummy"
                >
                    <operations>
                        <op id="NODE-ID-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>""",
            outdent(
                """\
                The following actions were skipped because -f was used:
                  pacemaker_remote authkey remove
                  stop pacemaker_remote on 'NODE-HOST'
                  disable pacemaker_remote on 'NODE-HOST'
                """
            )
        )

    def test_success_remove_by_node_name(self):
        self.assert_remove_by_identifier("NODE-NAME")

    def test_success_remove_by_resource_id(self):
        self.assert_remove_by_identifier("NODE-ID")

    def test_success_remove_by_resource_host(self):
        self.assert_remove_by_identifier("NODE-HOST")
