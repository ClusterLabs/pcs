from pcs_test.tier1.cib_resource.common import ResourceTest
from pcs_test.tools.bin_mock import get_mock_settings

ERRORS_HAVE_OCCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)


class Enable(ResourceTest):
    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_enable_disabled_stonith(self):
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
        self.assert_effect(
            "stonith enable S".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_pcsmock_minimal">
                    <meta_attributes id="S-meta_attributes"/>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>""",
        )

    def test_keep_enabled_stonith(self):
        result_xml = """<resources>
            <primitive class="stonith" id="S" type="fence_pcsmock_minimal">
                <operations>
                    <op id="S-monitor-interval-60s" interval="60s"
                        name="monitor"
                    />
                </operations>
            </primitive>
        </resources>"""

        self.assert_effect(
            "stonith create S fence_pcsmock_minimal".split(), result_xml
        )
        self.assert_effect("stonith enable S".split(), result_xml)


class Disable(ResourceTest):
    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_disable_enabled_stonith(self):
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
        self.assert_pcs_fail(
            "stonith disable S".split(),
            (
                "Error: Requested action leaves the cluster with no enabled "
                "means to fence nodes, resulting in the cluster not being able "
                "to recover from certain failure conditions, use --force to "
                "override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_disable_enabled_stonith_forced(self):
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
        self.assert_effect(
            "stonith disable S --force".split(),
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
            stderr_full=(
                "Warning: Requested action leaves the cluster with no enabled "
                "means to fence nodes, resulting in the cluster not being able "
                "to recover from certain failure conditions\n"
            ),
        )

    def test_keep_disabled_stonith(self):
        result_xml = """<resources>
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
        </resources>"""
        self.assert_effect(
            "stonith create S fence_pcsmock_minimal --disabled".split(),
            result_xml,
        )
        self.assert_effect("stonith disable S".split(), result_xml)
