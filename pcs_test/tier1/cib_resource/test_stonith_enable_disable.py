from pcs_test.tier1.cib_resource.common import ResourceTest
from pcs_test.tier1.cib_resource.stonith_common import need_load_xvm_fence_agent


@need_load_xvm_fence_agent
class Enable(ResourceTest):
    def test_enable_disabled_stonith(self):
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
        self.assert_effect(
            "stonith enable S".split(),
            """<resources>
                <primitive class="stonith" id="S" type="fence_xvm">
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
            <primitive class="stonith" id="S" type="fence_xvm">
                <operations>
                    <op id="S-monitor-interval-60s" interval="60s"
                        name="monitor"
                    />
                </operations>
            </primitive>
        </resources>"""

        self.assert_effect("stonith create S fence_xvm".split(), result_xml)
        self.assert_effect("stonith enable S".split(), result_xml)


@need_load_xvm_fence_agent
class Disable(ResourceTest):
    def test_disable_enabled_stonith(self):
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
        self.assert_effect(
            "stonith disable S".split(),
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

    def test_keep_disabled_stonith(self):
        result_xml = """<resources>
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
        self.assert_effect(
            "stonith create S fence_xvm --disabled".split(), result_xml
        )
        self.assert_effect("stonith disable S".split(), result_xml)
