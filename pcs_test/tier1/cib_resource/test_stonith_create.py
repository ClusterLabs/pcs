import re

from pcs_test.tier1.cib_resource.common import ResourceTest
from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.misc import is_minimum_pacemaker_version

PCMK_2_0_3_PLUS = is_minimum_pacemaker_version(2, 0, 3)
PCMK_2_0_5_PLUS = is_minimum_pacemaker_version(2, 0, 5)
ERRORS_HAVE_OCCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)


class PlainStonith(ResourceTest):
    def test_simplest(self):
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")
        self.assert_effect(
            "stonith create S fence_xvm".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_xvm">
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_base_with_agent_that_provides_unfencing(self):
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")
        self.assert_effect(
            "stonith create S fence_scsi --force".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_scsi">
                    <meta_attributes id="S-meta_attributes">
                        <nvpair id="S-meta_attributes-provides" name="provides"
                            value="unfencing"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_error_when_not_valid_name(self):
        self.assert_pcs_fail_regardless_of_force(
            "stonith create S fence_xvm:invalid".split(),
            "Error: Invalid stonith agent name 'fence_xvm:invalid'. Agent name "
            "cannot contain the ':' character, do not use the 'stonith:' prefix. "
            "List of agents can be obtained by using command 'pcs stonith list'.\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_error_when_not_valid_agent(self):
        error = error_re = None
        if PCMK_2_0_3_PLUS:
            # pacemaker 2.0.5 adds 'crm_resource:'
            # The exact message returned form pacemaker differs from version to
            # version (sometimes from commit to commit), so we don't check for
            # the whole of it.
            error_re = re.compile(
                "^"
                "Error: Agent 'stonith:absent' is not installed or does not provide "
                "valid metadata:( crm_resource:)? Metadata query for "
                "stonith:absent failed:.+"
                f"use --force to override\n{ERRORS_HAVE_OCCURRED}$",
                re.MULTILINE,
            )
        else:
            error = (
                "Error: Agent 'stonith:absent' is not installed or does not provide "
                "valid metadata: Agent absent not found or does not support "
                "meta-data: Invalid argument (22), "
                "Metadata query for stonith:absent failed: Input/output error, "
                "use --force to override\n" + ERRORS_HAVE_OCCURRED
            )
        self.assert_pcs_fail(
            "stonith create S absent".split(),
            stderr_full=error,
            stderr_regexp=error_re,
        )

    def test_warning_when_not_valid_agent(self):
        error = error_re = None
        if PCMK_2_0_3_PLUS:
            # pacemaker 2.0.5 adds 'crm_resource:'
            # The exact message returned form pacemaker differs from version to
            # version (sometimes from commit to commit), so we don't check for
            # the whole of it.
            error_re = re.compile(
                "^"
                "Warning: Agent 'stonith:absent' is not installed or does not provide "
                "valid metadata:( crm_resource:)? Metadata query for "
                "stonith:absent failed:.+",
                re.MULTILINE,
            )
        else:
            error = (
                "Warning: Agent 'stonith:absent' is not installed or does not provide "
                "valid metadata: Agent absent not found or does not support "
                "meta-data: Invalid argument (22), "
                "Metadata query for stonith:absent failed: Input/output error\n"
            )
        self.assert_effect(
            "stonith create S absent --force".split(),
            """<resources>
                <primitive class="stonith" id="S" type="absent">
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
            stderr_full=error,
            stderr_regexp=error_re,
        )

    def test_disabled_puts_target_role_stopped(self):
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")
        self.assert_effect(
            "stonith create S fence_xvm --disabled".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_xvm">
                    <meta_attributes id="S-meta_attributes">
                        <nvpair id="S-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_debug_and_verbose_allowed(self):
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")
        self.assert_effect(
            "stonith create S fence_apc ip=i username=u verbose=v debug=d password=1234".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug"
                            name="debug" value="d"
                        />
                        <nvpair id="S-instance_attributes-ip"
                            name="ip" value="i"
                        />
                        <nvpair id="S-instance_attributes-password"
                            name="password" value="1234"
                        />
                        <nvpair id="S-instance_attributes-username"
                            name="username" value="u"
                        />
                        <nvpair id="S-instance_attributes-verbose"
                            name="verbose" value="v"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
            stderr_start=(
                "Warning: stonith option 'debug' is deprecated and might be "
                "removed in a future release, therefore it should not "
                "be used, use 'debug_file' instead\n"
            ),
        )

    def test_error_when_action_specified(self):
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")
        self.assert_pcs_fail(
            "stonith create S fence_xvm action=reboot".split(),
            "Error: stonith option 'action' is deprecated and might be removed "
            "in a future release, therefore it should not be"
            " used, use 'pcmk_off_action', 'pcmk_reboot_action' instead, "
            "use --force to override\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_warn_when_action_specified_forced(self):
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")
        self.assert_effect(
            "stonith create S fence_xvm action=reboot --force".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_xvm">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-action"
                            name="action" value="reboot"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
            stderr_full=(
                "Warning: stonith option 'action' is deprecated and might be "
                "removed in a future release, therefore it should not be "
                "used, use 'pcmk_off_action', 'pcmk_reboot_action' instead\n"
            ),
        )


class WithMeta(ResourceTest):
    def test_simplest_with_meta_provides(self):
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")
        self.assert_effect(
            "stonith create S fence_xvm meta provides=something".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_xvm">
                    <meta_attributes id="S-meta_attributes">
                        <nvpair id="S-meta_attributes-provides" name="provides"
                            value="something"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_base_with_agent_that_provides_unfencing_with_meta_provides(self):
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")
        self.assert_effect(
            "stonith create S fence_scsi meta provides=something --force".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_scsi">
                    <meta_attributes id="S-meta_attributes">
                        <nvpair id="S-meta_attributes-provides" name="provides"
                            value="unfencing"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )


class InGroup(ResourceTest):
    def test_fail_create_in_group(self):
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")
        self.assert_pcs_fail(
            "stonith create S fence_xvm --group G --after S1".split(),
            (
                "Error: Specified options '--after', '--group' are not "
                "supported in this command\n"
            ),
        )
