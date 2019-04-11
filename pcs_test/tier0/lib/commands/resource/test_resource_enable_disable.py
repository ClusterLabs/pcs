# pylint: disable=too-many-lines
from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import (
    outdent,
    skip_unless_pacemaker_supports_bundle,
)

from pcs.common import report_codes
from pcs.lib import reports
from pcs.lib.commands import resource
from pcs.lib.errors import (
    LibraryError,
    ReportItemSeverity as severities,
)


TIMEOUT = 10

fixture_primitive_cib_enabled = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
        </primitive>
    </resources>
"""
fixture_primitive_cib_enabled_with_meta = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <meta_attributes id="A-meta_attributes" />
        </primitive>
    </resources>
"""
fixture_primitive_cib_disabled = """
    <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        </primitive>
    </resources>
"""
fixture_primitive_status_template = """
    <resources>
        <resource id="A" managed="{managed}" />
    </resources>
"""
fixture_primitive_status_managed = fixture_primitive_status_template.format(
    managed="true"
)
fixture_primitive_status_unmanaged = fixture_primitive_status_template.format(
    managed="false"
)

def get_fixture_two_primitives_cib(
    primitive1_disabled=False, primitive1_meta=False,
    primitive2_disabled=False, primitive2_meta=False
):
    parts = ["""
        <resources>
        <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
    """]
    if primitive1_disabled:
        parts.append("""
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        """)
    elif primitive1_meta:
        parts.append("""<meta_attributes id="A-meta_attributes" />""")
    parts.append("""
        </primitive>
        <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
    """)
    if primitive2_disabled:
        parts.append("""
            <meta_attributes id="B-meta_attributes">
                <nvpair id="B-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        """)
    elif primitive2_meta:
        parts.append("""<meta_attributes id="B-meta_attributes" />""")
    parts.append("""</primitive></resources>""")
    return "".join(parts)
fixture_two_primitives_cib_enabled = get_fixture_two_primitives_cib()
fixture_two_primitives_cib_enabled_with_meta_both = \
    get_fixture_two_primitives_cib(
        primitive1_meta=True, primitive2_meta=True
    )
fixture_two_primitives_cib_disabled = get_fixture_two_primitives_cib(
    primitive1_disabled=True
)
fixture_two_primitives_cib_disabled_with_meta = get_fixture_two_primitives_cib(
    primitive1_disabled=True, primitive2_meta=True
)
fixture_two_primitives_cib_disabled_both = get_fixture_two_primitives_cib(
    primitive1_disabled=True, primitive2_disabled=True
)
fixture_two_primitives_status_managed = """
    <resources>
        <resource id="A" managed="true" />
        <resource id="B" managed="true" />
    </resources>
"""

def get_fixture_group_cib(
    group_disabled=False, group_meta=False,
    primitive1_disabled=False, primitive1_meta=False,
    primitive2_disabled=False, primitive2_meta=False
):
    parts = ["""<resources><group id="A">"""]
    if group_disabled:
        parts.append("""
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        """)
    elif group_meta:
        parts.append("""<meta_attributes id="A-meta_attributes" />""")
    parts.append("""
        <primitive id="A1" class="ocf" provider="heartbeat" type="Dummy">
    """)
    if primitive1_disabled:
        parts.append("""
            <meta_attributes id="A1-meta_attributes">
                <nvpair id="A1-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        """)
    elif primitive1_meta:
        parts.append("""<meta_attributes id="A1-meta_attributes" />""")
    parts.append("""
        </primitive>
        <primitive id="A2" class="ocf" provider="heartbeat" type="Dummy">
    """)
    if primitive2_disabled:
        parts.append("""
            <meta_attributes id="A2-meta_attributes">
                <nvpair id="A2-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        """)
    elif primitive2_meta:
        parts.append("""<meta_attributes id="A2-meta_attributes" />""")
    parts.append("""</primitive></group></resources>""")
    return "".join(parts)
fixture_group_cib_enabled = get_fixture_group_cib()
fixture_group_cib_enabled_with_meta_group = get_fixture_group_cib(
    group_meta=True
)
fixture_group_cib_enabled_with_meta_primitive = get_fixture_group_cib(
    primitive1_meta=True
)
fixture_group_cib_disabled_group = get_fixture_group_cib(group_disabled=True)
fixture_group_cib_disabled_group_with_meta_primitive = \
    get_fixture_group_cib(group_disabled=True, primitive1_meta=True)
fixture_group_cib_disabled_primitive = get_fixture_group_cib(
    primitive1_disabled=True
)
fixture_group_cib_disabled_primitive_with_meta_group = get_fixture_group_cib(
    group_meta=True, primitive1_disabled=True
)
fixture_group_cib_disabled_both = get_fixture_group_cib(
    group_disabled=True, primitive1_disabled=True
)
fixture_group_status_template = """
    <resources>
        <group id="A" number_resources="2">
            <resource id="A1" managed="{managed}" />
            <resource id="A2" managed="{managed}" />
        </group>
    </resources>
"""
fixture_group_status_managed = fixture_group_status_template.format(
    managed="true"
)
fixture_group_status_unmanaged = fixture_group_status_template.format(
    managed="false"
)

def get_fixture_clone_cib(
    clone_disabled=False, clone_meta=False,
    primitive_disabled=False, primitive_meta=False
):
    parts = ["""<resources><clone id="A-clone">"""]
    if clone_disabled:
        parts.append("""
            <meta_attributes id="A-clone-meta_attributes">
                <nvpair id="A-clone-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        """)
    elif clone_meta:
        parts.append("""<meta_attributes id="A-clone-meta_attributes" />""")
    parts.append(
        """<primitive id="A" class="ocf" provider="heartbeat" type="Dummy">"""
    )
    if primitive_disabled:
        parts.append("""
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        """)
    elif primitive_meta:
        parts.append("""<meta_attributes id="A-meta_attributes" />""")
    parts.append("""</primitive></clone></resources>""")
    return "".join(parts)
fixture_clone_cib_enabled = get_fixture_clone_cib()
fixture_clone_cib_enabled_with_meta_both = get_fixture_clone_cib(
    clone_meta=True, primitive_meta=True
)
fixture_clone_cib_enabled_with_meta_clone = get_fixture_clone_cib(
    clone_meta=True
)
fixture_clone_cib_enabled_with_meta_primitive = get_fixture_clone_cib(
    primitive_meta=True
)
fixture_clone_cib_disabled_clone = get_fixture_clone_cib(clone_disabled=True)
fixture_clone_cib_disabled_primitive = get_fixture_clone_cib(
    primitive_disabled=True
)
fixture_clone_cib_disabled_both = get_fixture_clone_cib(
    clone_disabled=True, primitive_disabled=True
)
fixture_clone_status_template = """
    <resources>
        <clone id="A-clone" managed="{managed}" multi_state="false"
            unique="false"
        >
            <resource id="A" managed="{managed}" />
            <resource id="A" managed="{managed}" />
        </clone>
    </resources>
"""
fixture_clone_status_managed = fixture_clone_status_template.format(
    managed="true"
)
fixture_clone_status_unmanaged = fixture_clone_status_template.format(
    managed="false"
)

def get_fixture_master_cib(
    master_disabled=False, master_meta=False,
    primitive_disabled=False, primitive_meta=False
):
    parts = ["""<resources><master id="A-master">"""]
    if master_disabled:
        parts.append("""
            <meta_attributes id="A-master-meta_attributes">
                <nvpair id="A-master-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        """)
    elif master_meta:
        parts.append("""<meta_attributes id="A-master-meta_attributes" />""")
    parts.append(
        """<primitive id="A" class="ocf" provider="heartbeat" type="Dummy">"""
    )
    if primitive_disabled:
        parts.append("""
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        """)
    elif primitive_meta:
        parts.append("""<meta_attributes id="A-meta_attributes" />""")
    parts.append("""</primitive></master></resources>""")
    return"".join(parts)
fixture_master_cib_enabled = get_fixture_master_cib()
fixture_master_cib_enabled_with_meta_both = get_fixture_master_cib(
    master_meta=True, primitive_meta=True
)
fixture_master_cib_enabled_with_meta_master = get_fixture_master_cib(
    master_meta=True
)
fixture_master_cib_enabled_with_meta_primitive = get_fixture_master_cib(
    primitive_meta=True
)
fixture_master_cib_disabled_master = get_fixture_master_cib(
    master_disabled=True
)
fixture_master_cib_disabled_primitive = get_fixture_master_cib(
    primitive_disabled=True
)
fixture_master_cib_disabled_both = get_fixture_master_cib(
    master_disabled=True, primitive_disabled=True
)
fixture_master_status_template = """
    <resources>
        <clone id="A-master" managed="{managed}" multi_state="true"
            unique="false"
        >
            <resource id="A" managed="{managed}" />
            <resource id="A" managed="{managed}" />
        </clone>
    </resources>
"""
fixture_master_status_managed = fixture_master_status_template.format(
    managed="true"
)
fixture_master_status_unmanaged = fixture_master_status_template.format(
    managed="false"
)

def get_fixture_clone_group_cib(
    clone_disabled=False, clone_meta=False,
    group_disabled=False, group_meta=False,
    primitive1_disabled=False, primitive1_meta=False,
    primitive2_disabled=False, primitive2_meta=False,
    all_meta=False
):
    # pylint: disable=too-many-arguments
    parts = ["""<resources><clone id="A-clone">"""]
    if clone_disabled:
        parts.append("""
            <meta_attributes id="A-clone-meta_attributes">
                <nvpair id="A-clone-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        """)
    elif clone_meta or all_meta:
        parts.append("""<meta_attributes id="A-clone-meta_attributes" />""")
    parts.append("""<group id="A">""")
    if group_disabled:
        parts.append("""
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        """)
    elif group_meta or all_meta:
        parts.append("""<meta_attributes id="A-meta_attributes" />""")
    parts.append(
        """<primitive id="A1" class="ocf" provider="heartbeat" type="Dummy">"""
    )
    if primitive1_disabled:
        parts.append("""
            <meta_attributes id="A1-meta_attributes">
                <nvpair id="A1-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        """)
    elif primitive1_meta or all_meta:
        parts.append("""<meta_attributes id="A1-meta_attributes" />""")
    parts.append("""
        </primitive>
        <primitive id="A2" class="ocf" provider="heartbeat" type="Dummy">
    """)
    if primitive2_disabled:
        parts.append("""
            <meta_attributes id="A2-meta_attributes">
                <nvpair id="A2-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        """)
    elif primitive2_meta or all_meta:
        parts.append("""<meta_attributes id="A2-meta_attributes" />""")
    parts.append("""</primitive></group></clone></resources>""")
    return "".join(parts)
fixture_clone_group_cib_enabled = get_fixture_clone_group_cib()
fixture_clone_group_cib_enabled_with_meta_clone = get_fixture_clone_group_cib(
    clone_meta=True
)
fixture_clone_group_cib_enabled_with_meta_group = get_fixture_clone_group_cib(
    group_meta=True
)
fixture_clone_group_cib_enabled_with_meta_primitive = \
    get_fixture_clone_group_cib(primitive1_meta=True)
fixture_clone_group_cib_disabled_clone = get_fixture_clone_group_cib(
    clone_disabled=True
)
fixture_clone_group_cib_disabled_group = get_fixture_clone_group_cib(
    group_disabled=True
)
fixture_clone_group_cib_disabled_primitive = get_fixture_clone_group_cib(
    primitive1_disabled=True
)
fixture_clone_group_cib_disabled_primitive_with_meta_clone_group = \
    get_fixture_clone_group_cib(
        clone_meta=True, group_meta=True, primitive1_disabled=True
    )
fixture_clone_group_cib_disabled_clone_group_with_meta_primitive = \
    get_fixture_clone_group_cib(
        clone_disabled=True, group_disabled=True, primitive1_meta=True
    )
fixture_clone_group_cib_disabled_all = get_fixture_clone_group_cib(
    clone_disabled=True, group_disabled=True, primitive1_disabled=True
)
fixture_clone_group_status_template = """
    <resources>
        <clone id="A-clone" managed="{managed}" multi_state="false"
            unique="false"
        >
            <group id="A:0" number_resources="2">
                <resource id="A1" managed="{managed}" />
                <resource id="A2" managed="{managed}" />
            </group>
            <group id="A:1" number_resources="2">
                <resource id="A1" managed="{managed}" />
                <resource id="A2" managed="{managed}" />
            </group>
        </clone>
    </resources>
"""
fixture_clone_group_status_managed = fixture_clone_group_status_template.format(
    managed="true"
)
fixture_clone_group_status_unmanaged = \
    fixture_clone_group_status_template.format(managed="false")

def get_fixture_bundle_cib(
    bundle_disabled=False, bundle_meta=False,
    primitive_disabled=False, primitive_meta=False
):
    parts = ["""<resources><bundle id="A-bundle">"""]
    if bundle_disabled:
        parts.append("""
            <meta_attributes id="A-bundle-meta_attributes">
                <nvpair id="A-bundle-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        """)
    elif bundle_meta:
        parts.append("""<meta_attributes id="A-bundle-meta_attributes" />""")
    parts.append("""
        <docker image="pcs:test" />
        <primitive id="A" class="ocf" provider="heartbeat" type="Dummy">
    """)
    if primitive_disabled:
        parts.append("""
            <meta_attributes id="A-meta_attributes">
                <nvpair id="A-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        """)
    elif primitive_meta:
        parts.append("""<meta_attributes id="A-meta_attributes" />""")
    parts.append("""</primitive></bundle></resources>""")
    return "".join(parts)
fixture_bundle_cib_enabled = get_fixture_bundle_cib()
fixture_bundle_cib_enabled_with_meta_both = get_fixture_bundle_cib(
    bundle_meta=True, primitive_meta=True
)
fixture_bundle_cib_enabled_with_meta_bundle = get_fixture_bundle_cib(
    bundle_meta=True
)
fixture_bundle_cib_enabled_with_meta_primitive = get_fixture_bundle_cib(
    primitive_meta=True
)
fixture_bundle_cib_disabled_primitive = get_fixture_bundle_cib(
    primitive_disabled=True
)
fixture_bundle_cib_disabled_bundle = get_fixture_bundle_cib(
    bundle_disabled=True
)
fixture_bundle_cib_disabled_both = get_fixture_bundle_cib(
    bundle_disabled=True, primitive_disabled=True
)
fixture_bundle_status_template = """
    <resources>
        <bundle id="A-bundle" type="docker" image="pcmktest:http"
            unique="false" managed="{managed}" failed="false"
        >
            <replica id="0">
                <resource id="A" />
            </replica>
            <replica id="1">
                <resource id="A" />
            </replica>
        </bundle>
    </resources>
"""
fixture_bundle_status_managed = fixture_bundle_status_template.format(
    managed="true"
)
fixture_bundle_status_unmanaged = fixture_bundle_status_template.format(
    managed="false"
)

def fixture_report_unmanaged(resource_id):
    return (
        severities.WARNING,
        report_codes.RESOURCE_IS_UNMANAGED,
        {
            "resource_id": resource_id,
        },
        None
    )

class DisablePrimitive(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_nonexistent_resource(self):
        (self.config
            .runner.cib.load(resources=fixture_primitive_cib_enabled)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.disable(self.env_assist.get_env(), ["B"], False),
            [
                fixture.report_not_found("B", "resources")
            ],
            expected_in_processor=False
        )

    def test_nonexistent_resource_in_status(self):
        (self.config
            .runner.cib.load(resources=fixture_two_primitives_cib_enabled)
            .runner.pcmk.load_state(resources=fixture_primitive_status_managed)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.disable(self.env_assist.get_env(), ["B"], False),
            [
                fixture.report_not_found("B")
            ],
        )

    def test_correct_resource(self):
        (self.config
            .runner.cib.load(resources=fixture_two_primitives_cib_enabled)
            .runner.pcmk.load_state(
                resources=fixture_two_primitives_status_managed
            )
            .env.push_cib(resources=fixture_two_primitives_cib_disabled)
        )
        resource.disable(self.env_assist.get_env(), ["A"], False)

    def test_unmanaged(self):
        # The code doesn't care what causes the resource to be unmanaged
        # (cluster property, resource's meta-attribute or whatever). It only
        # checks the cluster state (crm_mon).
        (self.config
            .runner.cib.load(resources=fixture_primitive_cib_enabled)
            .runner.pcmk.load_state(
                resources=fixture_primitive_status_unmanaged
            )
            .env.push_cib(resources=fixture_primitive_cib_disabled)
        )
        resource.disable(self.env_assist.get_env(), ["A"], False)
        self.env_assist.assert_reports([fixture_report_unmanaged("A")])


class EnablePrimitive(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_nonexistent_resource(self):
        (self.config
            .runner.cib.load(resources=fixture_primitive_cib_disabled)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.enable(self.env_assist.get_env(), ["B"], False),
            [
                fixture.report_not_found("B", "resources")
            ],
            expected_in_processor=False
        )

    def test_nonexistent_resource_in_status(self):
        (self.config
            .runner.cib.load(resources=fixture_two_primitives_cib_disabled)
            .runner.pcmk.load_state(resources=fixture_primitive_status_managed)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.enable(self.env_assist.get_env(), ["B"], False),
            [
                fixture.report_not_found("B")
            ]
        )

    def test_correct_resource(self):
        (self.config
            .runner.cib.load(resources=fixture_two_primitives_cib_disabled_both)
            .runner.pcmk.load_state(
                resources=fixture_two_primitives_status_managed
            )
            .env.push_cib(
                resources=fixture_two_primitives_cib_disabled_with_meta
            )
        )
        resource.enable(self.env_assist.get_env(), ["B"], False)

    def test_unmanaged(self):
        # The code doesn't care what causes the resource to be unmanaged
        # (cluster property, resource's meta-attribute or whatever). It only
        # checks the cluster state (crm_mon).
        (self.config
            .runner.cib.load(resources=fixture_primitive_cib_disabled)
            .runner.pcmk.load_state(
                resources=fixture_primitive_status_unmanaged
            )
            .env.push_cib(resources=fixture_primitive_cib_enabled_with_meta)
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)
        self.env_assist.assert_reports([fixture_report_unmanaged("A")])


class MoreResources(TestCase):
    fixture_cib_enabled = """
        <resources>
            <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
            </primitive>
            <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
            </primitive>
            <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
            </primitive>
            <primitive class="ocf" id="D" provider="heartbeat" type="Dummy">
            </primitive>
        </resources>
    """
    fixture_cib_disabled = """
        <resources>
            <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                <meta_attributes id="A-meta_attributes">
                    <nvpair id="A-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
            <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
                <meta_attributes id="B-meta_attributes">
                    <nvpair id="B-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
            <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
                <meta_attributes id="C-meta_attributes">
                    <nvpair id="C-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
            <primitive class="ocf" id="D" provider="heartbeat" type="Dummy">
                <meta_attributes id="D-meta_attributes">
                    <nvpair id="D-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </primitive>
        </resources>
    """
    fixture_status = """
        <resources>
            <resource id="A" managed="true" />
            <resource id="B" managed="false" />
            <resource id="C" managed="true" />
            <resource id="D" managed="false" />
        </resources>
    """

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success_enable(self):
        fixture_enabled = """
            <resources>
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <meta_attributes id="A-meta_attributes" />
                </primitive>
                <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
                    <meta_attributes id="B-meta_attributes" />
                </primitive>
                <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
                    <meta_attributes id="C-meta_attributes">
                        <nvpair id="C-meta_attributes-target-role"
                            name="target-role" value="Stopped" />
                    </meta_attributes>
                </primitive>
                <primitive class="ocf" id="D" provider="heartbeat" type="Dummy">
                    <meta_attributes id="D-meta_attributes" />
                </primitive>
            </resources>
        """
        (self.config
            .runner.cib.load(resources=self.fixture_cib_disabled)
            .runner.pcmk.load_state(resources=self.fixture_status)
            .env.push_cib(resources=fixture_enabled)
        )
        resource.enable(self.env_assist.get_env(), ["A", "B", "D"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("B"),
            fixture_report_unmanaged("D"),
        ])

    def test_success_disable(self):
        fixture_disabled = """
            <resources>
                <primitive class="ocf" id="A" provider="heartbeat" type="Dummy">
                    <meta_attributes id="A-meta_attributes">
                        <nvpair id="A-meta_attributes-target-role"
                            name="target-role" value="Stopped" />
                    </meta_attributes>
                </primitive>
                <primitive class="ocf" id="B" provider="heartbeat" type="Dummy">
                    <meta_attributes id="B-meta_attributes">
                        <nvpair id="B-meta_attributes-target-role"
                            name="target-role" value="Stopped" />
                    </meta_attributes>
                </primitive>
                <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
                </primitive>
                <primitive class="ocf" id="D" provider="heartbeat" type="Dummy">
                    <meta_attributes id="D-meta_attributes">
                        <nvpair id="D-meta_attributes-target-role"
                            name="target-role" value="Stopped" />
                    </meta_attributes>
                </primitive>
            </resources>
        """
        (self.config
            .runner.cib.load(resources=self.fixture_cib_enabled)
            .runner.pcmk.load_state(resources=self.fixture_status)
            .env.push_cib(resources=fixture_disabled)
        )
        resource.disable(self.env_assist.get_env(), ["A", "B", "D"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("B"),
            fixture_report_unmanaged("D"),
        ])

    def test_bad_resource_enable(self):
        (self.config
            .runner.cib.load(resources=self.fixture_cib_disabled)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.enable(
                self.env_assist.get_env(),
                ["B", "X", "Y", "A"],
                wait=False
            ),
            [
                fixture.report_not_found("X", "resources"),
                fixture.report_not_found("Y", "resources"),
            ],
            expected_in_processor=False
        )

    def test_bad_resource_disable(self):
        (self.config
            .runner.cib.load(resources=self.fixture_cib_enabled)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.disable(
                self.env_assist.get_env(),
                ["B", "X", "Y", "A"],
                wait=False
            ),
            [
                fixture.report_not_found("X", "resources"),
                fixture.report_not_found("Y", "resources"),
            ],
            expected_in_processor=False
        )

class Wait(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.pcmk.can_wait()

    fixture_status_running = """
        <resources>
            <resource id="A" managed="true" role="Started">
                <node name="node1" id="1" cached="false"/>
            </resource>
            <resource id="B" managed="true" role="Started">
                <node name="node2" id="1" cached="false"/>
            </resource>
        </resources>
    """
    fixture_status_stopped = """
        <resources>
            <resource id="A" managed="true" role="Stopped">
            </resource>
            <resource id="B" managed="true" role="Stopped">
            </resource>
        </resources>
    """
    fixture_status_mixed = """
        <resources>
            <resource id="A" managed="true" role="Stopped">
            </resource>
            <resource id="B" managed="true" role="Stopped">
            </resource>
        </resources>
    """
    fixture_wait_timeout_error = outdent(
        """\
        Pending actions:
                Action 12: B-node2-stop on node2
        Error performing operation: Timer expired
        """
    ).strip()

    def test_enable_dont_wait_on_error(self):
        (self.config
            .runner.cib.load(resources=fixture_primitive_cib_disabled)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.enable(self.env_assist.get_env(), ["B"], TIMEOUT),
            [
                fixture.report_not_found("B", "resources"),
            ],
            expected_in_processor=False
        )

    def test_disable_dont_wait_on_error(self):
        (self.config
            .runner.cib.load(resources=fixture_primitive_cib_enabled)
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.disable(self.env_assist.get_env(), ["B"], TIMEOUT),
            [
                fixture.report_not_found("B", "resources"),
            ],
            expected_in_processor=False
        )

    def test_enable_resource_stopped(self):
        (self.config
            .runner.cib.load(resources=fixture_two_primitives_cib_disabled_both)
            .runner.pcmk.load_state(resources=self.fixture_status_stopped)
            .env.push_cib(
                resources=fixture_two_primitives_cib_enabled_with_meta_both,
                wait=TIMEOUT
            )
            .runner.pcmk.load_state(
                name="",
                resources=self.fixture_status_stopped,
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.enable(
                self.env_assist.get_env(), ["A", "B"], TIMEOUT
            ),
            [
                fixture.report_resource_not_running("A", severities.ERROR),
                fixture.report_resource_not_running("B", severities.ERROR),
            ]
        )

    def test_disable_resource_stopped(self):
        (self.config
            .runner.cib.load(resources=fixture_two_primitives_cib_enabled)
            .runner.pcmk.load_state(resources=self.fixture_status_running)
            .env.push_cib(
                resources=fixture_two_primitives_cib_disabled_both,
                wait=TIMEOUT
            )
            .runner.pcmk.load_state(
                name="",
                resources=self.fixture_status_stopped,
            )
        )

        resource.disable(self.env_assist.get_env(), ["A", "B"], TIMEOUT)
        self.env_assist.assert_reports([
            fixture.report_resource_not_running("A"),
            fixture.report_resource_not_running("B"),
        ])

    def test_enable_resource_running(self):
        (self.config
            .runner.cib.load(resources=fixture_two_primitives_cib_disabled_both)
            .runner.pcmk.load_state(resources=self.fixture_status_stopped)
            .env.push_cib(
                resources=fixture_two_primitives_cib_enabled_with_meta_both,
                wait=TIMEOUT
            )
            .runner.pcmk.load_state(
                name="",
                resources=self.fixture_status_running,
            )
        )

        resource.enable(self.env_assist.get_env(), ["A", "B"], TIMEOUT)

        self.env_assist.assert_reports([
            fixture.report_resource_running("A", {"Started": ["node1"]}),
            fixture.report_resource_running("B", {"Started": ["node2"]}),
        ])

    def test_disable_resource_running(self):
        (self.config
            .runner.cib.load(resources=fixture_two_primitives_cib_enabled)
            .runner.pcmk.load_state(resources=self.fixture_status_running)
            .env.push_cib(
                resources=fixture_two_primitives_cib_disabled_both,
                wait=TIMEOUT
            )
            .runner.pcmk.load_state(
                name="",
                resources=self.fixture_status_running,
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.disable(
                self.env_assist.get_env(), ["A", "B"], TIMEOUT
            ),
            [
                fixture.report_resource_running(
                    "A", {"Started": ["node1"]}, severities.ERROR
                ),
                fixture.report_resource_running(
                    "B", {"Started": ["node2"]}, severities.ERROR
                ),
            ]
        )

    def test_enable_wait_timeout(self):
        (self.config
            .runner.cib.load(resources=fixture_primitive_cib_disabled)
            .runner.pcmk.load_state(resources=self.fixture_status_stopped)
            .env.push_cib(
                resources=fixture_primitive_cib_enabled_with_meta,
                wait=TIMEOUT,
                exception=LibraryError(
                    reports.wait_for_idle_timed_out(
                        self.fixture_wait_timeout_error
                    )
                )
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.enable(self.env_assist.get_env(), ["A"], TIMEOUT),
            [
                fixture.report_wait_for_idle_timed_out(
                    self.fixture_wait_timeout_error
                )
            ],
            expected_in_processor=False
        )

    def test_disable_wait_timeout(self):
        (self.config
            .runner.cib.load(resources=fixture_primitive_cib_enabled)
            .runner.pcmk.load_state(resources=self.fixture_status_running)
            .env.push_cib(
                resources=fixture_primitive_cib_disabled,
                wait=TIMEOUT,
                exception=LibraryError(
                    reports.wait_for_idle_timed_out(
                        self.fixture_wait_timeout_error
                    )
                )
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.disable(self.env_assist.get_env(), ["A"], TIMEOUT),
            [
                fixture.report_wait_for_idle_timed_out(
                    self.fixture_wait_timeout_error
                )
            ],
            expected_in_processor=False
        )


class WaitClone(TestCase):
    fixture_status_running = """
        <resources>
            <clone id="A-clone" managed="true" multi_state="false" unique="false">
                <resource id="A" managed="true" role="Started">
                    <node name="node1" id="1" cached="false"/>
                </resource>
                <resource id="A" managed="true" role="Started">
                    <node name="node2" id="2" cached="false"/>
                </resource>
            </clone>
        </resources>
    """
    fixture_status_stopped = """
        <resources>
            <clone id="A-clone" managed="true" multi_state="false" unique="false">
                <resource id="A" managed="true" role="Stopped">
                </resource>
                <resource id="A" managed="true" role="Stopped">
                </resource>
            </clone>
        </resources>
    """

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.pcmk.can_wait()

    def test_disable_clone(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_cib_enabled)
            .runner.pcmk.load_state(resources=self.fixture_status_running)
            .env.push_cib(
                resources=fixture_clone_cib_disabled_clone,
                wait=TIMEOUT
            )
            .runner.pcmk.load_state(
                name="",
                resources=self.fixture_status_stopped,
            )
        )

        resource.disable(self.env_assist.get_env(), ["A-clone"], TIMEOUT)
        self.env_assist.assert_reports([
            (
                severities.INFO,
                report_codes.RESOURCE_DOES_NOT_RUN,
                {
                    "resource_id": "A-clone",
                },
                None
            )
        ])

    def test_enable_clone(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_cib_disabled_clone)
            .runner.pcmk.load_state(resources=self.fixture_status_stopped)
            .env.push_cib(
                resources=fixture_clone_cib_enabled_with_meta_clone,
                wait=TIMEOUT
            )
            .runner.pcmk.load_state(
                name="",
                resources=self.fixture_status_running,
            )
        )

        resource.enable(self.env_assist.get_env(), ["A-clone"], TIMEOUT)
        self.env_assist.assert_reports([
            (
                severities.INFO,
                report_codes.RESOURCE_RUNNING_ON_NODES,
                {
                    "resource_id": "A-clone",
                    "roles_with_nodes": {"Started": ["node1", "node2"]},
                },
                None
            )
        ])

class DisableGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(resources=fixture_group_cib_enabled)

    def test_primitive(self):
        (self.config
            .runner.pcmk.load_state(resources=fixture_group_status_managed)
            .env.push_cib(resources=fixture_group_cib_disabled_primitive)
        )
        resource.disable(self.env_assist.get_env(), ["A1"], wait=False)

    def test_group(self):
        (self.config
            .runner.pcmk.load_state(resources=fixture_group_status_managed)
            .env.push_cib(resources=fixture_group_cib_disabled_group)
        )
        resource.disable(self.env_assist.get_env(), ["A"], wait=False)

    def test_primitive_unmanaged(self):
        (self.config
            .runner.pcmk.load_state(resources=fixture_group_status_unmanaged)
            .env.push_cib(resources=fixture_group_cib_disabled_primitive)
        )
        resource.disable(self.env_assist.get_env(), ["A1"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A1"),
        ])

    def test_group_unmanaged(self):
        (self.config
            .runner.pcmk.load_state(resources=fixture_group_status_unmanaged)
            .env.push_cib(resources=fixture_group_cib_disabled_group)
        )
        resource.disable(self.env_assist.get_env(), ["A"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A"),
        ])

class EnableGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config
            .runner.cib.load(resources=fixture_group_cib_disabled_primitive)
            .runner.pcmk.load_state(resources=fixture_group_status_managed)
            .env.push_cib(
                resources=fixture_group_cib_enabled_with_meta_primitive
            )
        )
        resource.enable(self.env_assist.get_env(), ["A1"], wait=False)

    def test_primitive_disabled_both(self):
        (self.config
            .runner.cib.load(resources=fixture_group_cib_disabled_both)
            .runner.pcmk.load_state(resources=fixture_group_status_managed)
            .env.push_cib(
                resources=fixture_group_cib_disabled_group_with_meta_primitive
            )
        )
        resource.enable(self.env_assist.get_env(), ["A1"], wait=False)

    def test_group(self):
        (self.config
            .runner.cib.load(resources=fixture_group_cib_disabled_group)
            .runner.pcmk.load_state(resources=fixture_group_status_managed)
            .env.push_cib(resources=fixture_group_cib_enabled_with_meta_group)
        )
        resource.enable(self.env_assist.get_env(), ["A"], wait=False)

    def test_group_both_disabled(self):
        (self.config
            .runner.cib.load(resources=fixture_group_cib_disabled_both)
            .runner.pcmk.load_state(resources=fixture_group_status_managed)
            .env.push_cib(
                resources=fixture_group_cib_disabled_primitive_with_meta_group
            )
        )
        resource.enable(self.env_assist.get_env(), ["A"], wait=False)

    def test_primitive_unmanaged(self):
        (self.config
            .runner.cib.load(resources=fixture_group_cib_disabled_primitive)
            .runner.pcmk.load_state(resources=fixture_group_status_unmanaged)
            .env.push_cib(
                resources=fixture_group_cib_enabled_with_meta_primitive
            )
        )
        resource.enable(self.env_assist.get_env(), ["A1"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A1"),
        ])

    def test_group_unmanaged(self):
        (self.config
            .runner.cib.load(resources=fixture_group_cib_disabled_group)
            .runner.pcmk.load_state(resources=fixture_group_status_unmanaged)
            .env.push_cib(resources=fixture_group_cib_enabled_with_meta_group)
        )
        resource.enable(self.env_assist.get_env(), ["A"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A"),
        ])


class DisableClone(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.cib.load(resources=fixture_clone_cib_enabled)

    def test_primitive(self):
        (self.config
            .runner.pcmk.load_state(resources=fixture_clone_status_managed)
            .env.push_cib(resources=fixture_clone_cib_disabled_primitive)
        )
        resource.disable(self.env_assist.get_env(), ["A"], wait=False)

    def test_clone(self):
        (self.config
            .runner.pcmk.load_state(resources=fixture_clone_status_managed)
            .env.push_cib(resources=fixture_clone_cib_disabled_clone)
        )
        resource.disable(self.env_assist.get_env(), ["A-clone"], wait=False)

    def test_primitive_unmanaged(self):
        (self.config
            .runner.pcmk.load_state(resources=fixture_clone_status_unmanaged)
            .env.push_cib(resources=fixture_clone_cib_disabled_primitive)
        )
        resource.disable(self.env_assist.get_env(), ["A"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A"),
        ])

    def test_clone_unmanaged(self):
        (self.config
            .runner.pcmk.load_state(resources=fixture_clone_status_unmanaged)
            .env.push_cib(resources=fixture_clone_cib_disabled_clone)
        )
        resource.disable(self.env_assist.get_env(), ["A-clone"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A-clone"),
        ])

class EnableClone(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_cib_disabled_primitive)
            .runner.pcmk.load_state(resources=fixture_clone_status_managed)
            .env.push_cib(
                resources=fixture_clone_cib_enabled_with_meta_primitive
            )
        )
        resource.enable(self.env_assist.get_env(), ["A"], wait=False)

    def test_primitive_disabled_both(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_cib_disabled_both)
            .runner.pcmk.load_state(resources=fixture_clone_status_managed)
            .env.push_cib(resources=fixture_clone_cib_enabled_with_meta_both)
        )
        resource.enable(self.env_assist.get_env(), ["A"], wait=False)

    def test_clone(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_cib_disabled_clone)
            .runner.pcmk.load_state(resources=fixture_clone_status_managed)
            .env.push_cib(resources=fixture_clone_cib_enabled_with_meta_clone)
        )
        resource.enable(self.env_assist.get_env(), ["A-clone"], wait=False)

    def test_clone_disabled_both(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_cib_disabled_both)
            .runner.pcmk.load_state(resources=fixture_clone_status_managed)
            .env.push_cib(resources=fixture_clone_cib_enabled_with_meta_both)
        )
        resource.enable(self.env_assist.get_env(), ["A-clone"], wait=False)

    def test_primitive_unmanaged(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_cib_disabled_primitive)
            .runner.pcmk.load_state(resources=fixture_clone_status_unmanaged)
            .env.push_cib(
                resources=fixture_clone_cib_enabled_with_meta_primitive
            )
        )
        resource.enable(self.env_assist.get_env(), ["A"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A-clone"),
            fixture_report_unmanaged("A"),
        ])

    def test_clone_unmanaged(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_cib_disabled_clone)
            .runner.pcmk.load_state(resources=fixture_clone_status_unmanaged)
            .env.push_cib(resources=fixture_clone_cib_enabled_with_meta_clone)
        )
        resource.enable(self.env_assist.get_env(), ["A-clone"], wait=False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A-clone"),
            fixture_report_unmanaged("A"),
        ])

class DisableMaster(TestCase):
    # same as clone, minimum tests in here
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        (self.config
            .runner.cib.load(resources=fixture_master_cib_enabled)
            .runner.pcmk.load_state(resources=fixture_master_status_managed)
        )

    def test_primitive(self):
        self.config.env.push_cib(
            resources=fixture_master_cib_disabled_primitive
        )
        resource.disable(self.env_assist.get_env(), ["A"], False)

    def test_master(self):
        self.config.env.push_cib(
            resources=fixture_master_cib_disabled_master
        )
        resource.disable(self.env_assist.get_env(), ["A-master"], False)

class EnableMaster(TestCase):
    # same as clone, minimum tests in here
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config
            .runner.cib.load(resources=fixture_master_cib_disabled_primitive)
            .runner.pcmk.load_state(resources=fixture_master_status_managed)
            .env.push_cib(
                resources=fixture_master_cib_enabled_with_meta_primitive
            )
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)

    def test_primitive_disabled_both(self):
        (self.config
            .runner.cib.load(resources=fixture_master_cib_disabled_both)
            .runner.pcmk.load_state(resources=fixture_master_status_managed)
            .env.push_cib(resources=fixture_master_cib_enabled_with_meta_both)
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)

    def test_master(self):
        (self.config
            .runner.cib.load(resources=fixture_master_cib_disabled_master)
            .runner.pcmk.load_state(resources=fixture_master_status_managed)
            .env.push_cib(resources=fixture_master_cib_enabled_with_meta_master)
        )
        resource.enable(self.env_assist.get_env(), ["A-master"], False)

    def test_master_disabled_both(self):
        (self.config
            .runner.cib.load(resources=fixture_master_cib_disabled_both)
            .runner.pcmk.load_state(resources=fixture_master_status_managed)
            .env.push_cib(resources=fixture_master_cib_enabled_with_meta_both)
        )
        resource.enable(self.env_assist.get_env(), ["A-master"], False)

class DisableClonedGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_clone(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_group_cib_enabled)
            .runner.pcmk.load_state(
                resources=fixture_clone_group_status_managed
            )
            .env.push_cib(resources=fixture_clone_group_cib_disabled_clone)
        )
        resource.disable(self.env_assist.get_env(), ["A-clone"], False)

    def test_group(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_group_cib_enabled)
            .runner.pcmk.load_state(
                resources=fixture_clone_group_status_managed
            )
            .env.push_cib(resources=fixture_clone_group_cib_disabled_group)
        )
        resource.disable(self.env_assist.get_env(), ["A"], False)

    def test_primitive(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_group_cib_enabled)
            .runner.pcmk.load_state(
                resources=fixture_clone_group_status_managed
            )
            .env.push_cib(
                resources=fixture_clone_group_cib_disabled_primitive
            )
        )
        resource.disable(self.env_assist.get_env(), ["A1"], False)

    def test_clone_unmanaged(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_group_cib_enabled)
            .runner.pcmk.load_state(
                resources=fixture_clone_group_status_unmanaged
            )
            .env.push_cib(resources=fixture_clone_group_cib_disabled_clone)
        )
        resource.disable(self.env_assist.get_env(), ["A-clone"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A-clone"),
        ])

    def test_group_unmanaged(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_group_cib_enabled)
            .runner.pcmk.load_state(
                resources=fixture_clone_group_status_unmanaged
            )
            .env.push_cib(resources=fixture_clone_group_cib_disabled_group)
        )
        resource.disable(self.env_assist.get_env(), ["A"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A"),
        ])

    def test_primitive_unmanaged(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_group_cib_enabled)
            .runner.pcmk.load_state(
                resources=fixture_clone_group_status_unmanaged
            )
            .env.push_cib(
                resources=fixture_clone_group_cib_disabled_primitive
            )
        )
        resource.disable(self.env_assist.get_env(), ["A1"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A1"),
        ])


class EnableClonedGroup(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_clone(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_group_cib_disabled_clone)
            .runner.pcmk.load_state(
                resources=fixture_clone_group_status_managed
            )
            .env.push_cib(
                resources=fixture_clone_group_cib_enabled_with_meta_clone
            )
        )
        resource.enable(self.env_assist.get_env(), ["A-clone"], False)

    def test_clone_disabled_all(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_group_cib_disabled_all)
            .runner.pcmk.load_state(
                resources=fixture_clone_group_status_managed
            )
            .env.push_cib(
                resources
                =
                fixture_clone_group_cib_disabled_primitive_with_meta_clone_group
            )
        )
        resource.enable(self.env_assist.get_env(), ["A-clone"], False)

    def test_group(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_group_cib_disabled_group)
            .runner.pcmk.load_state(
                resources=fixture_clone_group_status_managed
            )
            .env.push_cib(
                resources=fixture_clone_group_cib_enabled_with_meta_group
            )
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)

    def test_group_disabled_all(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_group_cib_disabled_all)
            .runner.pcmk.load_state(
                resources=fixture_clone_group_status_managed
            )
            .env.push_cib(
                resources
                =
                fixture_clone_group_cib_disabled_primitive_with_meta_clone_group
            )
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)

    def test_primitive(self):
        (self.config
            .runner.cib.load(
                resources=fixture_clone_group_cib_disabled_primitive
            )
            .runner.pcmk.load_state(
                resources=fixture_clone_group_status_managed
            )
            .env.push_cib(
                resources=fixture_clone_group_cib_enabled_with_meta_primitive
            )
        )
        resource.enable(self.env_assist.get_env(), ["A1"], False)

    def test_primitive_disabled_all(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_group_cib_disabled_all)
            .runner.pcmk.load_state(
                resources=fixture_clone_group_status_managed
            )
            .env.push_cib(
                resources
                =
                fixture_clone_group_cib_disabled_clone_group_with_meta_primitive
            )
        )
        resource.enable(self.env_assist.get_env(), ["A1"], False)

    def test_clone_unmanaged(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_group_cib_disabled_clone)
            .runner.pcmk.load_state(
                resources=fixture_clone_group_status_unmanaged
            )
            .env.push_cib(
                resources=fixture_clone_group_cib_enabled_with_meta_clone
            )
        )
        resource.enable(self.env_assist.get_env(), ["A-clone"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A-clone"),
            fixture_report_unmanaged("A"),
        ])

    def test_group_unmanaged(self):
        (self.config
            .runner.cib.load(resources=fixture_clone_group_cib_disabled_group)
            .runner.pcmk.load_state(
                resources=fixture_clone_group_status_unmanaged
            )
            .env.push_cib(
                resources=fixture_clone_group_cib_enabled_with_meta_group
            )
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A"),
            fixture_report_unmanaged("A-clone"),
        ])

    def test_primitive_unmanaged(self):
        (self.config
            .runner.cib.load(
                resources=fixture_clone_group_cib_disabled_primitive
            )
            .runner.pcmk.load_state(
                resources=fixture_clone_group_status_unmanaged
            )
            .env.push_cib(
                resources=fixture_clone_group_cib_enabled_with_meta_primitive
            )
        )
        resource.enable(self.env_assist.get_env(), ["A1"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A1"),
        ])


@skip_unless_pacemaker_supports_bundle
class DisableBundle(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config
            .runner.cib.load(resources=fixture_bundle_cib_enabled)
            .runner.pcmk.load_state(resources=fixture_bundle_status_managed)
            .env.push_cib(resources=fixture_bundle_cib_disabled_primitive)
        )
        resource.disable(self.env_assist.get_env(), ["A"], False)

    def test_bundle(self):
        (self.config
            .runner.cib.load(resources=fixture_bundle_cib_enabled)
            .runner.pcmk.load_state(resources=fixture_bundle_status_managed)
            .env.push_cib(resources=fixture_bundle_cib_disabled_bundle)
        )
        resource.disable(self.env_assist.get_env(), ["A-bundle"], False)

    def test_primitive_unmanaged(self):
        (self.config
            .runner.cib.load(resources=fixture_bundle_cib_enabled)
            .runner.pcmk.load_state(resources=fixture_bundle_status_unmanaged)
            .env.push_cib(resources=fixture_bundle_cib_disabled_primitive)
        )
        resource.disable(self.env_assist.get_env(), ["A"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A"),
        ])

    def test_bundle_unmanaged(self):
        (self.config
            .runner.cib.load(resources=fixture_bundle_cib_enabled)
            .runner.pcmk.load_state(resources=fixture_bundle_status_unmanaged)
            .env.push_cib(resources=fixture_bundle_cib_disabled_bundle)
        )
        resource.disable(self.env_assist.get_env(), ["A-bundle"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A-bundle"),
        ])


@skip_unless_pacemaker_supports_bundle
class EnableBundle(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_primitive(self):
        (self.config
            .runner.cib.load(resources=fixture_bundle_cib_disabled_primitive)
            .runner.pcmk.load_state(resources=fixture_bundle_status_managed)
            .env.push_cib(
                resources=fixture_bundle_cib_enabled_with_meta_primitive
            )
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)

    def test_primitive_disabled_both(self):
        (self.config
            .runner.cib.load(resources=fixture_bundle_cib_disabled_both)
            .runner.pcmk.load_state(resources=fixture_bundle_status_managed)
            .env.push_cib(resources=fixture_bundle_cib_enabled_with_meta_both)
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)

    def test_bundle(self):
        (self.config
            .runner.cib.load(resources=fixture_bundle_cib_disabled_bundle)
            .runner.pcmk.load_state(resources=fixture_bundle_status_managed)
            .env.push_cib(resources=fixture_bundle_cib_enabled_with_meta_bundle)
        )
        resource.enable(self.env_assist.get_env(), ["A-bundle"], False)

    def test_bundle_disabled_both(self):
        (self.config
            .runner.cib.load(resources=fixture_bundle_cib_disabled_both)
            .runner.pcmk.load_state(resources=fixture_bundle_status_managed)
            .env.push_cib(resources=fixture_bundle_cib_enabled_with_meta_both)
        )
        resource.enable(self.env_assist.get_env(), ["A-bundle"], False)

    def test_primitive_unmanaged(self):
        (self.config
            .runner.cib.load(resources=fixture_bundle_cib_disabled_primitive)
            .runner.pcmk.load_state(resources=fixture_bundle_status_unmanaged)
            .env.push_cib(
                resources=fixture_bundle_cib_enabled_with_meta_primitive
            )
        )
        resource.enable(self.env_assist.get_env(), ["A"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A"),
            fixture_report_unmanaged("A-bundle"),
        ])

    def test_bundle_unmanaged(self):
        (self.config
            .runner.cib.load(resources=fixture_bundle_cib_disabled_primitive)
            .runner.pcmk.load_state(resources=fixture_bundle_status_unmanaged)
            .env.push_cib(
                resources=fixture_bundle_cib_enabled_with_meta_primitive
            )
        )
        resource.enable(self.env_assist.get_env(), ["A-bundle"], False)
        self.env_assist.assert_reports([
            fixture_report_unmanaged("A-bundle"),
            fixture_report_unmanaged("A"),
        ])
