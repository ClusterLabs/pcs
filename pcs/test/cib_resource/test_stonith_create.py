from __future__ import (
    absolute_import,
    division,
    print_function,
)

import re

from pcs import utils
from pcs.test.cib_resource.common import ResourceTest
from pcs.test.tools import pcs_unittest as unittest
from pcs.test.cib_resource.stonith_common import need_load_xvm_fence_agent

need_fence_scsi_providing_unfencing = unittest.skipUnless(
    not utils.is_rhel6(),
    "test requires system where stonith agent 'fence_scsi' provides unfencing"
)

class PlainStonith(ResourceTest):
    @need_load_xvm_fence_agent
    def test_simplest(self):
        self.assert_effect(
            "stonith create S fence_xvm",
            """<resources>
                <primitive class="stonith" id="S" type="fence_xvm">
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>"""
        )

    @need_fence_scsi_providing_unfencing
    def test_base_with_agent_that_provides_unfencing(self):
        self.assert_effect(
            "stonith create S fence_scsi",
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
            </resources>"""
        )

    def test_error_when_not_valid_name(self):
        self.assert_pcs_fail_regardless_of_force(
            "stonith create S fence_xvm:invalid",
            "Error: Invalid stonith agent name 'fence_xvm:invalid'. List of"
                " agents can be obtained by using command 'pcs stonith list'."
                " Do not use the 'stonith:' prefix. Agent name cannot contain"
                " the ':' character.\n"
        )

    def test_error_when_not_valid_agent(self):
        self.assert_pcs_fail(
            "stonith create S absent",
            # pacemaker 1.1.18 changes -5 to Input/output error
            stdout_regexp=re.compile("^"
                "Error: Agent 'absent' is not installed or does not provide "
                "valid metadata: Metadata query for stonith:absent failed: "
                "(-5|Input/output error), use --force to override\n"
                "$", re.MULTILINE
            )
        )

    def test_warning_when_not_valid_agent(self):
        self.assert_effect(
            "stonith create S absent --force",
            """<resources>
                <primitive class="stonith" id="S" type="absent">
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
            # pacemaker 1.1.18 changes -5 to Input/output error
            output_regexp=re.compile("^"
                "Warning: Agent 'absent' is not installed or does not provide "
                    "valid metadata: Metadata query for stonith:absent failed: "
                    "(-5|Input/output error)\n"
                "$", re.MULTILINE
            )
        )

    @need_load_xvm_fence_agent
    def test_disabled_puts_target_role_stopped(self):
        self.assert_effect(
            "stonith create S fence_xvm --disabled",
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
            </resources>"""
        )

    def test_debug_and_verbose_allowed(self):
        self.assert_effect(
            "stonith create S fence_apc login=l ipaddr=i verbose=v debug=d",
            """<resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug"
                            name="debug" value="d"
                        />
                        <nvpair id="S-instance_attributes-ipaddr"
                            name="ipaddr" value="i"
                        />
                        <nvpair id="S-instance_attributes-login"
                            name="login" value="l"
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
            </resources>"""
        )

    @need_load_xvm_fence_agent
    def test_error_when_action_specified(self):
        self.assert_pcs_fail(
            "stonith create S fence_xvm action=reboot",
            "Error: stonith option 'action' is deprecated and should not be"
                " used, use pcmk_off_action, pcmk_reboot_action instead, use"
                " --force to override\n"
        )

    @need_load_xvm_fence_agent
    def test_warn_when_action_specified_forced(self):
        self.assert_effect(
            "stonith create S fence_xvm action=reboot --force",
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
            "Warning: stonith option 'action' is deprecated and should not be"
                " used, use pcmk_off_action, pcmk_reboot_action instead\n"
        )


class WithMeta(ResourceTest):
    @need_load_xvm_fence_agent
    def test_simplest_with_meta_provides(self):
        self.assert_effect(
            "stonith create S fence_xvm meta provides=something",
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
            </resources>"""
        )

    @need_fence_scsi_providing_unfencing
    def test_base_with_agent_that_provides_unfencing_with_meta_provides(self):
        self.assert_effect(
            "stonith create S fence_scsi meta provides=something",
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
            </resources>"""
        )

class InGroup(ResourceTest):
    @need_load_xvm_fence_agent
    def test_command_simply_puts_stonith_into_group(self):
        self.assert_effect(
            "stonith create S fence_xvm --group G",
            """<resources>
                <group id="G">
                    <primitive class="stonith" id="S" type="fence_xvm">
                        <operations>
                            <op id="S-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>"""
        )

    @need_load_xvm_fence_agent
    def test_command_simply_puts_stonith_into_group_at_the_end(self):
        self.assert_pcs_success("stonith create S1 fence_xvm --group G")
        self.assert_effect(
            "stonith create S2 fence_xvm --group G",
            """<resources>
                <group id="G">
                    <primitive class="stonith" id="S1" type="fence_xvm">
                        <operations>
                            <op id="S1-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                    <primitive class="stonith" id="S2" type="fence_xvm">
                        <operations>
                            <op id="S2-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>"""
        )

    @need_load_xvm_fence_agent
    def test_command_simply_puts_stonith_into_group_before_another(self):
        self.assert_pcs_success("stonith create S1 fence_xvm --group G")
        self.assert_effect(
            "stonith create S2 fence_xvm --group G --before S1",
            """<resources>
                <group id="G">
                    <primitive class="stonith" id="S2" type="fence_xvm">
                        <operations>
                            <op id="S2-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                    <primitive class="stonith" id="S1" type="fence_xvm">
                        <operations>
                            <op id="S1-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>"""
        )

    @need_load_xvm_fence_agent
    def test_command_simply_puts_stonith_into_group_after_another(self):
        self.assert_pcs_success_all([
            "stonith create S1 fence_xvm --group G",
            "stonith create S2 fence_xvm --group G",
        ])
        self.assert_effect(
            "stonith create S3 fence_xvm --group G --after S1",
            """<resources>
                <group id="G">
                    <primitive class="stonith" id="S1" type="fence_xvm">
                        <operations>
                            <op id="S1-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                    <primitive class="stonith" id="S3" type="fence_xvm">
                        <operations>
                            <op id="S3-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                    <primitive class="stonith" id="S2" type="fence_xvm">
                        <operations>
                            <op id="S2-monitor-interval-60s" interval="60s"
                                name="monitor"
                            />
                        </operations>
                    </primitive>
                </group>
            </resources>"""
        )

    @need_load_xvm_fence_agent
    def test_fail_when_inteded_before_item_does_not_exist(self):
        self.assert_pcs_fail(
            "stonith create S2 fence_xvm --group G --before S1",
            "Error: there is no resource 'S1' in the group 'G'\n"
        )

    @need_load_xvm_fence_agent
    def test_fail_when_inteded_after_item_does_not_exist(self):
        self.assert_pcs_fail(
            "stonith create S2 fence_xvm --group G --after S1",
            "Error: there is no resource 'S1' in the group 'G'\n"
        )

    def test_fail_when_entered_both_after_and_before(self):
        self.assert_pcs_fail(
            "stonith create S fence_xvm --group G --after S1 --before S2",
            "Error: you cannot specify both --before and --after\n"
        )

    def test_fail_when_after_is_used_without_group(self):
        self.assert_pcs_fail(
            "stonith create S fence_xvm --after S1",
            "Error: you cannot use --after without --group\n"
        )

    def test_fail_when_before_is_used_without_group(self):
        self.assert_pcs_fail(
            "stonith create S fence_xvm --before S1",
            "Error: you cannot use --before without --group\n"
        )

    def test_fail_when_before_after_conflicts_and_moreover_without_group(self):
        self.assert_pcs_fail(
            "stonith create S fence_xvm --after S1 --before S2",
            "Error: you cannot specify both --before and --after"
                " and you have to specify --group\n"
        )
