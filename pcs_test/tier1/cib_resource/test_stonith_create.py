from pcs_test.tier1.cib_resource.common import ResourceTest
from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.misc import is_minimum_pacemaker_version

PCMK_2_0_3_PLUS = is_minimum_pacemaker_version(2, 0, 3)
PCMK_2_0_5_PLUS = is_minimum_pacemaker_version(2, 0, 5)
ERRORS_HAVE_OCCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)


class PlainStonith(ResourceTest):
    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_simplest(self):
        self.assert_effect(
            "stonith create S fence_pcsmock_minimal".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_pcsmock_minimal">
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_base_with_agent_that_provides_unfencing(self):
        self.assert_effect(
            "stonith create S fence_pcsmock_unfencing".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_pcsmock_unfencing">
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
            "stonith create S fence_pcsmock:invalid".split(),
            "Error: Invalid stonith agent name 'fence_pcsmock:invalid'. Agent name "
            "cannot contain the ':' character, do not use the 'stonith:' prefix. "
            "List of agents can be obtained by using command 'pcs stonith list'.\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_error_when_not_valid_agent(self):
        self.assert_pcs_fail(
            "stonith create S absent".split(),
            stderr_full=(
                "Error: Agent 'stonith:absent' is not installed or "
                "does not provide valid metadata: "
                "pcs mock error message: unable to load agent metadata, "
                "use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_warning_when_not_valid_agent(self):
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
            stderr_full=(
                "Warning: Agent 'stonith:absent' is not installed or "
                "does not provide valid metadata: "
                "pcs mock error message: unable to load agent metadata\n"
            ),
        )

    def test_disabled_puts_target_role_stopped(self):
        self.assert_effect(
            "stonith create S fence_pcsmock_minimal --disabled".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_pcsmock_minimal">
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
        self.assert_effect(
            "stonith create S fence_pcsmock_params ip=i username=u verbose=v debug=d password=1234".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_pcsmock_params">
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
        self.assert_pcs_fail(
            "stonith create S fence_pcsmock_action action=reboot".split(),
            "Error: stonith option 'action' is deprecated and might be removed "
            "in a future release, therefore it should not be"
            " used, use 'pcmk_off_action', 'pcmk_reboot_action' instead, "
            "use --force to override\n" + ERRORS_HAVE_OCCURRED,
        )

    def test_warn_when_action_specified_forced(self):
        self.assert_effect(
            "stonith create S fence_pcsmock_action action=reboot --force".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_pcsmock_action">
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
    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_simplest_with_meta_provides(self):
        self.assert_effect(
            "stonith create S fence_pcsmock_minimal meta provides=something".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_pcsmock_minimal">
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
        self.assert_effect(
            "stonith create S fence_pcsmock_unfencing meta provides=something".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_pcsmock_unfencing">
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
    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_fail_create_in_group(self):
        self.assert_pcs_fail(
            "stonith create S fence_pcsmock_minimal --group G --after S1".split(),
            (
                "Error: Specified options '--after', '--group' are not "
                "supported in this command\n"
                "Hint: Syntax has changed from previous version. See 'man pcs' "
                "-> Changes in pcs-0.12.\n"
            ),
        )
