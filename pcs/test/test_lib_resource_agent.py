from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
import os.path

from lxml import etree

from pcs.test.tools.assertions import (
    ExtendedAssertionsMixin,
    assert_xml_equal,
)
from pcs.test.tools.pcs_mock import mock
from pcs.test.tools.xml import XmlManipulation as XmlMan


from pcs import settings
from pcs.lib import resource_agent as lib_ra
from pcs.lib.external import CommandRunner


class LibraryResourceTest(TestCase, ExtendedAssertionsMixin):
    pass


class GetParameterTest(LibraryResourceTest):
    def test_with_all_data(self):
        xml = """
            <parameter name="test_param" required="1">
                <longdesc>
                    Long description
                </longdesc>
                <shortdesc>short description</shortdesc>
                <content type="test_type" default="default_value" />
            </parameter>
        """
        self.assertEqual(
            {
                "name": "test_param",
                "longdesc": "Long description",
                "shortdesc": "short description",
                "type": "test_type",
                "required": True,
                "default": "default_value"
            },
            lib_ra._get_parameter(etree.XML(xml))
        )

    def test_minimal_data(self):
        xml = '<parameter name="test_param" />'
        self.assertEqual(
            {
                "name": "test_param",
                "longdesc": "",
                "shortdesc": "",
                "type": "string",
                "required": False,
                "default": None
            },
            lib_ra._get_parameter(etree.XML(xml))
        )

    def test_no_name(self):
        xml = '<parameter />'
        self.assertRaises(
            lib_ra.InvalidMetadataFormat,
            lambda: lib_ra._get_parameter(etree.XML(xml))
        )

    def test_invalid_element(self):
        xml = """
            <param name="test_param" required="1">
                <longdesc>
                    Long description
                </longdesc>
                <shortdesc>short description</shortdesc>
                <content type="test_type" default="default_value" />
            </param>
        """
        self.assertRaises(
            lib_ra.InvalidMetadataFormat,
            lambda: lib_ra._get_parameter(etree.XML(xml))
        )


class GetAgentParametersTest(LibraryResourceTest):
    def test_all_data(self):
        xml = """
            <resource-agent>
                <parameters>
                    <parameter name="test_param" required="1">
                        <longdesc>
                            Long description
                        </longdesc>
                        <shortdesc>short description</shortdesc>
                        <content type="test_type" default="default_value" />
                    </parameter>
                    <parameter name="another parameter"/>
                </parameters>
            </resource-agent>
        """
        self.assertEqual(
            [
                {
                    "name": "test_param",
                    "longdesc": "Long description",
                    "shortdesc": "short description",
                    "type": "test_type",
                    "required": True,
                    "default": "default_value"
                },
                {
                    "name": "another parameter",
                    "longdesc": "",
                    "shortdesc": "",
                    "type": "string",
                    "required": False,
                    "default": None
                }
            ],
            lib_ra._get_agent_parameters(etree.XML(xml))
        )

    def test_empty_parameters(self):
        xml = """
            <resource-agent>
                <parameters />
            </resource-agent>
        """
        self.assertEqual(0, len(lib_ra._get_agent_parameters(etree.XML(xml))))

    def test_no_parameters(self):
        xml = """
            <resource-agent>
                <longdesc />
            </resource-agent>
        """
        self.assertEqual(0, len(lib_ra._get_agent_parameters(etree.XML(xml))))

    def test_invalid_format(self):
        xml = """
            <resource-agent>
                <parameters>
                    <parameter />
                </parameters>
            </resource-agent>
        """
        self.assertRaises(
            lib_ra.InvalidMetadataFormat,
            lambda: lib_ra._get_agent_parameters(etree.XML(xml))
        )


class GetFenceAgentMetadataTest(LibraryResourceTest):
    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_invalid_agent_name(self, mock_obj):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_obj.return_value = True
        agent_name = "agent"
        self.assert_raises(
            lib_ra.AgentNotFound,
            lambda: lib_ra.get_fence_agent_metadata(mock_runner, agent_name),
            {"agent": agent_name}
        )

        mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_relative_path_name(self, mock_obj):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_obj.return_value = True
        agent_name = "fence_agent/../fence"
        self.assert_raises(
            lib_ra.AgentNotFound,
            lambda: lib_ra.get_fence_agent_metadata(mock_runner, agent_name),
            {"agent": agent_name}
        )

        mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_not_runnable(self, mock_obj):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_obj.return_value = False
        agent_name = "fence_agent"

        self.assert_raises(
            lib_ra.AgentNotFound,
            lambda: lib_ra.get_fence_agent_metadata(mock_runner, agent_name),
            {"agent": agent_name}
        )
        mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_execution_failed(self, mock_is_runnable):
        mock_is_runnable.return_value = True
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = ("error", 1)
        agent_name = "fence_ipmi"

        self.assert_raises(
            lib_ra.UnableToGetAgentMetadata,
            lambda: lib_ra.get_fence_agent_metadata(mock_runner, agent_name),
            {"agent": agent_name}
        )

        script_path = os.path.join(settings.fence_agent_binaries, agent_name)
        mock_runner.run.assert_called_once_with(
            [script_path, "-o", "metadata"], ignore_stderr=True
        )

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_invalid_xml(self, mock_is_runnable):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = ("not xml", 0)
        mock_is_runnable.return_value = True
        agent_name = "fence_ipmi"
        self.assert_raises(
            lib_ra.UnableToGetAgentMetadata,
            lambda: lib_ra.get_fence_agent_metadata(mock_runner, agent_name),
            {"agent": agent_name}
        )

        script_path = os.path.join(settings.fence_agent_binaries, agent_name)
        mock_runner.run.assert_called_once_with(
            [script_path, "-o", "metadata"], ignore_stderr=True
        )

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_success(self, mock_is_runnable):
        agent_name = "fence_ipmi"
        xml = "<xml />"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (xml, 0)
        mock_is_runnable.return_value = True

        out_dom = lib_ra.get_fence_agent_metadata(mock_runner, agent_name)

        script_path = os.path.join(settings.fence_agent_binaries, agent_name)
        mock_runner.run.assert_called_once_with(
            [script_path, "-o", "metadata"], ignore_stderr=True
        )
        assert_xml_equal(xml, str(XmlMan(out_dom)))


class GetOcfResourceAgentMetadataTest(LibraryResourceTest):
    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_relative_path_provider(self, mock_is_runnable):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_is_runnable.return_value = True
        provider = "provider/../provider2"
        agent = "agent"

        self.assert_raises(
            lib_ra.AgentNotFound,
            lambda: lib_ra._get_ocf_resource_agent_metadata(
                mock_runner, provider, agent
            ),
            {"agent": "ocf:{0}:{1}".format(provider, agent)}
        )

        mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_relative_path_agent(self, mock_is_runnable):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_is_runnable.return_value = True
        provider = "provider"
        agent = "agent/../agent2"

        self.assert_raises(
            lib_ra.AgentNotFound,
            lambda: lib_ra._get_ocf_resource_agent_metadata(
                mock_runner, provider, agent
            ),
            {"agent": "ocf:{0}:{1}".format(provider, agent)}
        )

        mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_not_runnable(self, mock_is_runnable):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_is_runnable.return_value = False
        provider = "provider"
        agent = "agent"

        self.assert_raises(
            lib_ra.AgentNotFound,
            lambda: lib_ra._get_ocf_resource_agent_metadata(
                mock_runner, provider, agent
            ),
            {"agent": "ocf:{0}:{1}".format(provider, agent)}
        )

        mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_execution_failed(self, mock_is_runnable):
        provider = "provider"
        agent = "agent"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = ("error", 1)
        mock_is_runnable.return_value = True

        self.assert_raises(
            lib_ra.UnableToGetAgentMetadata,
            lambda: lib_ra._get_ocf_resource_agent_metadata(
                mock_runner, provider, agent
            ),
            {"agent": "ocf:{0}:{1}".format(provider, agent)}
        )

        script_path = os.path.join(settings.ocf_resources, provider, agent)
        mock_runner.run.assert_called_once_with(
            [script_path, "meta-data"],
            env_extend={"OCF_ROOT": settings.ocf_root},
            ignore_stderr=True
        )

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_invalid_xml(self, mock_is_runnable):
        provider = "provider"
        agent = "agent"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = ("not xml", 0)
        mock_is_runnable.return_value = True

        self.assert_raises(
            lib_ra.UnableToGetAgentMetadata,
            lambda: lib_ra._get_ocf_resource_agent_metadata(
                mock_runner, provider, agent
            ),
            {"agent": "ocf:{0}:{1}".format(provider, agent)}
        )

        script_path = os.path.join(settings.ocf_resources, provider, agent)
        mock_runner.run.assert_called_once_with(
            [script_path, "meta-data"],
            env_extend={"OCF_ROOT": settings.ocf_root},
            ignore_stderr=True
        )

    @mock.patch("pcs.lib.resource_agent.is_path_runnable")
    def test_success(self, mock_is_runnable):
        provider = "provider"
        agent = "agent"
        xml = "<xml />"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (xml, 0)
        mock_is_runnable.return_value = True

        out_dom = lib_ra._get_ocf_resource_agent_metadata(
            mock_runner, provider, agent
        )

        script_path = os.path.join(settings.ocf_resources, provider, agent)
        mock_runner.run.assert_called_once_with(
            [script_path, "meta-data"],
            env_extend={"OCF_ROOT": settings.ocf_root},
            ignore_stderr=True
        )
        assert_xml_equal(xml, str(XmlMan(out_dom)))


class GetNagiosResourceAgentMetadataTest(LibraryResourceTest):
    def test_relative_path_name(self):
        agent = "agent/../agent2"
        self.assert_raises(
            lib_ra.AgentNotFound,
            lambda: lib_ra._get_nagios_resource_agent_metadata(agent),
            {"agent": "nagios:" + agent}
        )

    @mock.patch("lxml.etree.parse")
    def test_file_opening_exception(self, mock_obj):
        agent = "agent"
        mock_obj.side_effect = IOError()
        self.assert_raises(
            lib_ra.UnableToGetAgentMetadata,
            lambda: lib_ra._get_nagios_resource_agent_metadata(agent),
            {"agent": "nagios:" + agent}
        )

    @mock.patch("lxml.etree.parse")
    def test_invalid_xml(self, mock_obj):
        agent = "agent"
        mock_obj.side_effect = etree.XMLSyntaxError(None, None, None, None)
        self.assert_raises(
            lib_ra.UnableToGetAgentMetadata,
            lambda: lib_ra._get_nagios_resource_agent_metadata(agent),
            {"agent": "nagios:" + agent}
        )

    @mock.patch("lxml.etree.parse")
    def test_success(self, mock_obj):
        agent = "agent"
        xml = "<xml />"
        mock_obj.return_value = etree.ElementTree(etree.XML(xml))
        out_dom = lib_ra._get_nagios_resource_agent_metadata(agent)
        metadata_path = os.path.join(
            settings.nagios_metadata_path, agent + ".xml"
        )

        mock_obj.assert_called_once_with(metadata_path)
        assert_xml_equal(xml, str(XmlMan(out_dom)))


class GetAgentDescTest(LibraryResourceTest):
    def test_invalid_metadata_format(self):
        xml = "<xml />"
        self.assertRaises(
            lib_ra.InvalidMetadataFormat,
            lambda: lib_ra.get_agent_desc(etree.XML(xml))
        )

    def test_no_desc(self):
        xml = "<resource-agent />"
        expected = {
            "longdesc": "",
            "shortdesc": ""
        }
        self.assertEqual(expected, lib_ra.get_agent_desc(etree.XML(xml)))

    def test_shortdesc_attribute(self):
        xml = '<resource-agent shortdesc="short description" />'
        expected = {
            "longdesc": "",
            "shortdesc": "short description"
        }
        self.assertEqual(expected, lib_ra.get_agent_desc(etree.XML(xml)))

    def test_shortdesc_element(self):
        xml = """
            <resource-agent>
                <shortdesc>short description</shortdesc>
            </resource-agent>
        """
        expected = {
            "longdesc": "",
            "shortdesc": "short description"
        }
        self.assertEqual(expected, lib_ra.get_agent_desc(etree.XML(xml)))

    def test_longdesc(self):
        xml = """
            <resource-agent>
                <longdesc>long description</longdesc>
            </resource-agent>
        """
        expected = {
            "longdesc": "long description",
            "shortdesc": ""
        }
        self.assertEqual(expected, lib_ra.get_agent_desc(etree.XML(xml)))

    def test_longdesc_and_shortdesc_attribute(self):
        xml = """
            <resource-agent shortdesc="short_desc">
                <longdesc>long description</longdesc>
            </resource-agent>
        """
        expected = {
            "longdesc": "long description",
            "shortdesc": "short_desc"
        }
        self.assertEqual(expected, lib_ra.get_agent_desc(etree.XML(xml)))

    def test_longdesc_and_shortdesc_element(self):
        xml = """
            <resource-agent>
                <shortdesc>short_desc</shortdesc>
                <longdesc>long description</longdesc>
            </resource-agent>
        """
        expected = {
            "longdesc": "long description",
            "shortdesc": "short_desc"
        }
        self.assertEqual(expected, lib_ra.get_agent_desc(etree.XML(xml)))


class FilterFenceAgentParametersTest(LibraryResourceTest):
    def test_filter(self):
        params = [
            {"name": "debug"},
            {"name": "valid_param"},
            {"name": "verbose"},
            {"name": "help"},
            {"name": "action"},
            {"name": "another_param"},
            {"name": "version"},
        ]
        self.assertEqual(
            [
                {"name": "valid_param"},
                {
                    "name": "action",
                    "required": False,
                    "shortdesc":
                        "\nWARNING: specifying 'action' is deprecated and not" +
                        " necessary with current Pacemaker versions"
                },
                {"name": "another_param"}
            ],
            lib_ra._filter_fence_agent_parameters(params)
        )

    def test_action(self):
        params = [
            {
                "name": "action",
                "required": True,
                "shortdesc": "Action"
            }
        ]

        self.assertEqual(
            [
                {
                    "name": "action",
                    "required": False,
                    "shortdesc":
                        "Action\nWARNING: specifying 'action' is deprecated " +
                        "and not necessary with current Pacemaker versions"
                }
            ],
            lib_ra._filter_fence_agent_parameters(params)
        )


class GetResourceAgentMetadata(LibraryResourceTest):
    def test_unsupported_class(self):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        agent = "class:provider:agent"
        self.assert_raises(
            lib_ra.UnsupportedResourceAgent,
            lambda: lib_ra.get_resource_agent_metadata(mock_runner, agent),
            {"agent": agent}
        )

        mock_runner.run.assert_not_called()

    def test_ocf_no_provider(self):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        agent = "ocf:agent"

        self.assert_raises(
            lib_ra.UnsupportedResourceAgent,
            lambda: lib_ra.get_resource_agent_metadata(mock_runner, agent),
            {"agent": agent}
        )

        mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.resource_agent._get_ocf_resource_agent_metadata")
    def test_ocf_ok(self, mock_obj):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        agent = "ocf:provider:agent"

        lib_ra.get_resource_agent_metadata(mock_runner, agent)

        mock_obj.assert_called_once_with(mock_runner, "provider", "agent")

    @mock.patch("pcs.lib.resource_agent._get_nagios_resource_agent_metadata")
    def test_nagios_ok(self, mock_obj):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        agent = "nagios:agent"

        lib_ra.get_resource_agent_metadata(mock_runner, agent)

        mock_obj.assert_called_once_with("agent")
        mock_runner.run.assert_not_called()


class GetPcmkAdvancedStonithParametersTest(LibraryResourceTest):
    def test_all_advanced(self):
        xml = """
            <resource-agent>
                <parameters>
                    <parameter name="test_param" required="0">
                        <longdesc>
                             Long description
                        </longdesc>
                        <shortdesc>
                             Advanced use only: short description
                        </shortdesc>
                        <content type="test_type" default="default_value" />
                    </parameter>
                    <parameter name="another parameter"/>
                </parameters>
            </resource-agent>
        """
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (xml, 0)
        self.assertEqual(
            [
                {
                    "name": "test_param",
                    "longdesc":
                        "Advanced use only: short description\nLong "
                        "description",
                    "shortdesc": "Advanced use only: short description",
                    "type": "test_type",
                    "required": False,
                    "default": "default_value",
                    "advanced": True
                },
                {
                    "name": "another parameter",
                    "longdesc": "",
                    "shortdesc": "",
                    "type": "string",
                    "required": False,
                    "default": None,
                    "advanced": False
                }
            ],
            lib_ra._get_pcmk_advanced_stonith_parameters(mock_runner)
        )
        mock_runner.run.assert_called_once_with(
            [settings.stonithd_binary, "metadata"], ignore_stderr=True
        )

    def test_failed_to_get_xml(self):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = ("", 1)
        self.assert_raises(
            lib_ra.UnableToGetAgentMetadata,
            lambda: lib_ra._get_pcmk_advanced_stonith_parameters(mock_runner),
            {"agent": "stonithd"}
        )

        mock_runner.run.assert_called_once_with(
            [settings.stonithd_binary, "metadata"], ignore_stderr=True
        )

    def test_invalid_xml(self):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = ("invalid XML", 0)
        self.assertRaises(
            lib_ra.InvalidMetadataFormat,
            lambda: lib_ra._get_pcmk_advanced_stonith_parameters(mock_runner)
        )

        mock_runner.run.assert_called_once_with(
            [settings.stonithd_binary, "metadata"], ignore_stderr=True
        )


class GetActionTest(LibraryResourceTest):
    def test_name_and_params(self):
        xml = '''
            <action name="required" param="value" another_param="same_value" />
        '''
        self.assertEqual(
            lib_ra._get_action(etree.XML(xml)),
            {
                "name": "required",
                "another_param": "same_value",
                "param": "value"
            }
        )

    def test_name_only(self):
        xml = '''
            <action name="required" />
        '''
        self.assertEqual(
            lib_ra._get_action(etree.XML(xml)), {"name": "required"}
        )

    def test_empty(self):
        xml = '<action />'
        self.assertRaises(
            lib_ra.InvalidMetadataFormat,
            lambda: lib_ra._get_action(etree.XML(xml))
        )

    def test_no_name(self):
        xml = '<action param="value" another_param="same_value" />'
        self.assertRaises(
            lib_ra.InvalidMetadataFormat,
            lambda: lib_ra._get_action(etree.XML(xml))
        )

    def test_not_action_element(self):
        xml = '<actions param="value" another_param="same_value" />'
        self.assertRaises(
            lib_ra.InvalidMetadataFormat,
            lambda: lib_ra._get_action(etree.XML(xml))
        )


class GetAgentActionsTest(LibraryResourceTest):
    def test_multiple_actions(self):
        xml = """
            <resource-agent>
                <actions>
                    <action name="on" automatic="0"/>
                    <action name="off" />
                    <action name="reboot" />
                    <action name="status" />
                </actions>
            </resource-agent>
        """
        self.assertEqual(
            lib_ra.get_agent_actions(etree.XML(xml)),
            [
                {
                    "name": "on",
                    "automatic": "0"
                },
                {"name": "off"},
                {"name": "reboot"},
                {"name": "status"}
            ]
        )

    def test_root_is_not_resource_agent(self):
        xml = """
            <agent>
                <actions>
                    <action name="on" automatic="0"/>
                    <action name="off" />
                </actions>
            </agent>
        """
        self.assertRaises(
            lib_ra.InvalidMetadataFormat,
            lambda: lib_ra._get_action(etree.XML(xml))
        )

    def test_action_without_name(self):
        xml = """
            <resource-agent>
                <actions>
                    <action name="on" automatic="0"/>
                    <action />
                    <action name="reboot" />
                    <action name="status" />
                </actions>
            </resource-agent>
        """
        self.assertRaises(
            lib_ra.InvalidMetadataFormat,
            lambda: lib_ra._get_action(etree.XML(xml))
        )

    def test_empty_actions(self):
        xml = """
            <resource-agent>
                <actions />
            </resource-agent>
        """
        self.assertEqual(len(lib_ra.get_agent_actions(etree.XML(xml))), 0)

    def test_no_actions(self):
        xml = "<resource-agent />"
        self.assertEqual(len(lib_ra.get_agent_actions(etree.XML(xml))), 0)


class ValidateResourceInstanceAttributesTest(LibraryResourceTest):
    def setUp(self):
        self.xml = etree.XML("<xml />")
        self.params = [
            {
                "name": "test_param",
                "longdesc": "Long description",
                "shortdesc": "short description",
                "type": "string",
                "required": False,
                "default": "default_value"
            },
            {
                "name": "required_param",
                "longdesc": "",
                "shortdesc": "",
                "type": "boolean",
                "required": True,
                "default": None
            },
            {
                "name": "another parameter",
                "longdesc": "",
                "shortdesc": "",
                "type": "string",
                "required": True,
                "default": None
            }
        ]

    def test_only_required(self):
        attrs = ["another parameter", "required_param"]
        self.assertEqual(
            lib_ra._validate_instance_attributes(self.params, attrs),
            ([], [])
        )

    def test_optional(self):
        attrs = ["another parameter", "required_param", "test_param"]
        self.assertEqual(
            lib_ra._validate_instance_attributes(self.params, attrs),
            ([], [])
        )

    def test_bad_attrs(self):
        attrs = ["another parameter", "required_param", "unknown_param"]
        self.assertEqual(
            lib_ra._validate_instance_attributes(self.params, attrs),
            (["unknown_param"], [])
        )

    def test_bad_attrs_and_missing_required(self):
        attrs = ["unknown_param", "test_param"]
        bad, missing = lib_ra._validate_instance_attributes(self.params, attrs)
        self.assertEqual(["unknown_param"], bad)
        self.assertEqual(
            sorted(["another parameter", "required_param"]),
            sorted(missing)
        )


@mock.patch("pcs.lib.resource_agent._validate_instance_attributes")
@mock.patch("pcs.lib.resource_agent.get_fence_agent_parameters")
@mock.patch("pcs.lib.resource_agent.get_fence_agent_metadata")
@mock.patch("pcs.lib.resource_agent.get_resource_agent_parameters")
@mock.patch("pcs.lib.resource_agent.get_resource_agent_metadata")
class ValidateInstanceAttributesTest(LibraryResourceTest):
    def setUp(self):
        self.runner = mock.MagicMock(spec_set=CommandRunner)
        self.valid_ret_val = (
            ["test_parm", "another"], ["nothing here", "port"]
        )
        self.xml = etree.XML("<xml />")
        self.instance_attrs = ["param", "another_one"]
        self.attrs = [
            {
                "name": "test_param",
                "longdesc": "Long description",
                "shortdesc": "short description",
                "type": "string",
                "required": False,
                "default": "default_value"
            },
            {
                "name": "required_param",
                "longdesc": "",
                "shortdesc": "",
                "type": "boolean",
                "required": True,
                "default": None
            }
        ]

    def test_resource(
        self, res_met_mock, res_par_mock, fen_met_mock, fen_par_mock, valid_mock
    ):
        agent = "ocf:pacemaker:Dummy"
        res_met_mock.return_value = self.xml
        res_par_mock.return_value = self.attrs
        valid_mock.return_value = self.valid_ret_val
        self.assertEqual(
            self.valid_ret_val,
            lib_ra.validate_instance_attributes(
                self.runner, self.instance_attrs, agent
            )
        )
        res_met_mock.assert_called_once_with(self.runner, agent)
        res_par_mock.assert_called_once_with(self.xml)
        valid_mock.assert_called_once_with(self.attrs, self.instance_attrs)
        fen_met_mock.assert_not_called()
        fen_par_mock.assert_not_called()

    def test_fence(
        self, res_met_mock, res_par_mock, fen_met_mock, fen_par_mock, valid_mock
    ):
        agent = "stonith:fence_test"
        fen_met_mock.return_value = self.xml
        fen_par_mock.return_value = self.attrs
        valid_mock.return_value = self.valid_ret_val
        self.assertEqual(
            (["test_parm", "another"], ["nothing here"]),
            lib_ra.validate_instance_attributes(
                self.runner, self.instance_attrs, agent
            )
        )
        fen_met_mock.assert_called_once_with(self.runner, "fence_test")
        fen_par_mock.assert_called_once_with(self.runner, self.xml)
        valid_mock.assert_called_once_with(self.attrs, self.instance_attrs)
        res_met_mock.assert_not_called()
        res_par_mock.assert_not_called()
