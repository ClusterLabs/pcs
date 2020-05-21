from unittest import TestCase
from lxml import etree

from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import (
    get_test_resource as rc,
    get_tmp_file,
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

    def tearDown(self):
        self.temp_cib.close()

    def fixture_resource(self, name, disabled=False):
        self.assert_pcs_success(
            (
                "resource create {0} ocf:heartbeat:Dummy --no-default-ops{1}"
            ).format(name, " --disabled" if disabled else "")
        )

    def fixture_tag(self, name, ids):
        self.assert_pcs_success(
            "tag create {tag_name} {ids}".format(
                tag_name=name, ids=" ".join(ids),
            )
        )

    def test_enable_none(self):
        self.assert_pcs_fail(
            "resource enable", "Error: You must specify resource(s) to enable\n"
        )

    def test_disable_none(self):
        self.assert_pcs_fail(
            "resource disable",
            "Error: You must specify resource(s) to disable\n",
        )

    def test_enable(self):
        self.fixture_resource("A", disabled=True)
        self.fixture_resource("B", disabled=True)
        self.fixture_tag("TA", ["A"])
        self.assert_effect(
            "resource enable TA B",
            """
            <resources>
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <meta_attributes id="A-meta_attributes"/>
                    <operations>
                        <op id="A-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
                <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
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
            "resource disable B TA",
            """
            <resources>
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
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
                <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
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
            "resource enable A B",
            (
                "Error: bundle/clone/group/resource/tag 'B' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(
            """
            <resources>
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
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
            "resource disable A B",
            (
                "Error: bundle/clone/group/resource/tag 'B' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(
            """
            <resources>
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <operations>
                        <op id="A-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>
            """
        )
