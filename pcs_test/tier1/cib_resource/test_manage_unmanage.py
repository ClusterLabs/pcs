from unittest import TestCase

from lxml import etree

from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


class ManageUnmanage(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//resources")[0]
        )
    ),
):
    empty_cib = rc("cib-empty.xml")

    @staticmethod
    def fixture_cib_unmanaged_a(add_empty_meta_b=False):
        empty_meta_b = '<meta_attributes id="B-meta_attributes" />'
        return """
            <resources>
                <primitive class="ocf" id="A" provider="pcsmock" type="minimal">
                    <meta_attributes id="A-meta_attributes">
                        <nvpair id="A-meta_attributes-is-managed"
                            name="is-managed" value="false"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="A-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
                <primitive class="ocf" id="B" provider="pcsmock" type="minimal">
                    {empty_meta_b}<operations>
                        <op id="B-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>
        """.format(empty_meta_b=(empty_meta_b if add_empty_meta_b else ""))

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_cib_resource_manage_unmanage")
        write_file_to_tmpfile(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings()

    def tearDown(self):
        self.temp_cib.close()

    def fixture_resource(self, name, managed=True, with_monitors=False):
        self.assert_pcs_success(
            [
                "resource",
                "create",
                name,
                "ocf:pcsmock:minimal",
                "--no-default-ops",
            ]
        )
        if not managed:
            cmd = ["resource", "unmanage", name]
            if with_monitors:
                cmd.append("--monitor")
            self.assert_pcs_success(cmd)

    def fixture_tag(self, name, ids):
        self.assert_pcs_success(["tag", "create", name] + ids)

    def test_unmanage_none(self):
        self.assert_pcs_fail(
            "resource unmanage".split(),
            "Error: You must specify resource(s) to unmanage\n",
        )

    def test_manage_none(self):
        self.assert_pcs_fail(
            "resource manage".split(),
            "Error: You must specify resource(s) to manage\n",
        )

    def test_unmanage_one(self):
        self.fixture_resource("A")
        self.fixture_resource("B")
        self.assert_effect(
            "resource unmanage A".split(), self.fixture_cib_unmanaged_a()
        )

    def test_manage_one(self):
        self.fixture_resource("A", managed=False)
        self.fixture_resource("B", managed=False)
        self.assert_effect(
            "resource manage B".split(),
            self.fixture_cib_unmanaged_a(add_empty_meta_b=True),
        )

    def test_unmanage_monitor(self):
        self.fixture_resource("A")
        self.assert_effect(
            "resource unmanage A --monitor".split(),
            """
            <resources>
                <primitive class="ocf" id="A" provider="pcsmock" type="minimal">
                    <meta_attributes id="A-meta_attributes">
                        <nvpair id="A-meta_attributes-is-managed"
                            name="is-managed" value="false"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="A-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s" enabled="false"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
        )

    def test_unmanage_monitor_enabled(self):
        self.fixture_resource("A")
        self.assert_effect(
            "resource unmanage A".split(),
            """
            <resources>
                <primitive class="ocf" id="A" provider="pcsmock" type="minimal">
                    <meta_attributes id="A-meta_attributes">
                        <nvpair id="A-meta_attributes-is-managed"
                            name="is-managed" value="false"
                        />
                    </meta_attributes>
                    <operations>
                        <op id="A-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
        )

    def test_manage_monitor(self):
        self.fixture_resource("A", managed=True, with_monitors=True)
        self.assert_effect(
            "resource manage A --monitor".split(),
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
            """,
        )

    def test_manage_monitor_disabled(self):
        self.fixture_resource("A", managed=False, with_monitors=True)
        self.assert_effect(
            "resource manage A".split(),
            """
            <resources>
                <primitive class="ocf" id="A" provider="pcsmock" type="minimal">
                    <meta_attributes id="A-meta_attributes" />
                    <operations>
                        <op id="A-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s" enabled="false"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
            stderr_full=(
                "Warning: Resource 'A' has no enabled monitor operations."
                " Re-run with '--monitor' to enable them.\n"
            ),
        )

    def test_unmanage_more(self):
        self.fixture_resource("A")
        self.fixture_resource("B")
        self.fixture_tag("TA", ["A"])
        self.assert_effect(
            "resource unmanage TA B".split(),
            """
            <resources>
                <primitive class="ocf" id="A" provider="pcsmock" type="minimal">
                    <meta_attributes id="A-meta_attributes">
                        <nvpair id="A-meta_attributes-is-managed"
                            name="is-managed" value="false"
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
                        <nvpair id="B-meta_attributes-is-managed"
                            name="is-managed" value="false"
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

    def test_manage_more(self):
        self.fixture_resource("A", managed=False)
        self.fixture_resource("B", managed=False)
        self.fixture_tag("TA", ["A"])
        self.assert_effect(
            "resource manage TA B".split(),
            """
            <resources>
                <primitive class="ocf" id="A" provider="pcsmock" type="minimal">
                    <meta_attributes id="A-meta_attributes" />
                    <operations>
                        <op id="A-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
                <primitive class="ocf" id="B" provider="pcsmock" type="minimal">
                    <meta_attributes id="B-meta_attributes" />
                    <operations>
                        <op id="B-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
        )

    def test_unmanage_nonexistent(self):
        self.fixture_resource("A")

        self.assert_pcs_fail(
            "resource unmanage A B".split(),
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

    def test_manage_nonexistent(self):
        self.fixture_resource("A", managed=False)

        self.assert_pcs_fail(
            "resource manage A B".split(),
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
                        <nvpair id="A-meta_attributes-is-managed"
                            name="is-managed" value="false"
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
