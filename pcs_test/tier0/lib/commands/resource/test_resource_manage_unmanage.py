# pylint: disable=too-many-lines
from unittest import TestCase

from pcs.common.reports import codes as report_codes
from pcs.lib.commands import resource

from pcs_test.tier0.lib.commands.tag.tag_common import fixture_tags_xml
from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

fixture_primitive_cib_managed = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
        </primitive>
    </resources>
"""
fixture_primitive_cib_managed_with_meta = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <meta_attributes id="A-meta_attributes" />
        </primitive>
    </resources>
"""
fixture_primitive_cib_unmanaged = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
        </primitive>
    </resources>
"""

fixture_primitive_cib_managed_op_enabled = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Stateful">
            <operations>
                <op id="A-start" name="start" />
                <op id="A-stop" name="stop" />
                <op id="A-monitor-m" name="monitor" role="Master" />
                <op id="A-monitor-s" name="monitor" role="Slave" />
            </operations>
        </primitive>
    </resources>
"""
fixture_primitive_cib_managed_with_meta_op_enabled = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Stateful">
            <meta_attributes id="A-meta_attributes" />
            <operations>
                <op id="A-start" name="start" />
                <op id="A-stop" name="stop" />
                <op id="A-monitor-m" name="monitor" role="Master" />
                <op id="A-monitor-s" name="monitor" role="Slave" />
            </operations>
        </primitive>
    </resources>
"""
fixture_primitive_cib_managed_with_meta_op_disabled = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Stateful">
            <meta_attributes id="A-meta_attributes" />
            <operations>
                <op id="A-start" name="start" />
                <op id="A-stop" name="stop" />
                <op id="A-monitor-m" name="monitor" role="Master"
                    enabled="false" />
                <op id="A-monitor-s" name="monitor" role="Slave"
                    enabled="false" />
            </operations>
        </primitive>
    </resources>
"""
fixture_primitive_cib_unmanaged_op_enabled = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Stateful">
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <operations>
                <op id="A-start" name="start" />
                <op id="A-stop" name="stop" />
                <op id="A-monitor-m" name="monitor" role="Master" />
                <op id="A-monitor-s" name="monitor" role="Slave" />
            </operations>
        </primitive>
    </resources>
"""
fixture_primitive_cib_unmanaged_op_disabled = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Stateful">
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <operations>
                <op id="A-start" name="start" />
                <op id="A-stop" name="stop" />
                <op id="A-monitor-m" name="monitor" role="Master"
                    enabled="false" />
                <op id="A-monitor-s" name="monitor" role="Slave"
                    enabled="false" />
            </operations>
        </primitive>
    </resources>
"""


def get_fixture_group_cib(
    group_unmanaged=False,
    group_meta=False,
    primitive1_unmanaged=False,
    primitive1_meta=False,
    primitive2_unmanaged=False,
    primitive2_meta=False,
):
    parts = [
        """
        <resources><group id="A">
        <primitive id="A1" class="ocf" provider="heartbeat" type="Dummy">
    """
    ]
    if primitive1_unmanaged:
        parts.append(
            """
            <meta_attributes id="A1-meta_attributes">
                <nvpair id="A1-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
        """
        )
    elif primitive1_meta:
        parts.append("""<meta_attributes id="A1-meta_attributes" />""")
    parts.append(
        """
        </primitive>
        <primitive id="A2" class="ocf" provider="heartbeat" type="Dummy">
    """
    )
    if primitive2_unmanaged:
        parts.append(
            """
            <meta_attributes id="A2-meta_attributes">
                <nvpair id="A2-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
        """
        )
    elif primitive2_meta:
        parts.append("""<meta_attributes id="A2-meta_attributes" />""")
    parts.append("""</primitive>""")
    if group_unmanaged:
        parts.append(
            """
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
        """
        )
    elif group_meta:
        parts.append("""<meta_attributes id="A-meta_attributes" />""")
    parts.append("""</group></resources>""")
    return "".join(parts)


fixture_group_cib_managed = get_fixture_group_cib()
fixture_group_cib_managed_with_both_meta = get_fixture_group_cib(
    group_meta=True, primitive1_meta=True
)
fixture_group_cib_managed_with_resources_meta = get_fixture_group_cib(
    primitive1_meta=True, primitive2_meta=True
)
fixture_group_cib_unmanaged_resource = get_fixture_group_cib(
    primitive1_unmanaged=True
)
fixture_group_cib_unmanaged_resource_with_other_resource_meta = (
    get_fixture_group_cib(primitive1_unmanaged=True, primitive2_meta=True)
)
fixture_group_cib_unmanaged_resource_and_group = get_fixture_group_cib(
    group_unmanaged=True, primitive1_unmanaged=True
)
fixture_group_cib_unmanaged_all_resources = get_fixture_group_cib(
    primitive1_unmanaged=True, primitive2_unmanaged=True
)


def get_fixture_clone_cib(
    clone_unmanaged=False,
    clone_meta=False,
    primitive_unmanaged=False,
    primitive_meta=False,
):
    parts = ["""<resources><clone id="A-clone">"""]
    if clone_unmanaged:
        parts.append(
            """
            <meta_attributes id="A-clone-meta_attributes">
                <nvpair id="A-clone-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
        """
        )
    elif clone_meta:
        parts.append("""<meta_attributes id="A-clone-meta_attributes" />""")
    parts.append(
        """<primitive id="A" class="ocf" provider="heartbeat" type="Dummy">"""
    )
    if primitive_unmanaged:
        parts.append(
            """
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
        """
        )
    elif primitive_meta:
        parts.append("""<meta_attributes id="A-meta_attributes" />""")
    parts.append("""</primitive></clone></resources>""")
    return "".join(parts)


fixture_clone_cib_managed = get_fixture_clone_cib()
fixture_clone_cib_managed_with_meta_primitive = get_fixture_clone_cib(
    primitive_meta=True
)
fixture_clone_cib_managed_with_meta_clone = get_fixture_clone_cib(
    clone_meta=True
)
fixture_clone_cib_managed_with_meta_both = get_fixture_clone_cib(
    clone_meta=True, primitive_meta=True
)
fixture_clone_cib_unmanaged_clone = get_fixture_clone_cib(clone_unmanaged=True)
fixture_clone_cib_unmanaged_primitive = get_fixture_clone_cib(
    primitive_unmanaged=True
)
fixture_clone_cib_unmanaged_both = get_fixture_clone_cib(
    clone_unmanaged=True, primitive_unmanaged=True
)

fixture_clone_cib_managed_op_enabled = """
    <resources>
        <clone id="A-clone">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <operations>
                    <op id="A-start" name="start" />
                    <op id="A-stop" name="stop" />
                    <op id="A-monitor" name="monitor"/>
                </operations>
            </primitive>
        </clone>
    </resources>
"""
fixture_clone_cib_unmanaged_primitive_op_disabled = """
    <resources>
        <clone id="A-clone">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
                <operations>
                    <op id="A-start" name="start" />
                    <op id="A-stop" name="stop" />
                    <op id="A-monitor" name="monitor" enabled="false"/>
                </operations>
            </primitive>
        </clone>
    </resources>
"""

fixture_master_cib_managed = """
    <resources>
        <master id="A-master">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </master>
    </resources>
"""
fixture_master_cib_managed_with_master_meta = """
    <resources>
        <master id="A-master">
            <meta_attributes id="A-master-meta_attributes" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </master>
    </resources>
"""
fixture_master_cib_managed_with_primitive_meta = """
    <resources>
        <master id="A-master">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes" />
            </primitive>
        </master>
    </resources>
"""
fixture_master_cib_managed_with_both_meta = """
    <resources>
        <master id="A-master">
            <meta_attributes id="A-master-meta_attributes" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes" />
            </primitive>
        </master>
    </resources>
"""
fixture_master_cib_unmanaged_master = """
    <resources>
        <master id="A-master">
            <meta_attributes id="A-master-meta_attributes">
                <nvpair id="A-master-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
            </primitive>
        </master>
    </resources>
"""
fixture_master_cib_unmanaged_primitive = """
    <resources>
        <master id="A-master">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
        </master>
    </resources>
"""
fixture_master_cib_unmanaged_both = """
    <resources>
        <master id="A-master">
            <meta_attributes id="A-master-meta_attributes">
                <nvpair id="A-master-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
        </master>
    </resources>
"""

fixture_master_cib_managed_op_enabled = """
    <resources>
        <master id="A-master">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <operations>
                    <op id="A-start" name="start" />
                    <op id="A-stop" name="stop" />
                    <op id="A-monitor" name="monitor"/>
                </operations>
            </primitive>
        </master>
    </resources>
"""
fixture_master_cib_unmanaged_primitive_op_disabled = """
    <resources>
        <master id="A-master">
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
                <operations>
                    <op id="A-start" name="start" />
                    <op id="A-stop" name="stop" />
                    <op id="A-monitor" name="monitor" enabled="false"/>
                </operations>
            </primitive>
        </master>
    </resources>
"""


def get_fixture_clone_group_cib(  # noqa: PLR0913
    *,
    clone_unmanaged=False,
    clone_meta=False,
    group_unmanaged=False,
    group_meta=False,
    primitive1_unmanaged=False,
    primitive1_meta=False,
    primitive2_unmanaged=False,
    primitive2_meta=False,
    all_meta=False,
):
    # pylint: disable=too-many-arguments
    parts = ["""<resources><clone id="A-clone">"""]
    if clone_unmanaged:
        parts.append(
            """
            <meta_attributes id="A-clone-meta_attributes">
                <nvpair id="A-clone-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
        """
        )
    elif clone_meta or all_meta:
        parts.append("""<meta_attributes id="A-clone-meta_attributes" />""")
    parts.append("""<group id="A">""")
    if group_unmanaged:
        parts.append(
            """
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
        """
        )
    elif group_meta or all_meta:
        parts.append("""<meta_attributes id="A-meta_attributes" />""")
    parts.append(
        """<primitive id="A1" class="ocf" provider="heartbeat" type="Dummy">"""
    )
    if primitive1_unmanaged:
        parts.append(
            """
            <meta_attributes id="A1-meta_attributes">
                <nvpair id="A1-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
        """
        )
    elif primitive1_meta or all_meta:
        parts.append("""<meta_attributes id="A1-meta_attributes" />""")
    parts.append(
        """
        </primitive>
        <primitive id="A2" class="ocf" provider="heartbeat" type="Dummy">
    """
    )
    if primitive2_unmanaged:
        parts.append(
            """
            <meta_attributes id="A2-meta_attributes">
                <nvpair id="A2-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
        """
        )
    elif primitive2_meta or all_meta:
        parts.append("""<meta_attributes id="A2-meta_attributes" />""")
    parts.append("""</primitive></group></clone></resources>""")
    return "".join(parts)


fixture_clone_group_cib_managed = get_fixture_clone_group_cib()
fixture_clone_group_cib_managed_with_all_meta = get_fixture_clone_group_cib(
    all_meta=True
)
fixture_clone_group_cib_managed_with_all_primitive_meta = (
    get_fixture_clone_group_cib(primitive1_meta=True, primitive2_meta=True)
)
fixture_clone_group_cib_managed_with_clone_meta = get_fixture_clone_group_cib(
    clone_meta=True
)
fixture_clone_group_cib_managed_with_primitive_meta = (
    get_fixture_clone_group_cib(primitive1_meta=True)
)
fixture_clone_group_cib_unmanaged_primitive = get_fixture_clone_group_cib(
    primitive1_unmanaged=True
)
fixture_clone_group_cib_unmanaged_primitive_with_all_meta = (
    get_fixture_clone_group_cib(primitive1_unmanaged=True, all_meta=True)
)
fixture_clone_group_cib_unmanaged_all_primitives = get_fixture_clone_group_cib(
    primitive1_unmanaged=True, primitive2_unmanaged=True
)
fixture_clone_group_cib_unmanaged_clone = get_fixture_clone_group_cib(
    clone_unmanaged=True
)
fixture_clone_group_cib_unmanaged_everything = get_fixture_clone_group_cib(
    clone_unmanaged=True,
    group_unmanaged=True,
    primitive1_unmanaged=True,
    primitive2_unmanaged=True,
)

fixture_clone_group_cib_managed_op_enabled = """
    <resources>
        <clone id="A-clone">
            <group id="A">
                <primitive id="A1" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <operations>
                        <op id="A1-start" name="start" />
                        <op id="A1-stop" name="stop" />
                        <op id="A1-monitor" name="monitor" />
                    </operations>
                </primitive>
                <primitive id="A2" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <operations>
                        <op id="A2-start" name="start" />
                        <op id="A2-stop" name="stop" />
                        <op id="A2-monitor" name="monitor" />
                    </operations>
                </primitive>
            </group>
        </clone>
    </resources>
"""
fixture_clone_group_cib_unmanaged_primitive_op_disabled = """
    <resources>
        <clone id="A-clone">
            <group id="A">
                <primitive id="A1" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <meta_attributes id="A1-meta_attributes">
                        <nvpair id="A1-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                    <operations>
                        <op id="A1-start" name="start" />
                        <op id="A1-stop" name="stop" />
                        <op id="A1-monitor" name="monitor" enabled="false" />
                    </operations>
                </primitive>
                <primitive id="A2" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <operations>
                        <op id="A2-start" name="start" />
                        <op id="A2-stop" name="stop" />
                        <op id="A2-monitor" name="monitor" />
                    </operations>
                </primitive>
            </group>
        </clone>
    </resources>
"""
fixture_clone_group_cib_unmanaged_all_primitives_op_disabled = """
    <resources>
        <clone id="A-clone">
            <group id="A">
                <primitive id="A1" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <meta_attributes id="A1-meta_attributes">
                        <nvpair id="A1-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                    <operations>
                        <op id="A1-start" name="start" />
                        <op id="A1-stop" name="stop" />
                        <op id="A1-monitor" name="monitor" enabled="false" />
                    </operations>
                </primitive>
                <primitive id="A2" class="ocf" provider="heartbeat"
                    type="Dummy"
                >
                    <meta_attributes id="A2-meta_attributes">
                        <nvpair id="A2-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                    <operations>
                        <op id="A2-start" name="start" />
                        <op id="A2-stop" name="stop" />
                        <op id="A2-monitor" name="monitor" enabled="false" />
                    </operations>
                </primitive>
            </group>
        </clone>
    </resources>
"""


fixture_bundle_empty_cib_managed = """
    <resources>
        <bundle id="A-bundle">
            <docker image="pcs:test" />
        </bundle>
    </resources>
"""
fixture_bundle_empty_cib_managed_with_meta = """
    <resources>
        <bundle id="A-bundle">
            <meta_attributes id="A-bundle-meta_attributes" />
            <docker image="pcs:test" />
        </bundle>
    </resources>
"""
fixture_bundle_empty_cib_unmanaged_bundle = """
    <resources>
        <bundle id="A-bundle">
            <meta_attributes id="A-bundle-meta_attributes">
                <nvpair id="A-bundle-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <docker image="pcs:test" />
        </bundle>
    </resources>
"""


def get_fixture_bundle_cib(
    bundle_unmanaged=False,
    bundle_meta=False,
    primitive_unmanaged=False,
    primitive_meta=False,
):
    parts = ["""<resources><bundle id="A-bundle">"""]
    if bundle_unmanaged:
        parts.append(
            """
            <meta_attributes id="A-bundle-meta_attributes">
                <nvpair id="A-bundle-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
        """
        )
    elif bundle_meta:
        parts.append("""<meta_attributes id="A-bundle-meta_attributes" />""")
    parts.append(
        """
        <docker image="pcs:test" />
        <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
    """
    )
    if primitive_unmanaged:
        parts.append(
            """
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
        """
        )
    elif primitive_meta:
        parts.append("""<meta_attributes id="A-meta_attributes" />""")
    parts.append("""</primitive></bundle></resources>""")
    return "".join(parts)


fixture_bundle_cib_managed = get_fixture_bundle_cib()
fixture_bundle_cib_managed_with_meta_bundle = get_fixture_bundle_cib(
    bundle_meta=True
)
fixture_bundle_cib_managed_with_meta_both = get_fixture_bundle_cib(
    bundle_meta=True, primitive_meta=True
)
fixture_bundle_cib_managed_with_meta_primitive = get_fixture_bundle_cib(
    primitive_meta=True
)
fixture_bundle_cib_unmanaged_bundle = get_fixture_bundle_cib(
    bundle_unmanaged=True
)
fixture_bundle_cib_unmanaged_primitive = get_fixture_bundle_cib(
    primitive_unmanaged=True
)
fixture_bundle_cib_unmanaged_both = get_fixture_bundle_cib(
    bundle_unmanaged=True, primitive_unmanaged=True
)

fixture_bundle_cib_managed_op_enabled = """
    <resources>
        <bundle id="A-bundle">
            <docker image="pcs:test" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <operations>
                    <op id="A-start" name="start" />
                    <op id="A-stop" name="stop" />
                    <op id="A-monitor" name="monitor"/>
                </operations>
            </primitive>
        </bundle>
    </resources>
"""
fixture_bundle_cib_unmanaged_primitive_op_disabled = """
    <resources>
        <bundle id="A-bundle">
            <docker image="pcs:test" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
                <operations>
                    <op id="A-start" name="start" />
                    <op id="A-stop" name="stop" />
                    <op id="A-monitor" name="monitor" enabled="false"/>
                </operations>
            </primitive>
        </bundle>
    </resources>
"""
fixture_bundle_cib_unmanaged_both_op_disabled = """
    <resources>
        <bundle id="A-bundle">
            <meta_attributes id="A-bundle-meta_attributes">
                <nvpair id="A-bundle-meta_attributes-is-managed"
                    name="is-managed" value="false" />
            </meta_attributes>
            <docker image="pcs:test" />
            <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
                <operations>
                    <op id="A-start" name="start" />
                    <op id="A-stop" name="stop" />
                    <op id="A-monitor" name="monitor" enabled="false"/>
                </operations>
            </primitive>
        </bundle>
    </resources>
"""


def fixture_report_no_monitors(resource_id):
    return fixture.warn(
        report_codes.RESOURCE_MANAGED_NO_MONITOR_ENABLED,
        resource_id=resource_id,
    )


class UnmanageTag(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_tag(self):
        self.config.runner.cib.load(
            resources=fixture_primitive_cib_managed,
            tags=fixture_tags_xml([("T", ("A"))]),
        )
        self.config.env.push_cib(resources=fixture_primitive_cib_unmanaged)
        resource.unmanage(self.env_assist.get_env(), ["T"])


class ManageTag(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_tag(self):
        self.config.runner.cib.load(
            resources=fixture_primitive_cib_unmanaged,
            tags=fixture_tags_xml([("T", ("A"))]),
        )
        self.config.env.push_cib(
            resources=fixture_primitive_cib_managed_with_meta
        )
        resource.manage(self.env_assist.get_env(), ["T"])


class UnmanagePrimitive(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_nonexistent_resource(self):
        self.config.runner.cib.load(resources=fixture_primitive_cib_managed)

        self.env_assist.assert_raise_library_error(
            lambda: resource.unmanage(self.env_assist.get_env(), ["B"]),
        )
        self.env_assist.assert_reports(
            [fixture.report_not_resource_or_tag("B")]
        )

    def test_primitive(self):
        self.config.runner.cib.load(resources=fixture_primitive_cib_managed)
        self.config.env.push_cib(resources=fixture_primitive_cib_unmanaged)
        resource.unmanage(self.env_assist.get_env(), ["A"])

    def test_primitive_unmanaged(self):
        self.config.runner.cib.load(resources=fixture_primitive_cib_unmanaged)
        self.config.env.push_cib(resources=fixture_primitive_cib_unmanaged)
        resource.unmanage(self.env_assist.get_env(), ["A"])


class ManagePrimitive(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_nonexistent_resource(self):
        self.config.runner.cib.load(resources=fixture_primitive_cib_unmanaged)

        self.env_assist.assert_raise_library_error(
            lambda: resource.manage(self.env_assist.get_env(), ["B"]),
        )
        self.env_assist.assert_reports(
            [fixture.report_not_resource_or_tag("B")]
        )

    def test_primitive(self):
        self.config.runner.cib.load(resources=fixture_primitive_cib_unmanaged)
        self.config.env.push_cib(
            resources=fixture_primitive_cib_managed_with_meta
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_primitive_managed(self):
        self.config.runner.cib.load(resources=fixture_primitive_cib_managed)
        self.config.env.push_cib(resources=fixture_primitive_cib_managed)
        resource.manage(self.env_assist.get_env(), ["A"])


class UnmanageGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        self.config.runner.cib.load(resources=fixture_group_cib_managed)
        self.config.env.push_cib(resources=fixture_group_cib_unmanaged_resource)
        resource.unmanage(self.env_assist.get_env(), ["A1"])

    def test_group(self):
        self.config.runner.cib.load(resources=fixture_group_cib_managed)
        self.config.env.push_cib(
            resources=fixture_group_cib_unmanaged_all_resources
        )
        resource.unmanage(self.env_assist.get_env(), ["A"])


class ManageGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        self.config.runner.cib.load(
            resources=fixture_group_cib_unmanaged_all_resources
        )
        self.config.env.push_cib(
            resources=fixture_group_cib_unmanaged_resource_with_other_resource_meta
        )
        resource.manage(self.env_assist.get_env(), ["A2"])

    def test_primitive_unmanaged_group(self):
        self.config.runner.cib.load(
            resources=fixture_group_cib_unmanaged_resource_and_group
        )
        self.config.env.push_cib(
            resources=fixture_group_cib_managed_with_both_meta
        )
        resource.manage(self.env_assist.get_env(), ["A1"])

    def test_group(self):
        self.config.runner.cib.load(
            resources=fixture_group_cib_unmanaged_all_resources
        )
        self.config.env.push_cib(
            resources=fixture_group_cib_managed_with_resources_meta
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_group_unmanaged_group(self):
        self.config.runner.cib.load(
            resources=fixture_group_cib_unmanaged_resource_and_group
        )
        self.config.env.push_cib(
            resources=fixture_group_cib_managed_with_both_meta
        )
        resource.manage(self.env_assist.get_env(), ["A"])


class UnmanageClone(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        self.config.runner.cib.load(resources=fixture_clone_cib_managed)
        self.config.env.push_cib(
            resources=fixture_clone_cib_unmanaged_primitive
        )
        resource.unmanage(self.env_assist.get_env(), ["A"])

    def test_clone(self):
        self.config.runner.cib.load(resources=fixture_clone_cib_managed)
        self.config.env.push_cib(
            resources=fixture_clone_cib_unmanaged_primitive
        )
        resource.unmanage(self.env_assist.get_env(), ["A-clone"])


class ManageClone(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        self.config.runner.cib.load(resources=fixture_clone_cib_unmanaged_clone)
        self.config.env.push_cib(
            resources=fixture_clone_cib_managed_with_meta_clone
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_primitive_unmanaged_primitive(self):
        self.config.runner.cib.load(
            resources=fixture_clone_cib_unmanaged_primitive
        )
        self.config.env.push_cib(
            resources=fixture_clone_cib_managed_with_meta_primitive
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_primitive_unmanaged_both(self):
        self.config.runner.cib.load(resources=fixture_clone_cib_unmanaged_both)
        self.config.env.push_cib(
            resources=fixture_clone_cib_managed_with_meta_both
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_clone(self):
        self.config.runner.cib.load(resources=fixture_clone_cib_unmanaged_clone)
        self.config.env.push_cib(
            resources=fixture_clone_cib_managed_with_meta_clone
        )
        resource.manage(self.env_assist.get_env(), ["A-clone"])

    def test_clone_unmanaged_primitive(self):
        self.config.runner.cib.load(
            resources=fixture_clone_cib_unmanaged_primitive
        )
        self.config.env.push_cib(
            resources=fixture_clone_cib_managed_with_meta_primitive
        )
        resource.manage(self.env_assist.get_env(), ["A-clone"])

    def test_clone_unmanaged_both(self):
        self.config.runner.cib.load(resources=fixture_clone_cib_unmanaged_both)
        self.config.env.push_cib(
            resources=fixture_clone_cib_managed_with_meta_both
        )
        resource.manage(self.env_assist.get_env(), ["A-clone"])


class UnmanageMaster(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        self.config.runner.cib.load(resources=fixture_master_cib_managed)
        self.config.env.push_cib(
            resources=fixture_master_cib_unmanaged_primitive
        )
        resource.unmanage(self.env_assist.get_env(), ["A"])

    def test_master(self):
        self.config.runner.cib.load(resources=fixture_master_cib_managed)
        self.config.env.push_cib(
            resources=fixture_master_cib_unmanaged_primitive
        )
        resource.unmanage(self.env_assist.get_env(), ["A-master"])


class ManageMaster(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        self.config.runner.cib.load(
            resources=fixture_master_cib_unmanaged_primitive
        )
        self.config.env.push_cib(
            resources=fixture_master_cib_managed_with_primitive_meta
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_primitive_unmanaged_master(self):
        self.config.runner.cib.load(
            resources=fixture_master_cib_unmanaged_master
        )
        self.config.env.push_cib(
            resources=fixture_master_cib_managed_with_master_meta
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_primitive_unmanaged_both(self):
        self.config.runner.cib.load(resources=fixture_master_cib_unmanaged_both)
        self.config.env.push_cib(
            resources=fixture_master_cib_managed_with_both_meta
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_master(self):
        self.config.runner.cib.load(
            resources=fixture_master_cib_unmanaged_master
        )
        self.config.env.push_cib(
            resources=fixture_master_cib_managed_with_master_meta
        )
        resource.manage(self.env_assist.get_env(), ["A-master"])

    def test_master_unmanaged_primitive(self):
        self.config.runner.cib.load(
            resources=fixture_master_cib_unmanaged_primitive
        )
        self.config.env.push_cib(
            resources=fixture_master_cib_managed_with_primitive_meta
        )
        resource.manage(self.env_assist.get_env(), ["A-master"])

    def test_master_unmanaged_both(self):
        self.config.runner.cib.load(resources=fixture_master_cib_unmanaged_both)
        self.config.env.push_cib(
            resources=fixture_master_cib_managed_with_both_meta
        )
        resource.manage(self.env_assist.get_env(), ["A-master"])


class UnmanageClonedGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        self.config.runner.cib.load(resources=fixture_clone_group_cib_managed)
        self.config.env.push_cib(
            resources=fixture_clone_group_cib_unmanaged_primitive
        )
        resource.unmanage(self.env_assist.get_env(), ["A1"])

    def test_group(self):
        self.config.runner.cib.load(resources=fixture_clone_group_cib_managed)
        self.config.env.push_cib(
            resources=fixture_clone_group_cib_unmanaged_all_primitives
        )
        resource.unmanage(self.env_assist.get_env(), ["A"])

    def test_clone(self):
        self.config.runner.cib.load(resources=fixture_clone_group_cib_managed)
        self.config.env.push_cib(
            resources=fixture_clone_group_cib_unmanaged_all_primitives
        )
        resource.unmanage(self.env_assist.get_env(), ["A-clone"])


class ManageClonedGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        self.config.runner.cib.load(
            resources=fixture_clone_group_cib_unmanaged_primitive
        )
        self.config.env.push_cib(
            resources=fixture_clone_group_cib_managed_with_primitive_meta
        )
        resource.manage(self.env_assist.get_env(), ["A1"])

    def test_primitive_unmanaged_all(self):
        self.config.runner.cib.load(
            resources=fixture_clone_group_cib_unmanaged_everything
        )
        self.config.env.push_cib(
            resources=fixture_clone_group_cib_unmanaged_primitive_with_all_meta
        )
        resource.manage(self.env_assist.get_env(), ["A2"])

    def test_group(self):
        self.config.runner.cib.load(
            resources=fixture_clone_group_cib_unmanaged_all_primitives
        )
        self.config.env.push_cib(
            resources=fixture_clone_group_cib_managed_with_all_primitive_meta
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_group_unmanaged_all(self):
        self.config.runner.cib.load(
            resources=fixture_clone_group_cib_unmanaged_everything
        )
        self.config.env.push_cib(
            resources=fixture_clone_group_cib_managed_with_all_meta
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_clone(self):
        self.config.runner.cib.load(
            resources=fixture_clone_group_cib_unmanaged_clone
        )
        self.config.env.push_cib(
            resources=fixture_clone_group_cib_managed_with_clone_meta
        )
        resource.manage(self.env_assist.get_env(), ["A-clone"])

    def test_clone_unmanaged_all(self):
        self.config.runner.cib.load(
            resources=fixture_clone_group_cib_unmanaged_everything
        )
        self.config.env.push_cib(
            resources=fixture_clone_group_cib_managed_with_all_meta
        )
        resource.manage(self.env_assist.get_env(), ["A-clone"])


class UnmanageBundle(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        self.config.runner.cib.load(resources=fixture_bundle_cib_managed)
        self.config.env.push_cib(
            resources=fixture_bundle_cib_unmanaged_primitive
        )
        resource.unmanage(self.env_assist.get_env(), ["A"])

    def test_bundle(self):
        self.config.runner.cib.load(resources=fixture_bundle_cib_managed)
        self.config.env.push_cib(resources=fixture_bundle_cib_unmanaged_both)
        resource.unmanage(self.env_assist.get_env(), ["A-bundle"])

    def test_bundle_empty(self):
        self.config.runner.cib.load(resources=fixture_bundle_empty_cib_managed)
        self.config.env.push_cib(
            resources=fixture_bundle_empty_cib_unmanaged_bundle
        )
        resource.unmanage(self.env_assist.get_env(), ["A-bundle"])


class ManageBundle(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        self.config.runner.cib.load(
            resources=fixture_bundle_cib_unmanaged_primitive
        )
        self.config.env.push_cib(
            resources=fixture_bundle_cib_managed_with_meta_primitive
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_primitive_unmanaged_bundle(self):
        self.config.runner.cib.load(
            resources=fixture_bundle_cib_unmanaged_bundle
        )
        self.config.env.push_cib(
            resources=fixture_bundle_cib_managed_with_meta_bundle
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_primitive_unmanaged_both(self):
        self.config.runner.cib.load(resources=fixture_bundle_cib_unmanaged_both)
        self.config.env.push_cib(
            resources=fixture_bundle_cib_managed_with_meta_both
        )
        resource.manage(self.env_assist.get_env(), ["A"])

    def test_bundle(self):
        self.config.runner.cib.load(
            resources=fixture_bundle_cib_unmanaged_bundle
        )
        self.config.env.push_cib(
            resources=fixture_bundle_cib_managed_with_meta_bundle
        )
        resource.manage(self.env_assist.get_env(), ["A-bundle"])

    def test_bundle_unmanaged_primitive(self):
        self.config.runner.cib.load(
            resources=fixture_bundle_cib_unmanaged_primitive
        )
        self.config.env.push_cib(
            resources=fixture_bundle_cib_managed_with_meta_primitive
        )
        resource.manage(self.env_assist.get_env(), ["A-bundle"])

    def test_bundle_unmanaged_both(self):
        self.config.runner.cib.load(resources=fixture_bundle_cib_unmanaged_both)
        self.config.env.push_cib(
            resources=fixture_bundle_cib_managed_with_meta_both
        )
        resource.manage(self.env_assist.get_env(), ["A-bundle"])

    def test_bundle_empty(self):
        self.config.runner.cib.load(
            resources=fixture_bundle_empty_cib_unmanaged_bundle
        )
        self.config.env.push_cib(
            resources=fixture_bundle_empty_cib_managed_with_meta
        )
        resource.manage(self.env_assist.get_env(), ["A-bundle"])


class MoreResources(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    fixture_cib_managed = """
        <resources>
            <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            </primitive>
            <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
            </primitive>
            <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
            </primitive>
        </resources>
    """
    fixture_cib_unmanaged = """
        <resources>
            <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
            <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
                <meta_attributes id="B-meta_attributes">
                    <nvpair id="B-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
            <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
                <meta_attributes id="C-meta_attributes">
                    <nvpair id="C-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </primitive>
        </resources>
    """

    def test_success_unmanage(self):
        fixture_cib_unmanaged = """
            <resources>
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <meta_attributes id="A-meta_attributes">
                        <nvpair id="A-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                </primitive>
                <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
                </primitive>
                <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
                    <meta_attributes id="C-meta_attributes">
                        <nvpair id="C-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                </primitive>
            </resources>
        """
        self.config.runner.cib.load(resources=self.fixture_cib_managed)
        self.config.env.push_cib(resources=fixture_cib_unmanaged)
        resource.unmanage(self.env_assist.get_env(), ["A", "C"])

    def test_success_manage(self):
        fixture_cib_managed = """
            <resources>
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <meta_attributes id="A-meta_attributes" />
                </primitive>
                <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
                    <meta_attributes id="B-meta_attributes">
                        <nvpair id="B-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                </primitive>
                <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
                    <meta_attributes id="C-meta_attributes" />
                </primitive>
            </resources>
        """
        self.config.runner.cib.load(resources=self.fixture_cib_unmanaged)
        self.config.env.push_cib(resources=fixture_cib_managed)
        resource.manage(self.env_assist.get_env(), ["A", "C"])

    def test_bad_resource_unmanage(self):
        self.config.runner.cib.load(resources=self.fixture_cib_managed)

        self.env_assist.assert_raise_library_error(
            lambda: resource.unmanage(
                self.env_assist.get_env(), ["B", "X", "Y", "A"]
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.report_not_resource_or_tag("X"),
                fixture.report_not_resource_or_tag("Y"),
            ],
        )

    def test_bad_resource_enable(self):
        self.config.runner.cib.load(resources=self.fixture_cib_unmanaged)

        self.env_assist.assert_raise_library_error(
            lambda: resource.manage(
                self.env_assist.get_env(), ["B", "X", "Y", "A"]
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.report_not_resource_or_tag("X"),
                fixture.report_not_resource_or_tag("Y"),
            ],
        )


class WithMonitor(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_unmanage_noop(self):
        self.config.runner.cib.load(resources=fixture_primitive_cib_managed)
        self.config.env.push_cib(resources=fixture_primitive_cib_unmanaged)
        resource.unmanage(self.env_assist.get_env(), ["A"], True)

    def test_manage_noop(self):
        self.config.runner.cib.load(resources=fixture_primitive_cib_unmanaged)
        self.config.env.push_cib(
            resources=fixture_primitive_cib_managed_with_meta
        )
        resource.manage(self.env_assist.get_env(), ["A"], True)

    def test_unmanage(self):
        self.config.runner.cib.load(
            resources=fixture_primitive_cib_managed_op_enabled
        )
        self.config.env.push_cib(
            resources=fixture_primitive_cib_unmanaged_op_disabled
        )
        resource.unmanage(self.env_assist.get_env(), ["A"], True)

    def test_manage(self):
        self.config.runner.cib.load(
            resources=fixture_primitive_cib_unmanaged_op_disabled
        )
        self.config.env.push_cib(
            resources=fixture_primitive_cib_managed_with_meta_op_enabled
        )
        resource.manage(self.env_assist.get_env(), ["A"], True)

    def test_unmanage_enabled_monitors(self):
        self.config.runner.cib.load(
            resources=fixture_primitive_cib_managed_op_enabled
        )
        self.config.env.push_cib(
            resources=fixture_primitive_cib_unmanaged_op_enabled
        )
        resource.unmanage(self.env_assist.get_env(), ["A"], False)

    def test_manage_disabled_monitors(self):
        self.config.runner.cib.load(
            resources=fixture_primitive_cib_unmanaged_op_disabled
        )
        self.config.env.push_cib(
            resources=fixture_primitive_cib_managed_with_meta_op_disabled
        )
        resource.manage(self.env_assist.get_env(), ["A"], False)
        self.env_assist.assert_reports([fixture_report_no_monitors("A")])

    def test_unmanage_clone(self):
        self.config.runner.cib.load(
            resources=fixture_clone_cib_managed_op_enabled
        )
        self.config.env.push_cib(
            resources=fixture_clone_cib_unmanaged_primitive_op_disabled
        )
        resource.unmanage(self.env_assist.get_env(), ["A-clone"], True)

    def test_unmanage_in_clone(self):
        self.config.runner.cib.load(
            resources=fixture_clone_cib_managed_op_enabled
        )
        self.config.env.push_cib(
            resources=fixture_clone_cib_unmanaged_primitive_op_disabled
        )
        resource.unmanage(self.env_assist.get_env(), ["A"], True)

    def test_unmanage_master(self):
        self.config.runner.cib.load(
            resources=fixture_master_cib_managed_op_enabled
        )
        self.config.env.push_cib(
            resources=fixture_master_cib_unmanaged_primitive_op_disabled
        )
        resource.unmanage(self.env_assist.get_env(), ["A-master"], True)

    def test_unmanage_in_master(self):
        self.config.runner.cib.load(
            resources=fixture_master_cib_managed_op_enabled
        )
        self.config.env.push_cib(
            resources=fixture_master_cib_unmanaged_primitive_op_disabled
        )
        resource.unmanage(self.env_assist.get_env(), ["A"], True)

    def test_unmanage_clone_with_group(self):
        self.config.runner.cib.load(
            resources=fixture_clone_group_cib_managed_op_enabled
        )
        self.config.env.push_cib(
            resources=fixture_clone_group_cib_unmanaged_all_primitives_op_disabled
        )
        resource.unmanage(self.env_assist.get_env(), ["A-clone"], True)

    def test_unmanage_group_in_clone(self):
        self.config.runner.cib.load(
            resources=fixture_clone_group_cib_managed_op_enabled
        )
        self.config.env.push_cib(
            resources=fixture_clone_group_cib_unmanaged_all_primitives_op_disabled
        )
        resource.unmanage(self.env_assist.get_env(), ["A"], True)

    def test_unmanage_in_cloned_group(self):
        self.config.runner.cib.load(
            resources=fixture_clone_group_cib_managed_op_enabled
        )
        self.config.env.push_cib(
            resources=fixture_clone_group_cib_unmanaged_primitive_op_disabled
        )
        resource.unmanage(self.env_assist.get_env(), ["A1"], True)

    def test_unmanage_bundle(self):
        self.config.runner.cib.load(
            resources=fixture_bundle_cib_managed_op_enabled
        )
        self.config.env.push_cib(
            resources=fixture_bundle_cib_unmanaged_both_op_disabled
        )
        resource.unmanage(self.env_assist.get_env(), ["A-bundle"], True)

    def test_unmanage_in_bundle(self):
        self.config.runner.cib.load(
            resources=fixture_bundle_cib_managed_op_enabled
        )
        self.config.env.push_cib(
            resources=fixture_bundle_cib_unmanaged_primitive_op_disabled
        )
        resource.unmanage(self.env_assist.get_env(), ["A"], True)

    def test_unmanage_bundle_empty(self):
        self.config.runner.cib.load(resources=fixture_bundle_empty_cib_managed)
        self.config.env.push_cib(
            resources=fixture_bundle_empty_cib_unmanaged_bundle
        )
        resource.unmanage(self.env_assist.get_env(), ["A-bundle"], True)

    def test_manage_one_resource_in_group(self):
        self.config.runner.cib.load(
            resources=fixture_clone_group_cib_unmanaged_all_primitives_op_disabled
        )
        self.config.env.push_cib(
            resources="""
                <resources>
                    <clone id="A-clone">
                        <group id="A">
                            <primitive id="A1" class="ocf" provider="heartbeat"
                                type="Dummy"
                            >
                                <meta_attributes id="A1-meta_attributes" />
                                <operations>
                                    <op id="A1-start" name="start" />
                                    <op id="A1-stop" name="stop" />
                                    <op id="A1-monitor" name="monitor" />
                                </operations>
                            </primitive>
                            <primitive id="A2" class="ocf" provider="heartbeat"
                                type="Dummy"
                            >
                                <meta_attributes id="A2-meta_attributes">
                                    <nvpair id="A2-meta_attributes-is-managed"
                                        name="is-managed" value="false" />
                                </meta_attributes>
                                <operations>
                                    <op id="A2-start" name="start" />
                                    <op id="A2-stop" name="stop" />
                                    <op id="A2-monitor" name="monitor"
                                        enabled="false"
                                    />
                                </operations>
                            </primitive>
                        </group>
                    </clone>
                </resources>
            """
        )
        resource.manage(self.env_assist.get_env(), ["A1"], True)
