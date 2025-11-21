from unittest import TestCase, mock

from pcs import settings
from pcs.common.pacemaker.cluster_property import ClusterPropertyMetadataDto
from pcs.common.resource_agent.dto import ResourceAgentParameterDto
from pcs.lib.commands import cluster_property

from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import get_test_resource as rc

from .crm_attribute_mixins import CrmAttributeMetadataErrorMixin

READONLY_PROPERTIES = [
    "cluster-infrastructure",
    "cluster-name",
    "dc-version",
    "have-watchdog",
    "last-lrm-refresh",
]


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class TestGetPropertiesMetadataCrmAttribute(
    CrmAttributeMetadataErrorMixin, TestCase
):
    _load_cib_when_metadata_error = False

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def metadata_error_command(self):
        return self.command()

    def command(self):
        return cluster_property.get_properties_metadata(
            self.env_assist.get_env()
        )

    def _load_fake_agent_test_metadata(self):
        self.config.runner.pcmk.is_crm_attribute_list_options_supported(
            is_supported=True
        )
        self.config.runner.pcmk.load_crm_attribute_metadata(
            agent_name="cluster-options",
            stdout="""
                <pacemaker-result api-version="2.38" request="crm_attribute --list-options=cluster --output-as xml">
                  <resource-agent name="cluster-options" version="2.1.5-7.el9">
                    <version>1.1</version>
                    <longdesc lang="en">agent longdesc</longdesc>
                    <shortdesc lang="en">agent shortdesc</shortdesc>
                    <parameters>
                      <parameter name="property-name" advanced="0" generated="0">
                        <longdesc lang="en">longdesc</longdesc>
                        <shortdesc lang="en">shortdesc</shortdesc>
                        <content type="boolean" default="false"/>
                      </parameter>
                      <parameter name="enum-property" advanced="0" generated="0">
                        <longdesc lang="en">same desc</longdesc>
                        <shortdesc lang="en">same desc</shortdesc>
                        <content type="select" default="stop">
                          <option value="stop" />
                          <option value="freeze" />
                          <option value="ignore" />
                          <option value="demote" />
                          <option value="suicide" />
                        </content>
                      </parameter>
                      <parameter name="advanced-property" advanced="0" generated="0">
                        <longdesc lang="en">longdesc</longdesc>
                        <shortdesc lang="en">
                          *** Advanced Use Only *** advanced shortdesc
                        </shortdesc>
                        <content type="boolean" default="false"/>
                      </parameter>
                    </parameters>
                  </resource-agent>
                  <status code="0" message="OK"/>
                </pacemaker-result>
            """,
        )

    def test_get_properties_metadata(self):
        self._load_fake_agent_test_metadata()
        self.assertEqual(
            self.command(),
            ClusterPropertyMetadataDto(
                properties_metadata=[
                    ResourceAgentParameterDto(
                        name="property-name",
                        shortdesc="shortdesc",
                        longdesc="shortdesc.\nlongdesc",
                        type="boolean",
                        default="false",
                        enum_values=None,
                        required=False,
                        advanced=False,
                        deprecated=False,
                        deprecated_by=[],
                        deprecated_desc=None,
                        unique_group=None,
                        reloadable=False,
                    ),
                    ResourceAgentParameterDto(
                        name="enum-property",
                        shortdesc="same desc",
                        longdesc=None,
                        type="select",
                        default="stop",
                        enum_values=[
                            "stop",
                            "freeze",
                            "ignore",
                            "demote",
                            "suicide",
                        ],
                        required=False,
                        advanced=False,
                        deprecated=False,
                        deprecated_by=[],
                        deprecated_desc=None,
                        unique_group=None,
                        reloadable=False,
                    ),
                    ResourceAgentParameterDto(
                        name="advanced-property",
                        shortdesc="advanced shortdesc",
                        longdesc="advanced shortdesc.\nlongdesc",
                        type="boolean",
                        default="false",
                        enum_values=None,
                        required=False,
                        advanced=True,
                        deprecated=False,
                        deprecated_by=[],
                        deprecated_desc=None,
                        unique_group=None,
                        reloadable=False,
                    ),
                ],
                readonly_properties=READONLY_PROPERTIES,
            ),
        )
        self.env_assist.assert_reports([])
