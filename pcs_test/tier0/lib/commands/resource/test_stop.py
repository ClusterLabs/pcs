import json
from unittest import TestCase

from pcs.common import reports
from pcs.lib.commands import resource

from pcs_test.tier0.lib.commands.tag import tag_common
from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.xml import XmlManipulation


def fixture_primitive_cib_enabled(resource_id="A"):
    return f"""
        <primitive class="ocf" id="{resource_id}" provider="heartbeat" type="Dummy" />
    """


def fixture_primitive_cib_disabled(resource_id="A"):
    return f"""
        <primitive class="ocf" id="{resource_id}" provider="heartbeat" type="Dummy">
            <meta_attributes id="{resource_id}-meta_attributes">
                <nvpair id="{resource_id}-meta_attributes-target-role"
                    name="target-role" value="Stopped" />
            </meta_attributes>
        </primitive>
    """


FIXTURE_MULTIPLE_PRIMITIVES_STATUS = """
    <resources>
        <resource id="A" role="Started" managed="true" />
        <resource id="B" role="Started" managed="true" />
    </resources>
"""

FIXTURE_MULTIPLE_PRIMITIVES_STATUS_UNMANAGED = """
    <resources>
        <resource id="A" role="Started" managed="true" />
        <resource id="B" role="Started" managed="false" />
    </resources>
"""


class StopResources(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_primitive(self):
        self.config.runner.cib.load(
            resources=f"""
                <resources>
                    {fixture_primitive_cib_enabled("A")}
                    {fixture_primitive_cib_enabled("B")}
                </resources>
            """
        )
        self.config.runner.pcmk.load_state(
            resources=FIXTURE_MULTIPLE_PRIMITIVES_STATUS
        )
        self.config.env.push_cib(
            resources=f"""
                <resources>
                    {fixture_primitive_cib_disabled("A")}
                    {fixture_primitive_cib_enabled("B")}
                </resources>
            """
        )

        resource.stop(self.env_assist.get_env(), ["A"], set())

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.STOPPING_RESOURCES, resource_id_list=["A"]
                )
            ]
        )

    def test_multiple_primitives(self):
        self.config.runner.cib.load(
            resources=f"""
                <resources>
                    {fixture_primitive_cib_enabled("A")}
                    {fixture_primitive_cib_enabled("B")}
                </resources>
            """
        )
        self.config.runner.pcmk.load_state(
            resources=FIXTURE_MULTIPLE_PRIMITIVES_STATUS
        )
        self.config.env.push_cib(
            resources=f"""
                <resources>
                    {fixture_primitive_cib_disabled("A")}
                    {fixture_primitive_cib_disabled("B")}
                </resources>
            """
        )

        resource.stop(self.env_assist.get_env(), ["A", "B"], set())

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.STOPPING_RESOURCES,
                    resource_id_list=["A", "B"],
                )
            ]
        )

    def test_nonexistent_resource(self):
        self.config.runner.cib.load(
            resources=f"""
                <resources>
                    {fixture_primitive_cib_enabled()}
                </resources>
            """
        )
        self.config.runner.pcmk.load_state()

        self.env_assist.assert_raise_library_error(
            lambda: resource.stop(
                self.env_assist.get_env(), ["nonexistent"], set()
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ID_NOT_FOUND,
                    id="nonexistent",
                    expected_types=[
                        "bundle",
                        "clone",
                        "group",
                        "master",
                        "primitive",
                        "tag",
                    ],
                    context_type="cib",
                    context_id="",
                )
            ]
        )

    def test_inner_resources(self):
        self.config.runner.cib.load(
            resources=f"""
                <resources>
                    <clone id="C">
                        <group id="G" number_resources="2">
                            {fixture_primitive_cib_enabled("A")}
                            {fixture_primitive_cib_enabled("B")}
                        </group>
                    </clone>
                </resources>
            """
        )

        self.config.runner.pcmk.load_state(
            resources="""
                <resources>
                    <clone id="C" multi_state="true" unique="false" managed="true">
                        <group id="G:0" number_resources="2">
                            <resource id="A" role="Started" managed="true" />
                            <resource id="B" role="Started" managed="true" />
                        </group>
                    </clone>
                </resources>
            """
        )
        self.config.env.push_cib(
            resources=f"""
                <resources>
                    <clone id="C">
                        <group id="G" number_resources="2">
                            {fixture_primitive_cib_disabled("A")}
                            {fixture_primitive_cib_disabled("B")}
                        </group>
                    </clone>
                </resources>
            """
        )

        resource.stop(self.env_assist.get_env(), ["C"], set())

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.STOPPING_RESOURCES,
                    resource_id_list=["A", "B", "C", "G"],
                )
            ]
        )

    def test_tag(self):
        tag_fixture = tag_common.fixture_tags_xml([("T", ("A", "B"))])
        self.config.runner.cib.load(
            resources=f"""
                <resources>
                    {fixture_primitive_cib_enabled("A")}
                    {fixture_primitive_cib_enabled("B")}
                </resources>
            """,
            tags=tag_fixture,
        )
        self.config.runner.pcmk.load_state(
            resources=FIXTURE_MULTIPLE_PRIMITIVES_STATUS
        )
        self.config.env.push_cib(
            resources=f"""
                <resources>
                    {fixture_primitive_cib_disabled("A")}
                    {fixture_primitive_cib_disabled("B")}
                </resources>
            """,
            tags=tag_fixture,
        )

        resource.stop(self.env_assist.get_env(), ["T"], set())

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.STOPPING_RESOURCES,
                    resource_id_list=["A", "B"],
                )
            ]
        )

    def test_unmanaged(self):
        self.config.runner.cib.load(
            resources=f"""
                <resources>
                    {fixture_primitive_cib_enabled("A")}
                    {fixture_primitive_cib_enabled("B")}
                </resources>
            """
        )
        self.config.runner.pcmk.load_state(
            resources=FIXTURE_MULTIPLE_PRIMITIVES_STATUS_UNMANAGED
        )

        self.env_assist.assert_raise_library_error(
            lambda: resource.stop(self.env_assist.get_env(), ["A", "B"], set())
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RESOURCE_IS_UNMANAGED,
                    resource_id="B",
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def test_unmanaged_force(self):
        self.config.runner.cib.load(
            resources=f"""
                <resources>
                    {fixture_primitive_cib_enabled("A")}
                    {fixture_primitive_cib_enabled("B")}
                </resources>
            """
        )
        self.config.runner.pcmk.load_state(
            resources=FIXTURE_MULTIPLE_PRIMITIVES_STATUS_UNMANAGED
        )
        self.config.env.push_cib(
            resources=f"""
                <resources>
                    {fixture_primitive_cib_disabled("A")}
                    {fixture_primitive_cib_disabled("B")}
                </resources>
            """
        )

        resource.stop(
            self.env_assist.get_env(), ["A", "B"], [reports.codes.FORCE]
        )

        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RESOURCE_IS_UNMANAGED, resource_id="B"
                ),
                fixture.info(
                    reports.codes.STOPPING_RESOURCES,
                    resource_id_list=["A", "B"],
                ),
            ]
        )

    def test_bundle_with_clone_works(self):
        cib_resources_template = """
            <resources>
                <bundle id="BUNDLE">
                    <docker image="pcs:test" />
                    {bundle_resource}
                </bundle>
                <clone>
                    {clone_resource}
                </clone>
            </resources>
        """
        self.config.runner.cib.load(
            resources=cib_resources_template.format(
                bundle_resource=fixture_primitive_cib_enabled("A"),
                clone_resource=fixture_primitive_cib_enabled("B"),
            )
        )
        self.config.runner.pcmk.load_state(
            resources="""
                <resources>
                    <bundle id="BUNDLE" type="podman" managed="true">
                        <replica id="0">
                            <resource id="BUNDLE-ip-192.168.122.250"
                                      resource_agent="ocf:heartbeat:IPaddr2"
                                      role="Stopped"
                            />
                            <resource id="A" role="Stopped" managed="true"/>
                            <resource id="BUNDLE-podman-0"
                                      resource_agent="ocf:heartbeat:podman"
                                      role="Stopped"
                            />
                            <resource id="BUNDLE-0"
                                      resource_agent="ocf:pacemaker:remote"
                                      role="Stopped"
                            />
                        </replica>
                    </bundle>
                    <clone id="C" multi_state="false" unique="false" managed="true">
                        <resource id="B" role="Stopped" managed="true"/>
                    </clone>
                </resources>
            """
        )
        self.config.env.push_cib(
            resources=cib_resources_template.format(
                bundle_resource=fixture_primitive_cib_disabled("A"),
                clone_resource=fixture_primitive_cib_enabled("B"),
            )
        )

        resource.stop(self.env_assist.get_env(), ["BUNDLE"], set())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.STOPPING_RESOURCES,
                    resource_id_list=["A", "BUNDLE"],
                )
            ]
        )


class StopStonith(TestCase):
    resources_cib = """
        <resources>
            <primitive id="S1" class="stonith" type="fence_any" />
            <primitive id="S2" class="stonith" type="fence_any" />
            <primitive id="S3" class="stonith" type="fence_kdump" />
        </resources>
    """
    resources_cib_disabled = """
        <resources>
            <primitive id="S1" class="stonith" type="fence_any">
                <meta_attributes id="S1-meta_attributes">
                    <nvpair id="S1-meta_attributes-target-role"
                        name="target-role" value="Stopped"
                    />
                </meta_attributes>
            </primitive>
            <primitive id="S2" class="stonith" type="fence_any">
                <meta_attributes id="S2-meta_attributes">
                    <nvpair id="S2-meta_attributes-target-role"
                        name="target-role" value="Stopped"
                    />
                </meta_attributes>
            </primitive>
            <primitive id="S3" class="stonith" type="fence_kdump" />
        </resources>
    """
    resources_status = """
        <resources>
            <resource id="S1" managed="true" />
            <resource id="S2" managed="true" />
            <resource id="S3" managed="true" />
        </resources>
    """

    def fixture_config_sbd_calls(self, sbd_enabled):
        node_name_list = ["node-1", "node-2"]
        self.config.env.set_known_nodes(node_name_list)
        self.config.corosync_conf.load(node_name_list=node_name_list)
        self.config.http.sbd.check_sbd(
            communication_list=[
                dict(
                    label=node,
                    param_list=[("watchdog", ""), ("device_list", "[]")],
                    output=json.dumps(
                        dict(
                            sbd=dict(
                                installed=True,
                                enabled=sbd_enabled,
                                running=sbd_enabled,
                            )
                        )
                    ),
                )
                for node in node_name_list
            ]
        )

    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_useful_enabled_stonith_left(self):
        resources_cib_disabled = """
            <resources>
                <primitive id="S1" class="stonith" type="fence_any" />
                <primitive id="S2" class="stonith" type="fence_any">
                    <meta_attributes id="S2-meta_attributes">
                        <nvpair id="S2-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                </primitive>
                <primitive id="S3" class="stonith" type="fence_kdump" />
            </resources>
        """
        self.config.runner.cib.load(resources=self.resources_cib)
        self.config.runner.pcmk.load_state(resources=self.resources_status)
        self.config.env.push_cib(resources=resources_cib_disabled)

        resource.stop(self.env_assist.get_env(), ["S2"])
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.STOPPING_RESOURCES, resource_id_list=["S2"]
                )
            ]
        )

    def test_no_stonith_left_sbd_enabled(self):
        self.config.runner.cib.load(resources=self.resources_cib)
        self.fixture_config_sbd_calls(True)
        self.config.runner.pcmk.load_state(resources=self.resources_status)
        self.config.env.push_cib(resources=self.resources_cib_disabled)

        resource.stop(self.env_assist.get_env(), ["S1", "S2"])
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.STOPPING_RESOURCES,
                    resource_id_list=["S1", "S2"],
                )
            ]
        )

    def test_no_stonith_left_not_live(self):
        tmp_file = "/fake/tmp_file"
        cmd_env = dict(CIB_file=tmp_file)
        cib_xml_man = XmlManipulation.from_file(rc("cib-empty.xml"))
        cib_xml_man.append_to_first_tag_name("resources", self.resources_cib)
        self.config.env.set_cib_data(str(cib_xml_man), cib_tempfile=tmp_file)
        self.config.runner.cib.load(resources=self.resources_cib, env=cmd_env)
        self.config.runner.pcmk.load_state(
            resources=self.resources_status, env=cmd_env
        )
        # doesn't call other nodes to check sbd status

        self.env_assist.assert_raise_library_error(
            lambda: resource.stop(self.env_assist.get_env(), ["S1", "S2"])
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NO_STONITH_MEANS_WOULD_BE_LEFT,
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def test_no_stonith_left_sbd_disabled(self):
        self.config.runner.cib.load(resources=self.resources_cib)
        self.fixture_config_sbd_calls(False)
        self.config.runner.pcmk.load_state(resources=self.resources_status)

        self.env_assist.assert_raise_library_error(
            lambda: resource.stop(self.env_assist.get_env(), ["S1", "S2"])
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NO_STONITH_MEANS_WOULD_BE_LEFT,
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def test_no_stonith_left_sbd_disabled_forced(self):
        self.config.runner.cib.load(resources=self.resources_cib)
        self.fixture_config_sbd_calls(False)
        self.config.runner.pcmk.load_state(resources=self.resources_status)
        self.config.env.push_cib(resources=self.resources_cib_disabled)

        resource.stop(
            self.env_assist.get_env(),
            ["S1", "S2"],
            force_flags={reports.codes.FORCE},
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.NO_STONITH_MEANS_WOULD_BE_LEFT,
                ),
                fixture.info(
                    reports.codes.STOPPING_RESOURCES,
                    resource_id_list=["S1", "S2"],
                ),
            ]
        )

    def test_no_useful_enabled_stonith_removed(self):
        resources_cib = """
            <resources>
                <primitive id="S1" class="stonith" type="fence_any">
                    <meta_attributes id="S1-meta_attributes">
                        <nvpair id="S1-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                </primitive>
                <primitive id="S3" class="stonith" type="fence_kdump" />
            </resources>
        """
        resources_cib_disabled = """
            <resources>
                <primitive id="S1" class="stonith" type="fence_any">
                    <meta_attributes id="S1-meta_attributes">
                        <nvpair id="S1-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                </primitive>
                <primitive id="S3" class="stonith" type="fence_kdump">
                    <meta_attributes id="S3-meta_attributes">
                        <nvpair id="S3-meta_attributes-target-role"
                            name="target-role" value="Stopped"
                        />
                    </meta_attributes>
                </primitive>
            </resources>
        """
        self.config.runner.cib.load(resources=resources_cib)
        self.fixture_config_sbd_calls(False)
        self.config.runner.pcmk.load_state(resources=self.resources_status)
        self.config.env.push_cib(resources=resources_cib_disabled)

        resource.stop(self.env_assist.get_env(), ["S1", "S3"])
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.STOPPING_RESOURCES,
                    resource_id_list=["S1", "S3"],
                )
            ]
        )
