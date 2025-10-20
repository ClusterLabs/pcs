from unittest import TestCase

from lxml import etree

from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    write_data_to_tmpfile,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


class EnableDisable(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//resources")[0]
        )
    ),
):
    empty_cib = rc("cib-empty.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_cib_resource_enable_disable")
        write_file_to_tmpfile(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings()

    def tearDown(self):
        self.temp_cib.close()

    def fixture_resource(self, name, disabled=False):
        cmd = [
            "resource",
            "create",
            name,
            "ocf:pcsmock:minimal",
            "--no-default-ops",
        ]
        if disabled:
            cmd.append("--disabled")
        self.assert_pcs_success(cmd)

    def fixture_tag(self, name, ids):
        self.assert_pcs_success(["tag", "create", name] + ids)

    def test_enable_none(self):
        self.assert_pcs_fail(
            "resource enable".split(),
            "Error: You must specify resource(s) to enable\n",
        )

    def test_disable_none(self):
        self.assert_pcs_fail(
            "resource disable".split(),
            "Error: You must specify resource(s) to disable\n",
        )

    def test_enable(self):
        self.fixture_resource("A", disabled=True)
        self.fixture_resource("B", disabled=True)
        self.fixture_tag("TA", ["A"])
        self.assert_effect(
            "resource enable TA B".split(),
            """
            <resources>
                <primitive class="ocf" id="A" provider="pcsmock" type="minimal">
                    <meta_attributes id="A-meta_attributes"/>
                    <operations>
                        <op id="A-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
                <primitive class="ocf" id="B" provider="pcsmock" type="minimal">
                    <meta_attributes id="B-meta_attributes"/>
                    <operations>
                        <op id="B-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
        )

    def test_disable(self):
        self.fixture_resource("A", disabled=False)
        self.fixture_resource("B", disabled=False)
        self.fixture_tag("TA", ["A"])

        self.assert_effect(
            "resource disable B TA".split(),
            """
            <resources>
                <primitive class="ocf" id="A" provider="pcsmock" type="minimal">
                    <meta_attributes id="A-meta_attributes">
                        <nvpair id="A-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="A-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
                <primitive class="ocf" id="B" provider="pcsmock" type="minimal">
                    <meta_attributes id="B-meta_attributes">
                        <nvpair id="B-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="B-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
        )

    def test_enable_nonexistent(self):
        self.fixture_resource("A", disabled=True)

        self.assert_pcs_fail(
            "resource enable A B".split(),
            (
                "Error: bundle / clone / group / resource / tag 'B' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(
            """
            <resources>
                <primitive class="ocf" id="A" provider="pcsmock" type="minimal">
                    <meta_attributes id="A-meta_attributes">
                        <nvpair id="A-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="A-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>
            """
        )

    def test_disable_nonexistent(self):
        self.fixture_resource("A", disabled=False)

        self.assert_pcs_fail(
            "resource disable A B".split(),
            (
                "Error: bundle / clone / group / resource / tag 'B' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(
            """
            <resources>
                <primitive class="ocf" id="A" provider="pcsmock" type="minimal">
                    <operations>
                        <op id="A-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>
            """
        )

    def test_resource_disable_non_existing_with_failed_action(self):
        xml = """
            <cib epoch="557" num_updates="122" admin_epoch="0" crm_feature_set="3.0.14" validate-with="pacemaker-2.10" update-origin="rh7-3" update-client="crmd" cib-last-written="Thu Aug 23 16:49:17 2012" have-quorum="0" dc-uuid="2">
              <configuration>
                <crm_config/>
                <nodes>
                </nodes>
                <resources/>
                <constraints/>
              </configuration>
              <status>
                <node_state id="1" uname="rh7-1" in_ccm="true" crmd="online" crm-debug-origin="do_update_resource" join="member" expected="member">
                  <lrm id="1">
                    <lrm_resources>
                      <lrm_resource id="A" type="apache" class="ocf" provider="pcsmock">
                        <lrm_rsc_op id="A_last_0" operation_key="A_monitor_0" operation="monitor" crm-debug-origin="do_update_resource" crm_feature_set="3.0.14" transition-key="1:1104:7:817ee250-d179-483a-819e-9be9cb0e06df" transition-magic="0:7;1:1104:7:817ee250-d179-483a-819e-9be9cb0e06df" exit-reason="" on_node="rh7-1" call-id="1079" rc-code="7" op-status="0" interval="0" last-run="1591791198" last-rc-change="1591791198" exec-time="275" queue-time="0" op-digest="f2317cad3d54cec5d7d7aa7d0bf35cf8"/>
                      </lrm_resource>
                    </lrm_resources>
                  </lrm>
                </node_state>
              </status>
            </cib>
            """
        write_data_to_tmpfile(xml, self.temp_cib)
        self.assert_pcs_fail(
            "resource disable A".split(),
            (
                "Error: bundle / clone / group / resource / tag 'A' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )
