from unittest import (
    TestCase,
    mock,
)

from pcs import resource
from pcs.cli.common.parse_args import InputModifiers
from pcs.common import const
from pcs.common.str_tools import format_list

from pcs_test.tier1.cib_resource.common import ResourceTest
from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.pcs_runner import PcsRunner

# pylint: disable=too-many-lines

ERRORS_HAVE_OCCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)


class Success(ResourceTest):
    msg_clone_without_meta = (
        "Deprecation Warning: Configuring clone meta attributes without "
        "specifying the 'meta' keyword after the 'clone' keyword is deprecated "
        "and will be removed in a future release. Specify --future to switch "
        "to the future behavior.\n"
    )

    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_base_create(self):
        self.assert_effect(
            "resource create R ocf:pcsmock:minimal --no-default-ops".split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_base_create_with_agent_name_including_systemd_instance(self):
        # crm_resource returns the same metadata for any systemd resource, no
        # matter if it exists or not
        self.assert_effect(
            "resource create R systemd:pcsmock@a:b --no-default-ops".split(),
            """<resources>
                <primitive class="systemd" id="R" type="pcsmock@a:b">
                    <operations>
                        <op id="R-monitor-interval-60s" interval="60s"
                            name="monitor" timeout="100s"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_base_create_with_default_ops(self):
        self.assert_effect(
            "resource create R ocf:pcsmock:minimal".split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-migrate_from-interval-0s" interval="0s"
                            name="migrate_from" timeout="20s"
                        />
                        <op id="R-migrate_to-interval-0s" interval="0s"
                            name="migrate_to" timeout="20s"
                        />
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                        <op id="R-reload-interval-0s" interval="0s"
                            name="reload" timeout="20s"
                        />
                        <op id="R-reload-agent-interval-0s" interval="0s"
                            name="reload-agent" timeout="20s"
                        />
                        <op id="R-start-interval-0s" interval="0s" name="start"
                            timeout="20s"
                        />
                        <op id="R-stop-interval-0s" interval="0s" name="stop"
                            timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_create_with_options(self):
        self.assert_effect(
            (
                "resource create --no-default-ops R ocf:pcsmock:params "
                "mandatory=mandat optional=opti"
            ).split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="params">
                    <instance_attributes id="R-instance_attributes">
                        <nvpair id="R-instance_attributes-mandatory"
                            name="mandatory" value="mandat"
                        />
                        <nvpair id="R-instance_attributes-optional"
                            name="optional" value="opti"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_create_with_trace_options(self):
        # trace_ra and trace_file options are not defined in metadata but they
        # are allowed for all ocf:heartbeat and ocf:pacemaker agents. This test
        # checks it is possible to set them without --force.
        self.assert_effect(
            (
                "resource create --no-default-ops R ocf:heartbeat:pcsMock "
                "trace_ra=1 trace_file=/root/trace"
            ).split(),
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat"
                    type="pcsMock"
                >
                    <instance_attributes id="R-instance_attributes">
                        <nvpair id="R-instance_attributes-trace_file"
                            name="trace_file" value="/root/trace"
                        />
                        <nvpair id="R-instance_attributes-trace_ra"
                            name="trace_ra" value="1"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_create_with_options_and_operations(self):
        self.assert_effect(
            (
                "resource create --no-default-ops R ocf:pcsmock:params "
                "mandatory=mandat optional=opti op monitor interval=30s"
            ).split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="params">
                    <instance_attributes id="R-instance_attributes">
                        <nvpair id="R-instance_attributes-mandatory"
                            name="mandatory" value="mandat"
                        />
                        <nvpair id="R-instance_attributes-optional"
                            name="optional" value="opti"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="R-monitor-interval-30s" interval="30s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_create_disabled(self):
        self.assert_effect(
            (
                "resource create R ocf:pcsmock:minimal --no-default-ops "
                "--disabled"
            ).split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <meta_attributes id="R-meta_attributes">
                        <nvpair id="R-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_with_clone(self):
        self.assert_effect(
            "resource create R ocf:pcsmock:minimal --no-default-ops clone".split(),
            """<resources>
                <clone id="R-clone">
                    <primitive class="ocf" id="R" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="R-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                </clone>
            </resources>""",
        )

    def test_with_custom_clone_id(self):
        self.assert_effect(
            (
                "resource create R ocf:pcsmock:minimal --no-default-ops clone "
                "CustomId"
            ).split(),
            """<resources>
                <clone id="CustomId">
                    <primitive class="ocf" id="R" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="R-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                </clone>
            </resources>""",
        )

    def test_with_clone_options(self):
        self.assert_effect(
            (
                "resource create R ocf:pcsmock:minimal --no-default-ops clone "
                "notify=true"
            ).split(),
            """<resources>
                <clone id="R-clone">
                    <primitive class="ocf" id="R" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="R-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                    <meta_attributes id="R-clone-meta_attributes">
                        <nvpair id="R-clone-meta_attributes-notify"
                            name="notify" value="true"
                        />
                    </meta_attributes>
                </clone>
            </resources>""",
            stderr_full=self.msg_clone_without_meta,
        )

    def test_create_with_options_and_meta(self):
        self.assert_effect(
            (
                "resource create --no-default-ops R ocf:pcsmock:params "
                "mandatory=mandat optional=opti meta is-managed=false"
            ).split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="params">
                    <instance_attributes id="R-instance_attributes">
                        <nvpair id="R-instance_attributes-mandatory"
                            name="mandatory" value="mandat"
                        />
                        <nvpair id="R-instance_attributes-optional"
                            name="optional" value="opti"
                        />
                    </instance_attributes>
                    <meta_attributes id="R-meta_attributes">
                        <nvpair id="R-meta_attributes-is-managed"
                            name="is-managed" value="false"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )


class SuccessOperations(ResourceTest):
    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_create_with_operations(self):
        self.assert_effect(
            (
                "resource create --no-default-ops R ocf:pcsmock:minimal "
                "op monitor interval=30s"
            ).split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-monitor-interval-30s" interval="30s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_multiple_op_keyword(self):
        self.assert_effect(
            (
                "resource create R ocf:pcsmock:minimal --no-default-ops "
                "op monitor interval=30s op monitor interval=20s"
            ).split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-monitor-interval-30s" interval="30s"
                            name="monitor"
                        />
                        <op id="R-monitor-interval-20s" interval="20s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_multiple_operations_same_op_keyword(self):
        self.assert_effect(
            (
                "resource create R ocf:pcsmock:minimal --no-default-ops "
                "op monitor interval=30s monitor interval=20s"
            ).split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-monitor-interval-30s" interval="30s"
                            name="monitor"
                        />
                        <op id="R-monitor-interval-20s" interval="20s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_multiple_op_options_for_same_action(self):
        self.assert_effect(
            (
                "resource create R ocf:pcsmock:minimal --no-default-ops "
                "op monitor interval=30s timeout=20s"
            ).split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-monitor-interval-30s" interval="30s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_op_with_OCF_CHECK_LEVEL(self):
        # pylint: disable=invalid-name
        self.assert_effect(
            (
                "resource create R ocf:pcsmock:minimal --no-default-ops "
                "op monitor interval=30s timeout=20s OCF_CHECK_LEVEL=1"
            ).split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-monitor-interval-30s" interval="30s"
                            name="monitor" timeout="20s"
                        >
                            <instance_attributes
                                id="R-monitor-interval-30s-instance_attributes"
                            >
                                <nvpair
                                    id="R-monitor-interval-30s-"""
            + 'instance_attributes-OCF_CHECK_LEVEL"'
            + """
                                    name="OCF_CHECK_LEVEL" value="1"
                                />
                            </instance_attributes>
                        </op>
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_default_ops_only(self):
        self.assert_effect(
            "resource create R ocf:pcsmock:minimal".split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-migrate_from-interval-0s" interval="0s"
                            name="migrate_from" timeout="20s"
                        />
                        <op id="R-migrate_to-interval-0s" interval="0s"
                            name="migrate_to" timeout="20s"
                        />
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                        <op id="R-reload-interval-0s" interval="0s"
                            name="reload" timeout="20s"
                        />
                        <op id="R-reload-agent-interval-0s" interval="0s"
                            name="reload-agent" timeout="20s"
                        />
                        <op id="R-start-interval-0s" interval="0s" name="start"
                            timeout="20s"
                        />
                        <op id="R-stop-interval-0s" interval="0s" name="stop"
                            timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_merging_default_ops_explicitly_specified(self):
        self.assert_effect(
            "resource create R ocf:pcsmock:minimal op start timeout=200".split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-migrate_from-interval-0s" interval="0s"
                            name="migrate_from" timeout="20s"
                        />
                        <op id="R-migrate_to-interval-0s" interval="0s"
                            name="migrate_to" timeout="20s"
                        />
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                        <op id="R-reload-interval-0s" interval="0s"
                            name="reload" timeout="20s"
                        />
                        <op id="R-reload-agent-interval-0s" interval="0s"
                            name="reload-agent" timeout="20s"
                        />
                        <op id="R-start-interval-0s" interval="0s" name="start"
                            timeout="200"
                        />
                        <op id="R-stop-interval-0s" interval="0s" name="stop"
                            timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_completing_monitor_operation(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:pcsmock:minimal".split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_adapt_second_op_interval(self):
        self.assert_effect(
            "resource create R ocf:pcsmock:duplicate_monitor".split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock"
                    type="duplicate_monitor"
                >
                    <operations>
                        <op id="R-demote-interval-0s" interval="0s"
                            name="demote" timeout="10s"
                        />
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" role="Master" timeout="20s"
                        />
                        <op id="R-monitor-interval-11" interval="11"
                            name="monitor" role="Slave" timeout="20s"
                        />
                        <op id="R-notify-interval-0s" interval="0s"
                            name="notify" timeout="5s"
                        />
                        <op id="R-promote-interval-0s" interval="0s"
                            name="promote" timeout="10s"
                        />
                        <op id="R-reload-agent-interval-0s" interval="0s"
                            name="reload-agent" timeout="10s"
                        />
                        <op id="R-start-interval-0s" interval="0s" name="start"
                            timeout="20s"
                        />
                        <op id="R-stop-interval-0s" interval="0s" name="stop"
                            timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
            stderr_full=(
                "Warning: changing a monitor operation interval from 10s to 11 to"
                " make the operation unique\n"
            ),
        )

    def test_warn_on_forced_unknown_operation(self):
        self.assert_effect(
            (
                "resource create --no-default-ops R ocf:pcsmock:minimal "
                "op monitro interval=30s --force"
            ).split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                        <op id="R-monitro-interval-30s" interval="30s"
                            name="monitro"
                        />
                    </operations>
                </primitive>
            </resources>""",
            stderr_full=(
                "Warning: 'monitro' is not a valid operation name value, use "
                "'meta-data', 'migrate_from', 'migrate_to', 'monitor', "
                "'reload', 'reload-agent', 'start', 'stop', 'validate-all'\n"
            ),
        )

    def test_op_id(self):
        self.assert_effect(
            (
                "resource create --no-default-ops R ocf:pcsmock:minimal "
                "op monitor interval=30s id=abcd"
            ).split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="abcd" interval="30s" name="monitor" />
                    </operations>
                </primitive>
            </resources>""",
        )


class SuccessNewParser(ResourceTest):
    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_primitive_meta(self):
        self.assert_effect(
            "resource create R ocf:pcsmock:minimal meta a=b --no-default-ops --future".split(),
            """<resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                    <meta_attributes id="R-meta_attributes">
                        <nvpair id="R-meta_attributes-a" name="a" value="b"/>
                    </meta_attributes>
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_clone_meta(self):
        self.assert_effect(
            "resource create R ocf:pcsmock:minimal clone meta a=b --no-default-ops --future".split(),
            """<resources>
                <clone id="R-clone">
                    <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                        <operations>
                            <op id="R-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                    <meta_attributes id="R-clone-meta_attributes">
                        <nvpair id="R-clone-meta_attributes-a" name="a" value="b"/>
                    </meta_attributes>
                </clone>
            </resources>""",
        )

    def test_primitive_and_clone_meta(self):
        self.assert_effect(
            "resource create R ocf:pcsmock:minimal meta a=b clone meta c=d --no-default-ops --future".split(),
            """<resources>
                <clone id="R-clone">
                    <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                        <meta_attributes id="R-meta_attributes">
                            <nvpair id="R-meta_attributes-a" name="a" value="b"/>
                        </meta_attributes>
                        <operations>
                            <op id="R-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                    <meta_attributes id="R-clone-meta_attributes">
                        <nvpair id="R-clone-meta_attributes-c" name="c" value="d"/>
                    </meta_attributes>
                </clone>
            </resources>""",
        )


class SuccessGroup(ResourceTest):
    FUTURE = ""
    GROUP = "--group"
    AFTER = "--after"
    BEFORE = "--before"
    DEPRECATED_GROUP = (
        "Deprecation Warning: Using '--group' is deprecated and will be "
        "replaced with 'group' in a future release. Specify --future to switch "
        "to the future behavior.\n"
    )
    DEPRECATED_AFTER = (
        "Deprecation Warning: Using '--after' is deprecated and will be "
        "replaced with 'after' in a future release. Specify --future to switch "
        "to the future behavior.\n"
    )
    DEPRECATED_BEFORE = (
        "Deprecation Warning: Using '--before' is deprecated and will be "
        "replaced with 'before' in a future release. Specify --future to switch "
        "to the future behavior.\n"
    )

    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_with_group(self):
        self.assert_effect(
            (
                "resource create R ocf:pcsmock:minimal --no-default-ops "
                f"{self.GROUP} G {self.FUTURE}"
            ).split(),
            """<resources>
                <group id="G">
                    <primitive class="ocf" id="R" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="R-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>""",
            stderr_full=self.DEPRECATED_GROUP,
        )

    def test_with_existing_group(self):
        self.assert_pcs_success(
            (
                "resource create R0 ocf:pcsmock:minimal --no-default-ops "
                f"{self.GROUP} G {self.FUTURE}"
            ).split(),
            stderr_full=self.DEPRECATED_GROUP,
        )
        self.assert_effect(
            (
                "resource create R ocf:pcsmock:minimal --no-default-ops "
                f"{self.GROUP} G {self.FUTURE}"
            ).split(),
            """<resources>
                <group id="G">
                    <primitive class="ocf" id="R0" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="R0-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                    <primitive class="ocf" id="R" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="R-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>""",
            stderr_full=self.DEPRECATED_GROUP,
        )

    def test_with_group_with_after(self):
        self.assert_pcs_success(
            (
                "resource create R0 ocf:pcsmock:minimal --no-default-ops "
                f"{self.GROUP} G {self.FUTURE}"
            ).split(),
            stderr_full=self.DEPRECATED_GROUP,
        )
        self.assert_pcs_success(
            (
                "resource create R1 ocf:pcsmock:minimal --no-default-ops "
                f"{self.GROUP} G {self.FUTURE}"
            ).split(),
            stderr_full=self.DEPRECATED_GROUP,
        )
        self.assert_effect(
            (
                "resource create R ocf:pcsmock:minimal --no-default-ops "
                f"{self.GROUP} G {self.AFTER} R0 {self.FUTURE}"
            ).split(),
            """<resources>
                <group id="G">
                    <primitive class="ocf" id="R0" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="R0-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                    <primitive class="ocf" id="R" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="R-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                    <primitive class="ocf" id="R1" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="R1-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>""",
            stderr_full=self.DEPRECATED_GROUP + self.DEPRECATED_AFTER,
        )
        self.assert_effect(
            (
                "resource create Rx ocf:pcsmock:minimal --no-default-ops "
                f"{self.GROUP} G {self.AFTER} R1 {self.FUTURE}"
            ).split(),
            """<resources>
                <group id="G">
                    <primitive class="ocf" id="R0" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="R0-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                    <primitive class="ocf" id="R" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="R-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                    <primitive class="ocf" id="R1" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="R1-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                    <primitive class="ocf" id="Rx" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="Rx-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>""",
            stderr_full=self.DEPRECATED_GROUP + self.DEPRECATED_AFTER,
        )

    def test_with_group_with_before(self):
        self.assert_pcs_success(
            (
                "resource create R0 ocf:pcsmock:minimal --no-default-ops "
                f"{self.GROUP} G {self.FUTURE}"
            ).split(),
            stderr_full=self.DEPRECATED_GROUP,
        )
        self.assert_effect(
            (
                "resource create R ocf:pcsmock:minimal --no-default-ops "
                f"{self.GROUP} G {self.BEFORE} R0 {self.FUTURE}"
            ).split(),
            """<resources>
                <group id="G">
                    <primitive class="ocf" id="R" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="R-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                    <primitive class="ocf" id="R0" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="R0-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>""",
            stderr_full=self.DEPRECATED_GROUP + self.DEPRECATED_BEFORE,
        )


class SuccessGroupFuture(SuccessGroup):
    FUTURE = "--future"
    GROUP = "group"
    AFTER = "after"
    BEFORE = "before"
    DEPRECATED_GROUP = DEPRECATED_AFTER = DEPRECATED_BEFORE = ""


class SuccessClone(ResourceTest):
    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_clone_places_disabled_correctly(self):
        self.assert_effect(
            "resource create R ocf:pcsmock:minimal clone --disabled".split(),
            """<resources>
                <clone id="R-clone">
                    <meta_attributes id="R-clone-meta_attributes">
                        <nvpair id="R-clone-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                    <primitive class="ocf" id="R" provider="pcsmock"
                        type="minimal"
                    >
                        <operations>
                            <op id="R-migrate_from-interval-0s" interval="0s"
                                name="migrate_from" timeout="20s"
                            />
                            <op id="R-migrate_to-interval-0s" interval="0s"
                                name="migrate_to" timeout="20s"
                            />
                            <op id="R-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                            <op id="R-reload-interval-0s" interval="0s"
                                name="reload" timeout="20s"
                            />
                            <op id="R-reload-agent-interval-0s" interval="0s"
                                name="reload-agent" timeout="20s"
                            />
                            <op id="R-start-interval-0s" interval="0s"
                                name="start" timeout="20s"
                            />
                            <op id="R-stop-interval-0s" interval="0s"
                                name="stop" timeout="20s"
                            />
                        </operations>
                    </primitive>
                </clone>
            </resources>""",
        )


class Promotable(TestCase, AssertPcsMixin):
    msg_promotable_without_meta = (
        "Deprecation Warning: Configuring promotable meta attributes without "
        "specifying the 'meta' keyword after the 'promotable' keyword is deprecated "
        "and will be removed in a future release. Specify --future to switch "
        "to the future behavior.\n"
    )

    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource"])
        self.resource = mock.Mock(spec_set=["create_as_clone"])
        self.lib.resource = self.resource
        # used for tests where code does not even call lib, so cib is not needed
        self.pcs_runner = PcsRunner(cib_file=None)
        self.pcs_runner.mock_settings = get_mock_settings()

    @staticmethod
    def fixture_options(
        *,
        allow_absent_agent=False,
        allow_invalid_instance_attributes=False,
        allow_invalid_operation=False,
        allow_not_suitable_command=False,
        ensure_disabled=False,
        use_default_operations=True,
        wait=False,
        enable_agent_self_validation=False,
    ):
        # pylint: disable=unused-argument
        return locals()

    @mock.patch("pcs.cli.reports.output.print_to_stderr")
    def test_alias_for_clone(self, mock_print_to_stderr):
        resource.resource_create(
            self.lib,
            ["R", "ocf:pcsmock:stateful", "promotable", "a=b", "c=d"],
            InputModifiers({}),
        )
        self.resource.create_as_clone.assert_called_once_with(
            "R",
            "ocf:pcsmock:stateful",
            [],
            {},
            {},
            {"a": "b", "c": "d", "promotable": "true"},
            clone_id=None,
            allow_incompatible_clone_meta_attributes=False,
            **self.fixture_options(),
        )
        mock_print_to_stderr.assert_called_once_with(
            "Deprecation Warning: Configuring promotable meta attributes "
            "without specifying the 'meta' keyword after the 'promotable' "
            "keyword is deprecated and will be removed in a future release. "
            "Specify --future to switch to the future behavior."
        )

    def test_fail_on_promotable(self):
        self.assert_pcs_fail(
            (
                "resource create R ocf:pcsmock:stateful promotable promotable=a"
            ).split(),
            (
                self.msg_promotable_without_meta
                + "Error: you cannot specify both promotable option and promotable "
                "keyword\n"
            ),
        )

    def test_fail_on_promotable_true(self):
        self.assert_pcs_fail(
            (
                "resource create R ocf:pcsmock:stateful promotable "
                "promotable=true"
            ).split(),
            (
                self.msg_promotable_without_meta
                + "Error: you cannot specify both promotable option and promotable "
                "keyword\n"
            ),
        )

    def test_fail_on_promotable_false(self):
        self.assert_pcs_fail(
            (
                "resource create R ocf:pcsmock:stateful promotable "
                "promotable=false"
            ).split(),
            (
                self.msg_promotable_without_meta
                + "Error: you cannot specify both promotable option and promotable "
                "keyword\n"
            ),
        )


class Bundle(ResourceTest):
    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def fixture_primitive(self, name, bundle=None):
        if bundle:
            self.assert_pcs_success(
                [
                    "resource",
                    "create",
                    name,
                    "ocf:pcsmock:minimal",
                    "bundle",
                    bundle,
                ]
            )
        else:
            self.assert_pcs_success(
                ["resource", "create", name, "ocf:pcsmock:minimal"]
            )

    def fixture_bundle(self, name):
        self.assert_pcs_success(
            [
                "resource",
                "bundle",
                "create",
                name,
                "container",
                "docker",
                "image=pcs:test",
                "network",
                "control-port=1234",
            ],
        )

    def test_bundle_id_not_specified(self):
        self.assert_pcs_fail(
            "resource create R ocf:pcsmock:minimal --no-default-ops bundle".split(),
            "Error: you have to specify exactly one bundle\n",
        )

    def test_bundle_id_is_not_bundle(self):
        self.fixture_primitive("R1")
        self.assert_pcs_fail(
            "resource create R2 ocf:pcsmock:minimal bundle R1".split(),
            "Error: 'R1' is not a bundle\n",
        )

    def test_bundle_id_does_not_exist(self):
        self.assert_pcs_fail(
            "resource create R1 ocf:pcsmock:minimal bundle B".split(),
            "Error: bundle 'B' does not exist\n",
        )

    def test_primitive_already_in_bundle(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R1", bundle="B")
        self.assert_pcs_fail(
            (
                "resource create R2 ocf:pcsmock:minimal --no-default-ops "
                "bundle B"
            ).split(),
            (
                "Error: bundle 'B' already contains resource 'R1', a bundle "
                "may contain at most one resource\n"
            ),
        )

    def test_success(self):
        self.fixture_bundle("B")
        self.assert_effect(
            (
                "resource create R1 ocf:pcsmock:minimal --no-default-ops "
                "bundle B"
            ).split(),
            """
                <resources>
                    <bundle id="B">
                        <docker image="pcs:test" />
                        <network control-port="1234"/>
                        <primitive class="ocf" id="R1" provider="pcsmock"
                            type="minimal"
                        >
                            <operations>
                                <op id="R1-monitor-interval-10s" interval="10s"
                                    name="monitor" timeout="20s"
                                />
                            </operations>
                        </primitive>
                    </bundle>
                </resources>
            """,
        )


class FailOrWarnGroupCloneBundleCombination(ResourceTest):
    FUTURE = ""
    GROUP = "--group"
    AFTER = "--after"
    BEFORE = "--before"
    DEPRECATED_GROUP = (
        "Deprecation Warning: Using '--group' is deprecated and will be "
        "replaced with 'group' in a future release. Specify --future to switch "
        "to the future behavior.\n"
    )

    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_error_group_clone_combination(self):
        self.assert_pcs_fail(
            (
                "resource create R ocf:pcsmock:minimal --no-default-ops "
                f"clone {self.GROUP} G {self.FUTURE}"
            ).split(),
            (
                self.DEPRECATED_GROUP
                + "Error: you can specify only one of clone, promotable, bundle "
                f"or {self.GROUP}\n"
            ),
        )

    def test_error_bundle_clone_combination(self):
        self.assert_pcs_fail(
            (
                "resource create R ocf:pcsmock:minimal --no-default-ops "
                f"clone bundle bundle_id {self.FUTURE}"
            ).split(),
            (
                "Error: you can specify only one of clone, promotable, bundle "
                f"or {self.GROUP}\n"
            ),
        )

    def test_error_bundle_group_combination(self):
        self.assert_pcs_fail(
            (
                "resource create R ocf:pcsmock:minimal --no-default-ops "
                f"{self.GROUP} G bundle bundle_id {self.FUTURE}"
            ).split(),
            (
                self.DEPRECATED_GROUP
                + "Error: you can specify only one of clone, promotable, bundle "
                f"or {self.GROUP}\n"
            ),
        )


class FailOrWarnGroupCloneBundleCombinationFuture(
    FailOrWarnGroupCloneBundleCombination
):
    FUTURE = "--future"
    GROUP = "group"
    AFTER = "after"
    BEFORE = "before"
    DEPRECATED_GROUP = ""


class FailOrWarn(ResourceTest):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_fail_when_nonexisting_agent(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat:NoExisting".split(),
            stderr_full=(
                "Error: Agent 'ocf:heartbeat:NoExisting' is not installed or "
                "does not provide valid metadata: "
                "pcs mock error message: unable to load agent metadata, "
                "use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_warn_when_forcing_noexistent_agent(self):
        self.assert_effect(
            "resource create R ocf:heartbeat:NoExisting --force".split(),
            """<resources>
                <primitive class="ocf" id="R" provider="heartbeat"
                    type="NoExisting"
                >
                    <operations>
                        <op id="R-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
            stderr_full=(
                "Warning: Agent 'ocf:heartbeat:NoExisting' is not installed or "
                "does not provide valid metadata: "
                "pcs mock error message: unable to load agent metadata\n"
            ),
        )

    def test_fail_on_invalid_resource_agent_name(self):
        self.assert_pcs_fail(
            "resource create R invalid_agent_name".split(),
            "Error: Unable to find agent 'invalid_agent_name', try specifying"
            " its full name\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_on_invalid_resource_agent_name_even_if_forced(self):
        self.assert_pcs_fail(
            "resource create R invalid_agent_name --force".split(),
            "Error: Unable to find agent 'invalid_agent_name', try specifying"
            " its full name\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_when_invalid_agent(self):
        self.assert_pcs_fail(
            "resource create R ocf:heartbeat: --force".split(),
            "Error: Invalid resource agent name 'ocf:heartbeat:'. Use"
            " standard:provider:type when standard is 'ocf' or"
            " standard:type otherwise. List of standards and providers can"
            " be obtained by using commands 'pcs resource standards' and"
            " 'pcs resource providers'.\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_vail_when_agent_class_is_not_allowed(self):
        self.assert_pcs_fail(
            "resource create R invalid:Dummy --force".split(),
            "Error: Invalid resource agent name 'invalid:Dummy'. Use"
            " standard:provider:type when standard is 'ocf' or"
            " standard:type otherwise. List of standards and providers can"
            " be obtained by using commands 'pcs resource standards' and"
            " 'pcs resource providers'.\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_when_missing_provider_with_ocf_resource_agent(self):
        self.assert_pcs_fail(
            "resource create R ocf:Dummy".split(),
            "Error: Invalid resource agent name 'ocf:Dummy'. Use"
            " standard:provider:type when standard is 'ocf' or"
            " standard:type otherwise. List of standards and providers can"
            " be obtained by using commands 'pcs resource standards' and"
            " 'pcs resource providers'.\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_when_provider_appear_with_non_ocf_resource_agent(self):
        self.assert_pcs_fail(
            "resource create R lsb:provider:Dummy --force".split(),
            "Error: Invalid resource agent name 'lsb:provider:Dummy'. Use"
            " standard:provider:type when standard is 'ocf' or"
            " standard:type otherwise. List of standards and providers can"
            " be obtained by using commands 'pcs resource standards' and"
            " 'pcs resource providers'.\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_print_info_about_agent_completion(self):
        self.assert_pcs_success(
            "resource create R camelcase".split(),
            stderr_full=(
                "Assumed agent name 'ocf:pcsmock:CamelCase' "
                "(deduced from 'camelcase')\n"
            ),
        )

    def test_fail_for_unambiguous_agent(self):
        self.assert_pcs_fail(
            "resource create R pcsmock".split(),
            "Error: Multiple agents match 'pcsmock', please specify full name:"
            " 'ocf:heartbeat:pcsMock' or 'ocf:pacemaker:pcsMock'\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_for_options_not_matching_resource_agent(self):
        self.assert_pcs_fail(
            "resource create R ocf:pcsmock:params a=b mandatory=x c=d".split(),
            "Error: invalid resource options: 'a', 'c', allowed options are: "
            "'advanced', 'enum', 'mandatory', 'optional', 'unique1', 'unique2'"
            ", use --force to override\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_for_missing_options_of_resource_agent(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops R params".split(),
            (
                "Assumed agent name 'ocf:pcsmock:params' (deduced from"
                " 'params')\n"
                "Error: required resource option 'mandatory' is missing,"
                " use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_on_invalid_resource_id(self):
        self.assert_pcs_fail(
            "resource create #R ocf:pcsmock:minimal".split(),
            "Error: invalid resource name '#R',"
            " '#' is not a valid first character for a resource name\n",
        )

    def test_fail_on_existing_resource_id(self):
        self.assert_pcs_success("resource create R ocf:pcsmock:minimal".split())
        self.assert_pcs_fail(
            "resource create R ocf:pcsmock:minimal".split(),
            "Error: 'R' already exists\n",
        )

    def test_fail_on_invalid_operation_id(self):
        self.assert_pcs_fail(
            (
                "resource create R ocf:pcsmock:minimal "
                "op monitor interval=30 id=#O"
            ).split(),
            (
                "Error: invalid operation id '#O',"
                " '#' is not a valid first character for a operation id\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_on_existing_operation_id(self):
        self.assert_pcs_success("resource create R ocf:pcsmock:minimal".split())
        self.assert_pcs_fail(
            (
                "resource create S ocf:pcsmock:minimal "
                "op monitor interval=30 id=R"
            ).split(),
            "Error: 'R' already exists\n",
        )

    def test_fail_on_duplicate_operation_id(self):
        self.assert_pcs_fail(
            (
                "resource create R ocf:pcsmock:minimal "
                "op monitor interval=30 id=O op monitor interval=60 id=O"
            ).split(),
            "Error: 'O' already exists\n",
        )

    def test_fail_on_resource_id_same_as_operation_id(self):
        self.assert_pcs_fail(
            (
                "resource create R ocf:pcsmock:minimal "
                "op monitor interval=30 id=R"
            ).split(),
            "Error: 'R' already exists\n",
        )

    def test_fail_on_unknown_operation(self):
        self.assert_pcs_fail(
            "resource create R ocf:pcsmock:minimal op monitro interval=100".split(),
            (
                "Error: 'monitro' is not a valid operation name value, use"
                " 'meta-data', 'migrate_from', 'migrate_to', 'monitor',"
                " 'reload', 'reload-agent', 'start', 'stop', 'validate-all', "
                "use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_on_ambiguous_value_of_option(self):
        self.assert_pcs_fail(
            (
                "resource create R ocf:pcsmock:minimal "
                "op monitor timeout=10 timeout=20"
            ).split(),
            "Error: duplicate option 'timeout' with different values '10' and"
            " '20'\n",
        )

    def test_unique_err(self):
        self.assert_pcs_success(
            "resource create R1 ocf:pcsmock:unique state=1".split()
        )
        self.assert_pcs_fail(
            "resource create R2 ocf:pcsmock:unique state=1".split(),
            (
                "Error: Value '1' of option 'state' is not unique across "
                "'ocf:pcsmock:unique' resources. Following resources are "
                "configured with the same value of the instance attribute: "
                "'R1', use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_unique_multiple_resources_warn_and_err(self):
        self.assert_pcs_success(
            "resource create R1 ocf:pcsmock:unique state=1".split()
        )
        self.assert_pcs_success(
            "resource create R2 ocf:pcsmock:unique state=1 --force".split(),
            stderr_full=(
                "Warning: Value '1' of option 'state' is not unique across "
                "'ocf:pcsmock:unique' resources. Following resources are "
                "configured with the same value of the instance attribute: 'R1'\n"
            ),
        )
        self.assert_pcs_success(
            "resource create R3 ocf:pcsmock:unique state=1 --force".split(),
            stderr_full=(
                "Warning: Value '1' of option 'state' is not unique across "
                "'ocf:pcsmock:unique' resources. Following resources are "
                "configured with the same value of the instance attribute: 'R1', "
                "'R2'\n"
            ),
        )
        self.assert_pcs_fail(
            "resource create R4 ocf:pcsmock:unique state=1".split(),
            (
                "Error: Value '1' of option 'state' is not unique across "
                "'ocf:pcsmock:unique' resources. Following resources are "
                "configured with the same value of the instance attribute: "
                "'R1', 'R2', 'R3', use --force to override\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )


class FailOrWarnOp(ResourceTest):
    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_fail_empty(self):
        self.assert_pcs_fail(
            (
                "resource create --no-default-ops R ocf:pcsmock:minimal "
                "op meta is-managed=false"
            ).split(),
            "Error: When using 'op' you must specify an operation name and at"
            " least one option\n",
        )

    def test_fail_only_name_without_any_option(self):
        self.assert_pcs_fail(
            (
                "resource create --no-default-ops R ocf:pcsmock:minimal "
                "op monitor meta is-managed=false"
            ).split(),
            "Error: When using 'op' you must specify an operation name and at"
            " least one option\n",
        )

    def test_fail_duplicit(self):
        self.assert_pcs_fail(
            (
                "resource create --no-default-ops R ocf:pcsmock:minimal "
                "op monitor interval=1h monitor interval=3600sec "
                "monitor interval=1min monitor interval=60s"
            ).split(),
            (
                "Error: multiple specification of the same operation with the"
                " same interval:\n"
                "monitor with intervals 1h, 3600sec\n"
                "monitor with intervals 1min, 60s\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_invalid_first_action(self):
        self.assert_pcs_fail(
            (
                "resource create --no-default-ops R ocf:pcsmock:minimal "
                "op mo=nitor interval=1min"
            ).split(),
            "Error: When using 'op' you must specify an operation name after"
            " 'op'\n",
        )

    def test_fail_invalid_option(self):
        self.assert_pcs_fail(
            (
                "resource create --no-default-ops R ocf:pcsmock:minimal "
                "op monitor interval=1min moni=tor timeout=80s"
            ).split(),
            "Error: invalid resource operation option 'moni', allowed options"
            " are: 'OCF_CHECK_LEVEL', 'description', 'enabled', 'id',"
            " 'interval', 'interval-origin', 'name', 'on-fail',"
            " 'record-pending', 'role', 'start-delay', 'timeout'\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_fail_on_invalid_role(self):
        self.assert_pcs_fail(
            (
                "resource create --no-default-ops R ocf:pcsmock:minimal "
                "op monitor role=abc"
            ).split(),
            (
                "Error: 'abc' is not a valid role value, use {}\n".format(
                    format_list(const.PCMK_ROLES)
                )
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_force_invalid_role(self):
        self.assert_pcs_fail(
            (
                "resource create --no-default-ops R ocf:pcsmock:minimal "
                "op monitor role=abc --force"
            ).split(),
            (
                "Error: 'abc' is not a valid role value, use {}\n".format(
                    format_list(const.PCMK_ROLES)
                )
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_on_invalid_on_fail(self):
        self.assert_pcs_fail_regardless_of_force(
            (
                "resource create --no-default-ops R ocf:pcsmock:minimal "
                "op monitor on-fail=Abc"
            ).split(),
            (
                "Error: 'Abc' is not a valid on-fail value, use 'block', "
                "'demote', 'fence', 'ignore', 'restart', 'restart-container', "
                "'standby', 'stop'\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_on_invalid_record_pending(self):
        self.assert_pcs_fail_regardless_of_force(
            (
                "resource create --no-default-ops R ocf:pcsmock:minimal "
                "op monitor record-pending=Abc"
            ).split(),
            (
                "Error: 'Abc' is not a valid record-pending value, use a "
                "pacemaker boolean value: '0', '1', 'false', 'n', 'no', "
                "'off', 'on', 'true', 'y', 'yes'\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_on_invalid_enabled(self):
        self.assert_pcs_fail_regardless_of_force(
            (
                "resource create --no-default-ops R ocf:pcsmock:minimal "
                "op monitor enabled=Abc"
            ).split(),
            (
                "Error: 'Abc' is not a valid enabled value, use a pacemaker "
                "boolean value: '0', '1', 'false', 'n', 'no', 'off', 'on', "
                "'true', 'y', 'yes'\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_on_combination_of_start_delay_and_interval_origin(self):
        self.assert_pcs_fail_regardless_of_force(
            (
                "resource create --no-default-ops R ocf:pcsmock:minimal "
                "op monitor start-delay=10 interval-origin=20"
            ).split(),
            (
                "Error: Only one of resource operation options "
                "'interval-origin' and 'start-delay' can be used\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_on_invalid_interval(self):
        self.assert_pcs_fail_regardless_of_force(
            (
                "resource create --no-default-ops R ocf:pcsmock:minimal "
                "op monitor interval="
            ).split(),
            (
                "Error: '' is not a valid interval value, use time interval "
                "(e.g. 1, 2s, 3m, 4h, ...)\n" + ERRORS_HAVE_OCCURRED
            ),
        )


class FailOrWarnGroup(ResourceTest):
    FUTURE = ""
    GROUP = "--group"
    AFTER = "--after"
    BEFORE = "--before"
    DEPRECATED_GROUP = (
        "Deprecation Warning: Using '--group' is deprecated and will be "
        "replaced with 'group' in a future release. Specify --future to switch "
        "to the future behavior.\n"
    )
    DEPRECATED_AFTER = (
        "Deprecation Warning: Using '--after' is deprecated and will be "
        "replaced with 'after' in a future release. Specify --future to switch "
        "to the future behavior.\n"
    )
    DEPRECATED_BEFORE = (
        "Deprecation Warning: Using '--before' is deprecated and will be "
        "replaced with 'before' in a future release. Specify --future to switch "
        "to the future behavior.\n"
    )

    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_fail_when_invalid_group(self):
        self.assert_pcs_fail(
            f"resource create R ocf:pcsmock:minimal {self.GROUP} 1 {self.FUTURE}".split(),
            (
                self.DEPRECATED_GROUP
                + "Error: invalid group name '1', '1' is not a valid first character"
                " for a group name\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_when_try_use_id_of_another_element(self):
        self.assert_effect(
            (
                "resource create R1 ocf:pcsmock:minimal --no-default-ops "
                "meta a=b"
            ).split(),
            """<resources>
                <primitive class="ocf" id="R1" provider="pcsmock"
                    type="minimal"
                >
                    <meta_attributes id="R1-meta_attributes">
                        <nvpair id="R1-meta_attributes-a" name="a" value="b"/>
                    </meta_attributes>
                    <operations>
                        <op id="R1-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )
        self.assert_pcs_fail(
            (
                "resource create R2 ocf:pcsmock:minimal "
                f"{self.GROUP} R1-meta_attributes {self.FUTURE}"
            ).split(),
            (
                self.DEPRECATED_GROUP
                + "Error: 'R1-meta_attributes' is not a group\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_when_entered_both_after_and_before(self):
        self.assert_pcs_fail(
            (
                "resource create R ocf:pcsmock:minimal "
                f"{self.GROUP} G {self.AFTER} S1 {self.BEFORE} S2 {self.FUTURE}"
            ).split(),
            (
                self.DEPRECATED_GROUP
                + self.DEPRECATED_BEFORE
                + self.DEPRECATED_AFTER
                + f"Error: you cannot specify both {self.BEFORE} and {self.AFTER}\n"
            ),
        )

    def test_fail_when_after_is_used_without_group(self):
        self.assert_pcs_fail(
            "resource create R ocf:pcsmock:minimal --after S1".split(),
            "Error: you cannot use --after without --group\n",
        )

    def test_fail_when_before_is_used_without_group(self):
        self.assert_pcs_fail(
            "resource create R ocf:pcsmock:minimal --before S1".split(),
            "Error: you cannot use --before without --group\n",
        )

    def test_fail_when_before_after_conflicts_and_moreover_without_group(self):
        self.assert_pcs_fail(
            "resource create R ocf:pcsmock:minimal --after S1 --before S2".split(),
            "Error: you cannot use --before without --group\n",
        )

    def test_fail_when_before_does_not_exist(self):
        self.assert_pcs_success(
            (
                f"resource create R0 ocf:pcsmock:minimal {self.GROUP} G1 "
                f"{self.FUTURE}"
            ).split(),
            stderr_full=self.DEPRECATED_GROUP,
        )
        self.assert_pcs_fail(
            (
                f"resource create R2 ocf:pcsmock:minimal {self.GROUP} G1 "
                f"{self.BEFORE} R1 {self.FUTURE}"
            ).split(),
            (
                self.DEPRECATED_GROUP
                + self.DEPRECATED_BEFORE
                + "Error: 'R1' does not exist\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_when_use_before_with_new_group(self):
        self.assert_pcs_fail(
            (
                f"resource create R2 ocf:pcsmock:minimal {self.GROUP} G1 "
                f"{self.BEFORE} R1 {self.FUTURE}"
            ).split(),
            (
                self.DEPRECATED_GROUP
                + self.DEPRECATED_BEFORE
                + "Error: 'R1' does not exist\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_when_after_does_not_exist(self):
        self.assert_pcs_success(
            (
                f"resource create R0 ocf:pcsmock:minimal {self.GROUP} G1 "
                f"{self.FUTURE}"
            ).split(),
            stderr_full=self.DEPRECATED_GROUP,
        )
        self.assert_pcs_fail(
            (
                f"resource create R2 ocf:pcsmock:minimal {self.GROUP} G1 "
                f"{self.AFTER} R1 {self.FUTURE}"
            ).split(),
            (
                self.DEPRECATED_GROUP
                + self.DEPRECATED_AFTER
                + "Error: 'R1' does not exist\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_when_use_after_with_new_group(self):
        self.assert_pcs_fail(
            (
                f"resource create R2 ocf:pcsmock:minimal {self.GROUP} G1 "
                f"{self.AFTER} R1 {self.FUTURE}"
            ).split(),
            (
                self.DEPRECATED_GROUP
                + self.DEPRECATED_AFTER
                + "Error: 'R1' does not exist\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )


class FailOrWarnGroupFuture(FailOrWarnGroup):
    FUTURE = "--future"
    GROUP = "group"
    AFTER = "after"
    BEFORE = "before"
    DEPRECATED_GROUP = DEPRECATED_AFTER = DEPRECATED_BEFORE = ""

    def test_fail_when_entered_both_after_and_before(self):
        self.assert_pcs_fail(
            (
                "resource create R ocf:pcsmock:minimal "
                f"{self.GROUP} G {self.AFTER} S1 {self.BEFORE} S2 {self.FUTURE}"
            ).split(),
            (
                self.DEPRECATED_GROUP
                + self.DEPRECATED_BEFORE
                + self.DEPRECATED_AFTER
                + f"Error: you cannot specify both '{self.BEFORE}' and '{self.AFTER}'\n"
            ),
        )

    def test_fail_when_after_is_used_without_group(self):
        self.assert_pcs_fail(
            "resource create R ocf:pcsmock:minimal after S1".split(),
            "Error: missing value of 'after' option\n",
        )

    def test_fail_when_before_is_used_without_group(self):
        self.assert_pcs_fail(
            "resource create R ocf:pcsmock:minimal before S1".split(),
            "Error: missing value of 'before' option\n",
        )

    def test_fail_when_before_after_conflicts_and_moreover_without_group(self):
        self.assert_pcs_fail(
            "resource create R ocf:pcsmock:minimal after S1 before S2".split(),
            "Error: missing value of 'after' option\n",
        )


class FailOrWarnPacemakerRemoteOrGuestNode(ResourceTest):
    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_fail_when_on_pacemaker_remote_attempt(self):
        self.assert_pcs_fail(
            "resource create R2 ocf:pacemaker:remote".split(),
            (
                "Error: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'"
                ", use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_warn_when_on_pacemaker_remote_attempt(self):
        self.assert_pcs_success(
            "resource create R2 ocf:pacemaker:remote --force".split(),
            stderr_full=(
                "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
            ),
        )

    def test_fail_when_on_pacemaker_remote_conflict_with_existing_node(self):
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote --force".split(),
            stderr_full=(
                "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
            ),
        )

        self.assert_pcs_fail(
            "resource create R2 ocf:pacemaker:remote server=R --force".split(),
            (
                "Warning: this command is not sufficient for creating a "
                "remote connection, use 'pcs cluster node add-remote'\n"
                "Error: Node address 'R' is already used by existing nodes; "
                "please, use other address\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_when_on_pacemaker_remote_conflict_with_existing_id(self):
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote server=R2 --force".split(),
            stderr_full=(
                "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
            ),
        )

        self.assert_pcs_fail(
            "resource create R2 ocf:pacemaker:remote --force".split(),
            (
                "Warning: this command is not sufficient for creating a "
                "remote connection, use 'pcs cluster node add-remote'\n"
                "Error: Node address 'R2' is already used by existing nodes; "
                "please, use other address\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_when_on_guest_conflict_with_existing_node(self):
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote --force".split(),
            stderr_full=(
                "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
            ),
        )

        self.assert_pcs_fail(
            (
                "resource create R2 ocf:pcsmock:minimal "
                "meta remote-node=R --force"
            ).split(),
            (
                "Warning: this command is not sufficient for creating a "
                "guest node, use 'pcs cluster node add-guest'\n"
                "Error: Cannot set name of the guest node to 'R' because that "
                "ID already exists in the cluster configuration.\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_when_on_guest_conflict_with_existing_node_host(self):
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote server=HOST --force".split(),
            stderr_full=(
                "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
            ),
        )

        self.assert_pcs_fail(
            (
                "resource create R2 ocf:pcsmock:minimal "
                "meta remote-node=HOST --force"
            ).split(),
            (
                "Warning: this command is not sufficient for creating a "
                "guest node, use 'pcs cluster node add-guest'\n"
                "Error: Cannot set name of the guest node to 'HOST' because "
                "that ID already exists in the cluster configuration.\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_when_on_guest_conflict_with_existing_node_host_addr(self):
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote server=HOST --force".split(),
            stderr_full=(
                "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
            ),
        )

        self.assert_pcs_fail(
            (
                "resource create R2 ocf:pcsmock:minimal "
                "meta remote-node=A remote-addr=HOST --force"
            ).split(),
            (
                "Warning: this command is not sufficient for creating a "
                "guest node, use 'pcs cluster node add-guest'\n"
                "Error: Node address 'HOST' is already used by existing nodes; "
                "please, use other address\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_not_fail_when_on_guest_when_conflict_host_with_name(self):
        self.assert_pcs_success(
            "resource create R ocf:pacemaker:remote server=HOST --force".split(),
            stderr_full=(
                "Warning: this command is not sufficient for creating a remote"
                " connection, use 'pcs cluster node add-remote'\n"
            ),
        )

        self.assert_pcs_success(
            (
                "resource create R2 ocf:pcsmock:minimal "
                "meta remote-node=HOST remote-addr=R --force"
            ).split(),
            stderr_full=(
                "Warning: this command is not sufficient for creating a guest "
                "node, use 'pcs cluster node add-guest'\n"
            ),
        )

    def test_fail_when_on_pacemaker_remote_guest_attempt(self):
        self.assert_pcs_fail(
            "resource create R2 ocf:pcsmock:minimal meta remote-node=HOST".split(),
            (
                "Error: this command is not sufficient for creating a guest "
                "node, use 'pcs cluster node add-guest', use --force to "
                "override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_warn_when_on_pacemaker_remote_guest_attempt(self):
        self.assert_pcs_success(
            (
                "resource create R2 ocf:pcsmock:minimal "
                "meta remote-node=HOST --force"
            ).split(),
            stderr_full=(
                "Warning: this command is not sufficient for creating a guest node,"
                " use 'pcs cluster node add-guest'\n"
            ),
        )
