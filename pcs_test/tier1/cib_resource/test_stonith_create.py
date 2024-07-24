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
        self.pcs_runner.mock_settings = get_mock_settings(
            "crm_resource_exec", "stonith_admin_exec"
        )

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
        self.pcs_runner.mock_settings = get_mock_settings(
            "crm_resource_exec", "stonith_admin_exec"
        )

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
    deprecation_warning = (
        "Deprecation Warning: Option to group stonith resource is deprecated "
        "and will be removed in a future release.\n"
    )

    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings(
            "crm_resource_exec", "stonith_admin_exec"
        )

    def test_command_simply_puts_stonith_into_group(self):
        self.assert_effect(
            "stonith create S fence_pcsmock_minimal --group G".split(),
            """<resources>
                <group id="G">
                    <primitive class="stonith" id="S" type="fence_pcsmock_minimal">
                        <operations>
                            <op id="S-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>""",
            stderr_full=self.deprecation_warning,
        )

    def test_command_simply_puts_stonith_into_group_at_the_end(self):
        self.assert_pcs_success(
            "stonith create S1 fence_pcsmock_minimal --group G".split(),
            stderr_full=self.deprecation_warning,
        )
        self.assert_effect(
            "stonith create S2 fence_pcsmock_minimal --group G".split(),
            """<resources>
                <group id="G">
                    <primitive class="stonith" id="S1" type="fence_pcsmock_minimal">
                        <operations>
                            <op id="S1-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                    <primitive class="stonith" id="S2" type="fence_pcsmock_minimal">
                        <operations>
                            <op id="S2-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>""",
            stderr_full=self.deprecation_warning,
        )

    def test_command_simply_puts_stonith_into_group_before_another(self):
        self.assert_pcs_success(
            "stonith create S1 fence_pcsmock_minimal --group G".split(),
            stderr_full=self.deprecation_warning,
        )
        self.assert_effect(
            "stonith create S2 fence_pcsmock_minimal --group G --before S1".split(),
            """<resources>
                <group id="G">
                    <primitive class="stonith" id="S2" type="fence_pcsmock_minimal">
                        <operations>
                            <op id="S2-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                    <primitive class="stonith" id="S1" type="fence_pcsmock_minimal">
                        <operations>
                            <op id="S1-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>""",
            stderr_full=self.deprecation_warning,
        )

    def test_command_simply_puts_stonith_into_group_after_another(self):
        self.assert_pcs_success_all(
            [
                "stonith create S1 fence_pcsmock_minimal --group G".split(),
                "stonith create S2 fence_pcsmock_minimal --group G".split(),
            ]
        )
        self.assert_effect(
            "stonith create S3 fence_pcsmock_minimal --group G --after S1".split(),
            """<resources>
                <group id="G">
                    <primitive class="stonith" id="S1" type="fence_pcsmock_minimal">
                        <operations>
                            <op id="S1-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                    <primitive class="stonith" id="S3" type="fence_pcsmock_minimal">
                        <operations>
                            <op id="S3-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                    <primitive class="stonith" id="S2" type="fence_pcsmock_minimal">
                        <operations>
                            <op id="S2-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>""",
            stderr_full=self.deprecation_warning,
        )

    def test_fail_when_intended_before_item_does_not_exist(self):
        self.assert_pcs_fail(
            "stonith create S2 fence_pcsmock_minimal --group G --before S1".split(),
            (
                self.deprecation_warning
                + "Error: 'S1' does not exist\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_when_intended_after_item_does_not_exist(self):
        self.assert_pcs_fail(
            "stonith create S2 fence_pcsmock_minimal --group G --after S1".split(),
            (
                self.deprecation_warning
                + "Error: 'S1' does not exist\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_fail_when_entered_both_after_and_before(self):
        self.assert_pcs_fail(
            "stonith create S fence_pcsmock_minimal --group G --after S1 --before S2".split(),
            "Error: you cannot specify both --before and --after\n",
        )

    def test_fail_when_after_is_used_without_group(self):
        self.assert_pcs_fail(
            "stonith create S fence_pcsmock_minimal --after S1".split(),
            "Error: you cannot use --after without --group\n",
        )

    def test_fail_when_before_is_used_without_group(self):
        self.assert_pcs_fail(
            "stonith create S fence_pcsmock_minimal --before S1".split(),
            "Error: you cannot use --before without --group\n",
        )

    def test_fail_when_before_after_conflicts_and_moreover_without_group(self):
        self.assert_pcs_fail(
            "stonith create S fence_pcsmock_minimal --after S1 --before S2".split(),
            "Error: you cannot specify both --before and --after"
            " and you have to specify --group\n",
        )
