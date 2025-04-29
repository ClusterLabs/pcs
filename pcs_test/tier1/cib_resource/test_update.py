from textwrap import dedent
from unittest import TestCase

from pcs_test.tier1.cib_resource.common import get_cib_resources
from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.fixture_cib import modify_cib_file
from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_file,
    write_data_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


def fixture_primitive(
    rsc_id,
    agent_class="ocf",
    agent_provider="pcsmock",
    agent_type="minimal",
    inner_xml="",
):
    return f"""
        <primitive class="{agent_class}" id="{rsc_id}"
          provider="{agent_provider}" type="{agent_type}"
        >
          {inner_xml}
        </primitive>
    """


def fixture_clone(clone_id, inner_xml=""):
    clone_id_split = clone_id.split("-")
    assert clone_id_split[-1] == "clone"
    rsc_id = "-".join(clone_id_split[:-1])
    primitive_xml = fixture_primitive(
        rsc_id,
        agent_class="ocf",
        agent_provider="pcsmock",
        agent_type="stateful",
    )
    return dedent(
        f"""
        <clone id="{clone_id}">
            {primitive_xml}
            {inner_xml}
        </clone>
        """
    )


def fixture_group(group_id, inner_xml=""):
    group_id_split = group_id.split("-")
    assert group_id_split[-1] == "group"
    rsc_id = "-".join(group_id_split[:-1])
    return dedent(
        f"""
        <group id="{group_id}">
            {fixture_primitive(rsc_id)}
            {inner_xml}
        </group>
        """
    )


def fixture_bundle(bundle_id, inner_xml=""):
    return dedent(
        f"""
        <bundle id="{bundle_id}">
          <docker image="pcs:test" replicas="4" replicas-per-host="2"
            run-command="/bin/true" network="extra_network_settings"
            options="extra_options"
          />
          {inner_xml}
        </bundle>
        """
    )


def fixture_resources(resources_xml=""):
    return f"<resources>\n  {resources_xml}\n</resources>\n"


def fixture_meta_attrs(rsc_id, nvpairs_xml=""):
    return dedent(
        f"""
        <meta_attributes id="{rsc_id}-meta_attributes">
          {nvpairs_xml}
        </meta_attributes>"""
    )


class ResourceMetaPrimitive(
    TestCase, get_assert_pcs_effect_mixin(get_cib_resources)
):
    rsc_id = "R"
    resource_fixture = staticmethod(fixture_primitive)

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_test_resource_meta")
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")

    def tearDown(self):
        self.temp_cib.close()

    def _fixture_nvpair_priority(self, value):
        return dedent(
            f"""
            <nvpair id="{self.rsc_id}-meta_attributes-priority"
                name="priority" value="{value}"
            />"""
        )

    def test_add(self):
        write_data_to_tmpfile(
            modify_cib_file(
                get_test_resource("cib-empty.xml"),
                resources=fixture_resources(self.resource_fixture(self.rsc_id)),
            ),
            self.temp_cib,
        )
        self.assert_effect(
            ["resource", "meta", self.rsc_id, "priority=2"],
            fixture_resources(
                self.resource_fixture(
                    self.rsc_id,
                    inner_xml=fixture_meta_attrs(
                        self.rsc_id,
                        nvpairs_xml=self._fixture_nvpair_priority(2),
                    ),
                ),
            ),
        )

    def test_modify(self):
        write_data_to_tmpfile(
            modify_cib_file(
                get_test_resource("cib-empty.xml"),
                resources=fixture_resources(
                    self.resource_fixture(
                        self.rsc_id,
                        inner_xml=fixture_meta_attrs(
                            self.rsc_id,
                            nvpairs_xml=self._fixture_nvpair_priority(2),
                        ),
                    )
                ),
            ),
            self.temp_cib,
        )
        self.assert_effect(
            ["resource", "meta", self.rsc_id, "priority=0"],
            fixture_resources(
                self.resource_fixture(
                    self.rsc_id,
                    inner_xml=fixture_meta_attrs(
                        self.rsc_id,
                        nvpairs_xml=self._fixture_nvpair_priority(0),
                    ),
                )
            ),
        )

    def test_remove(self):
        write_data_to_tmpfile(
            modify_cib_file(
                get_test_resource("cib-empty.xml"),
                resources=fixture_resources(
                    self.resource_fixture(
                        self.rsc_id,
                        inner_xml=fixture_meta_attrs(
                            self.rsc_id,
                            nvpairs_xml=self._fixture_nvpair_priority(2),
                        ),
                    )
                ),
            ),
            self.temp_cib,
        )
        self.assert_effect(
            ["resource", "meta", self.rsc_id, "priority="],
            fixture_resources(
                self.resource_fixture(
                    self.rsc_id,
                    inner_xml=fixture_meta_attrs(self.rsc_id),
                )
            ),
        )


class ResourceMetaGroup(ResourceMetaPrimitive):
    rsc_id = "R-group"
    resource_fixture = staticmethod(fixture_group)


class ResourceMetaClone(ResourceMetaPrimitive):
    rsc_id = "R-clone"
    resource_fixture = staticmethod(fixture_clone)


class ResourceMetaBundle(ResourceMetaPrimitive):
    rsc_id = "B"
    resource_fixture = staticmethod(fixture_bundle)
