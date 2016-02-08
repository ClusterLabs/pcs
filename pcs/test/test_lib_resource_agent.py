from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os.path
import unittest

from lxml import etree

try:
    import unittest.mock as mock
except ImportError:
    import mock

from pcs.test.library_test_tools import LibraryAssertionMixin
from pcs.test.library_test_tools import assert_xml_equal
from pcs.test.library_test_tools import XmlManipulation as XmlMan


from pcs import settings
from pcs.lib import error_codes
from pcs.lib import resource_agent as lib_ra
from pcs.lib.errors import ReportItemSeverity as Severities


class LibraryResourceTest(unittest.TestCase, LibraryAssertionMixin):
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
        self.assert_raise_library_error(
            lambda: lib_ra._get_parameter(etree.XML(xml)),
            (
                Severities.ERROR,
                error_codes.INVALID_METADATA_FORMAT,
                {}
            )
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
        self.assert_raise_library_error(
            lambda: lib_ra._get_parameter(etree.XML(xml)),
            (
                Severities.ERROR,
                error_codes.INVALID_METADATA_FORMAT,
                {}
            )
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
        self.assert_raise_library_error(
            lambda: lib_ra._get_agent_parameters(etree.XML(xml)),
            (
                Severities.ERROR,
                error_codes.INVALID_METADATA_FORMAT,
                {}
            )
        )


class GetFenceAgentMetadataTest(LibraryResourceTest):
    @mock.patch("pcs.lib.resource_agent._is_bin_runnable")
    def test_invalid_agent_name(self, mock_obj):
        mock_obj.return_value = True
        agent_name = "agent"
        self.assert_raise_library_error(
            lambda: lib_ra.get_fence_agent_metadata(agent_name),
            (
                Severities.ERROR,
                error_codes.INVALID_RESOURCE_NAME,
                {"agent_name": agent_name}
            )
        )

    @mock.patch("pcs.lib.resource_agent._is_bin_runnable")
    def test_relative_path_name(self, mock_obj):
        mock_obj.return_value = True
        agent_name = "fence_agent/../fence"
        self.assert_raise_library_error(
            lambda: lib_ra.get_fence_agent_metadata(agent_name),
            (
                Severities.ERROR,
                error_codes.INVALID_RESOURCE_NAME,
                {"agent_name": agent_name}
            )
        )

    @mock.patch("pcs.lib.resource_agent._is_bin_runnable")
    def test_not_runnable(self, mock_obj):
        mock_obj.return_value = False
        agent_name = "fence_agent"
        self.assert_raise_library_error(
            lambda: lib_ra.get_fence_agent_metadata(agent_name),
            (
                Severities.ERROR,
                error_codes.INVALID_RESOURCE_NAME,
                {"agent_name": agent_name}
            )
        )

    @mock.patch("pcs.lib.resource_agent._is_bin_runnable")
    @mock.patch("pcs.utils.run")
    def test_execution_failed(self, mock_run, mock_is_runnable):
        mock_is_runnable.return_value = True
        mock_run.return_value = ("", 1)
        agent_name = "fence_ipmi"
        self.assert_raise_library_error(
            lambda: lib_ra.get_fence_agent_metadata(agent_name),
            (
                Severities.ERROR,
                error_codes.UNABLE_TO_GET_AGENT_METADATA,
                {"agent_name": agent_name}
            )
        )

    @mock.patch("pcs.lib.resource_agent._is_bin_runnable")
    @mock.patch("pcs.utils.run")
    def test_invalid_xml(self, mock_run, mock_is_runnable):
        mock_run.return_value = ("not xml", 0)
        mock_is_runnable.return_value = True
        agent_name = "fence_ipmi"
        self.assert_raise_library_error(
            lambda: lib_ra.get_fence_agent_metadata(agent_name),
            (
                Severities.ERROR,
                error_codes.UNABLE_TO_GET_AGENT_METADATA,
                {"agent_name": agent_name}
            )
        )

    @mock.patch("pcs.lib.resource_agent._is_bin_runnable")
    @mock.patch("pcs.utils.run")
    def test_success(self, mock_run, mock_is_runnable):
        agent_name = "fence_ipmi"
        xml = "<xml />"
        mock_run.return_value = (xml, 0)
        mock_is_runnable.return_value = True
        out_dom = lib_ra.get_fence_agent_metadata(agent_name)
        script_path = os.path.join(settings.fence_agent_binaries, agent_name)

        mock_run.assert_called_once_with(
            [script_path, "-o", "metadata"]
        )
        assert_xml_equal(xml, str(XmlMan(out_dom)))


class GetOcfResourceAgentMetadataTest(LibraryResourceTest):
    @mock.patch("pcs.lib.resource_agent._is_bin_runnable")
    def test_relative_path_provider(self, mock_is_runnable):
        mock_is_runnable.return_value = True
        provider = "provider/../provider2"
        agent = "agent"
        self.assert_raise_library_error(
            lambda: lib_ra._get_ocf_resource_agent_metadata(provider, agent),
            (
                Severities.ERROR,
                error_codes.INVALID_RESOURCE_NAME,
                {"agent_name": "ocf::{0}:{1}".format(provider, agent)}
            )
        )

    @mock.patch("pcs.lib.resource_agent._is_bin_runnable")
    def test_relative_path_agent(self, mock_is_runnable):
        mock_is_runnable.return_value = True
        provider = "provider"
        agent = "agent/../agent2"
        self.assert_raise_library_error(
            lambda: lib_ra._get_ocf_resource_agent_metadata(provider, agent),
            (
                Severities.ERROR,
                error_codes.INVALID_RESOURCE_NAME,
                {"agent_name": "ocf::{0}:{1}".format(provider, agent)}
            )
        )

    @mock.patch("pcs.lib.resource_agent._is_bin_runnable")
    def test_not_runnable(self, mock_is_runnable):
        mock_is_runnable.return_value = False
        provider = "provider"
        agent = "agent"
        self.assert_raise_library_error(
            lambda: lib_ra._get_ocf_resource_agent_metadata(provider, agent),
            (
                Severities.ERROR,
                error_codes.INVALID_RESOURCE_NAME,
                {"agent_name": "ocf::{0}:{1}".format(provider, agent)}
            )
        )

    @mock.patch("pcs.lib.resource_agent._is_bin_runnable")
    @mock.patch("pcs.utils.run")
    def test_execution_failed(self, mock_run, mock_is_runnable):
        provider = "provider"
        agent = "agent"
        mock_run.return_value = ("", 1)
        mock_is_runnable.return_value = True
        self.assert_raise_library_error(
            lambda: lib_ra._get_ocf_resource_agent_metadata(provider, agent),
            (
                Severities.ERROR,
                error_codes.UNABLE_TO_GET_AGENT_METADATA,
                {"agent_name": "ocf::{0}:{1}".format(provider, agent)}
            )
        )

    @mock.patch("pcs.lib.resource_agent._is_bin_runnable")
    @mock.patch("pcs.utils.run")
    def test_invalid_xml(self, mock_run, mock_is_runnable):
        provider = "provider"
        agent = "agent"
        mock_run.return_value = ("not xml", 0)
        mock_is_runnable.return_value = True
        self.assert_raise_library_error(
            lambda: lib_ra._get_ocf_resource_agent_metadata(provider, agent),
            (
                Severities.ERROR,
                error_codes.UNABLE_TO_GET_AGENT_METADATA,
                {"agent_name": "ocf::{0}:{1}".format(provider, agent)}
            )
        )

    @mock.patch("pcs.lib.resource_agent._is_bin_runnable")
    @mock.patch("pcs.utils.run")
    def test_success(self, mock_run, mock_is_runnable):
        provider = "provider"
        agent = "agent"
        xml = "<xml />"
        mock_run.return_value = (xml, 0)
        mock_is_runnable.return_value = True
        out_dom = lib_ra._get_ocf_resource_agent_metadata(provider, agent)
        script_path = os.path.join(settings.ocf_resources, provider, agent)

        mock_run.assert_called_once_with(
            [script_path, "meta-data"],
            env_extend={"OCF_ROOT": settings.ocf_root}
        )
        assert_xml_equal(xml, str(XmlMan(out_dom)))


class GetNagiosResourceAgentMetadataTest(LibraryResourceTest):
    def test_relative_path_name(self):
        agent = "agent/../agent2"
        self.assert_raise_library_error(
            lambda: lib_ra._get_nagios_resource_agent_metadata(agent),
            (
                Severities.ERROR,
                error_codes.INVALID_RESOURCE_NAME,
                {"agent_name": "nagios:" + agent}
            )
        )

    @mock.patch("lxml.etree.parse")
    def test_file_opening_exception(self, mock_obj):
        agent = "agent"
        mock_obj.side_effect = IOError()
        self.assert_raise_library_error(
            lambda: lib_ra._get_nagios_resource_agent_metadata(agent),
            (
                Severities.ERROR,
                error_codes.UNABLE_TO_GET_AGENT_METADATA,
                {"agent_name": "nagios:" + agent}
            )
        )

    @mock.patch("lxml.etree.parse")
    def test_invalid_xml(self, mock_obj):
        agent = "agent"
        mock_obj.side_effect = etree.XMLSyntaxError(None, None, None, None)
        self.assert_raise_library_error(
            lambda: lib_ra._get_nagios_resource_agent_metadata(agent),
            (
                Severities.ERROR,
                error_codes.UNABLE_TO_GET_AGENT_METADATA,
                {"agent_name": "nagios:" + agent}
            )
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
        self.assert_raise_library_error(
            lambda: lib_ra.get_agent_desc(etree.XML(xml)),
            (
                Severities.ERROR,
                error_codes.INVALID_METADATA_FORMAT,
                {}
            )
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
                {"name": "another_param"}
            ],
            lib_ra._filter_fence_agent_parameters(params)
        )


class GetResourceAgentMetadata(LibraryResourceTest):
    def test_unsupported_class(self):
        agent = "class::provider:agent"
        self.assert_raise_library_error(
            lambda: lib_ra.get_resource_agent_metadata(agent),
            (
                Severities.ERROR,
                error_codes.UNSUPPORTED_RESOURCE_AGENT,
                {}
            )
        )

    def test_ocf_no_provider(self):
        agent = "ocf::agent"
        self.assert_raise_library_error(
            lambda: lib_ra.get_resource_agent_metadata(agent),
            (
                Severities.ERROR,
                error_codes.UNSUPPORTED_RESOURCE_AGENT,
                {}
            )
        )

    @mock.patch("pcs.lib.resource_agent._get_ocf_resource_agent_metadata")
    def test_ocf_ok(self, mock_obj):
        agent = "ocf::provider:agent"
        lib_ra.get_resource_agent_metadata(agent)
        mock_obj.assert_called_once_with("provider", "agent")

    @mock.patch("pcs.lib.resource_agent._get_nagios_resource_agent_metadata")
    def test_nagios_ok(self, mock_obj):
        agent = "nagios:agent"
        lib_ra.get_resource_agent_metadata(agent)
        mock_obj.assert_called_once_with("agent")
