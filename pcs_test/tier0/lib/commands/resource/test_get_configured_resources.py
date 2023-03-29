from unittest import TestCase

from pcs.common import reports
from pcs.common.pacemaker.resource.bundle import CibResourceBundleDto
from pcs.common.pacemaker.resource.list import CibResourcesDto
from pcs.common.pacemaker.resource.primitive import CibResourcePrimitiveDto
from pcs.common.resource_agent.dto import ResourceAgentNameDto
from pcs.lib.cib.resource.bundle import GENERIC_CONTAINER_TYPES
from pcs.lib.commands import resource

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.resources_dto import ALL_RESOURCES


class GetResourceRelationsTree(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_unsupported_bundle_container_type(self):
        self.config.runner.cib.load(
            resources="""
            <resources>
              <bundle id="B1">
                <unsupported image="pcs:test"/>
                <primitive id="R1" class="ocf" type="Dummy" provider="pacemaker"/>
              </bundle>
              <primitive id="R2" class="ocf" type="Dummy" provider="pacemaker"/>
            </resources>
                """
        )
        self.assertEqual(
            CibResourcesDto(
                primitives=[
                    CibResourcePrimitiveDto(
                        id="R1",
                        agent_name=ResourceAgentNameDto(
                            standard="ocf", provider="pacemaker", type="Dummy"
                        ),
                        description=None,
                        operations=[],
                        meta_attributes=[],
                        instance_attributes=[],
                        utilization=[],
                    ),
                    CibResourcePrimitiveDto(
                        id="R2",
                        agent_name=ResourceAgentNameDto(
                            standard="ocf", provider="pacemaker", type="Dummy"
                        ),
                        description=None,
                        operations=[],
                        meta_attributes=[],
                        instance_attributes=[],
                        utilization=[],
                    ),
                ],
                clones=[],
                groups=[],
                bundles=[
                    CibResourceBundleDto(
                        id="B1",
                        description=None,
                        member_id="R1",
                        container_type=None,
                        container_options=None,
                        network=None,
                        port_mappings=[],
                        storage_mappings=[],
                        meta_attributes=[],
                        instance_attributes=[],
                    ),
                ],
            ),
            resource.get_configured_resources(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RESOURCE_BUNDLE_UNSUPPORTED_CONTAINER_TYPE,
                    bundle_id="B1",
                    supported_container_types=sorted(GENERIC_CONTAINER_TYPES),
                    updating_options=False,
                )
            ]
        )

    def test_success(self):
        self.config.runner.cib.load(filename="cib-resources.xml")
        self.assertEqual(
            ALL_RESOURCES,
            resource.get_configured_resources(self.env_assist.get_env()),
        )
