import json
from textwrap import dedent
from unittest import (
    TestCase,
    mock,
)

from pcs.cli.cluster_property import command as cluster_property
from pcs.cli.common.errors import CmdLineInputError
from pcs.common.interface import dto
from pcs.common.pacemaker.cluster_property import ClusterPropertyMetadataDto
from pcs.common.pacemaker.nvset import (
    CibNvpairDto,
    CibNvsetDto,
    ListCibNvsetDto,
)
from pcs.common.reports import codes as report_codes
from pcs.common.resource_agent.dto import ResourceAgentParameterDto

from pcs_test.tools.misc import dict_to_modifiers

FIXTURE_PROPERTY_METADATA = ClusterPropertyMetadataDto(
    properties_metadata=[
        ResourceAgentParameterDto(
            name="property_name",
            shortdesc="Duplicate property",
            longdesc=None,
            type="string",
            default="duplicate_default",
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
            name="property_name",
            shortdesc=None,
            longdesc=None,
            type="string",
            default="default",
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
            name="property_advanced",
            shortdesc=None,
            longdesc=None,
            type="string",
            default="default",
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
    readonly_properties=["readonly"],
)

FIXTURE_PROPERTIES_CONFIG = ListCibNvsetDto(
    nvsets=[
        CibNvsetDto(
            id="cib-bootstrap-options",
            options={},
            rule=None,
            nvpairs=[
                CibNvpairDto(id="id1", name="property_name", value="value1")
            ],
        )
    ]
)


class TestSetProperty(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster_property"])
        self.cluster_property = mock.Mock(spec_set=["set_properties"])
        self.lib.cluster_property = self.cluster_property

    def _call_cmd(self, argv, modifiers=None):
        cluster_property.set_property(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.cluster_property.set_properties.assert_not_called()

    def test_empty_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["", ""])
        self.assertEqual(cm.exception.message, "missing value of '' option")
        self.cluster_property.set_properties.assert_not_called()

    def test_option_missing_value(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["a=1", "b"])
        self.assertEqual(cm.exception.message, "missing value of 'b' option")
        self.cluster_property.set_properties.assert_not_called()

    def test_value_missing_option_name(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["=1", "b=2"])
        self.assertEqual(cm.exception.message, "missing key in '=1' option")
        self.cluster_property.set_properties.assert_not_called()

    def test_option_multiple_values(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["a=1", "a=2", "b=2", "b="])
        self.assertEqual(
            cm.exception.message,
            "duplicate option 'a' with different values '1' and '2'",
        )
        self.cluster_property.set_properties.assert_not_called()

    def test_multiple_args(self):
        self._call_cmd(["a=1", "b=2", "c="])
        self.cluster_property.set_properties.assert_called_once_with(
            {"a": "1", "b": "2", "c": ""}, set()
        )

    def test_multiple_args_with_force(self):
        self._call_cmd(["a=1", "b=2", "c="], {"force": True})
        self.cluster_property.set_properties.assert_called_once_with(
            {"a": "1", "b": "2", "c": ""}, set([report_codes.FORCE])
        )

    def test_unsupported_modifier(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], {"all": True})
        self.assertEqual(
            cm.exception.message,
            "Specified option '--all' is not supported in this command",
        )
        self.cluster_property.assert_not_called()


class TestUnsetProperty(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster_property"])
        self.cluster_property = mock.Mock(spec_set=["set_properties"])
        self.lib.cluster_property = self.cluster_property

    def _call_cmd(self, argv, modifiers=None):
        cluster_property.unset_property(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.cluster_property.set_properties.assert_not_called()

    def test_args(self):
        self._call_cmd(["a=1", "=b", ""])
        self.cluster_property.set_properties.assert_called_once_with(
            {"a=1": "", "=b": "", "": ""}, set()
        )

    def test_args_with_force(self):
        self._call_cmd(["a=1", "=b", ""], {"force": True})
        self.cluster_property.set_properties.assert_called_once_with(
            {"a=1": "", "=b": "", "": ""}, set([report_codes.FORCE])
        )

    def test_unsupported_modifier(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], {"defaults": True})
        self.assertEqual(
            cm.exception.message,
            "Specified option '--defaults' is not supported in this command",
        )
        self.cluster_property.assert_not_called()

    def test_duplicate_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["a", "a", "b", "b", "c"])
        self.assertEqual(
            cm.exception.message,
            "duplicate arguments: 'a', 'b'",
        )
        self.cluster_property.assert_not_called()


class TestListPropertyDeprecated(TestCase):
    def setUp(self):
        self.lib = mock.Mock()
        self.argv = []
        self.modifiers = {}

    @mock.patch("pcs.cli.cluster_property.command.deprecation_warning")
    @mock.patch("pcs.cli.cluster_property.command.config")
    def test_deprecated_command(self, mock_config, mock_warn):
        cluster_property.list_property_deprecated(
            self.lib, self.argv, self.modifiers
        )
        mock_config.assert_called_once_with(self.lib, self.argv, self.modifiers)
        mock_warn.assert_called_once_with(
            "This command is deprecated and will be removed. "
            "Please use 'pcs property config' instead."
        )


@mock.patch("pcs.cli.cluster_property.command.print")
class TestConfig(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster_property"])
        self.cluster_property = mock.MagicMock(
            spec_set=["get_properties", "get_properties_metadata"]
        )
        self.cluster_property.get_properties_metadata.return_value = (
            FIXTURE_PROPERTY_METADATA
        )
        self.cluster_property.get_properties.return_value = (
            FIXTURE_PROPERTIES_CONFIG
        )
        self.lib.cluster_property = self.cluster_property

    def _call_cmd(self, argv, modifiers=None):
        cluster_property.config(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def test_default_output_format(self, mock_print):
        self._call_cmd([])
        self.cluster_property.get_properties.assert_called_once()
        self.cluster_property.get_properties_metadata.assert_not_called()
        mock_print.assert_called_once_with(
            dedent(
                """\
                Cluster Properties: cib-bootstrap-options
                  property_name=value1"""
            )
        )

    def test_specified_properties(self, mock_print):
        self._call_cmd(["property_name", "property_advanced", "property"])
        self.cluster_property.get_properties.assert_called_once()
        self.cluster_property.get_properties_metadata.assert_called_once()
        mock_print.assert_called_once_with(
            dedent(
                """\
                Cluster Properties: cib-bootstrap-options
                  property_advanced=default (default)
                  property_name=value1"""
            )
        )

    def test_output_format_cmd(self, mock_print):
        self._call_cmd([], {"output-format": "cmd"})
        self.cluster_property.get_properties.assert_called_once()
        self.cluster_property.get_properties_metadata.assert_called_once()
        mock_print.assert_called_once_with(
            "pcs property set --force -- \\\n  property_name=value1"
        )

    def test_all_option(self, mock_print):
        self._call_cmd([], {"all": True})
        self.cluster_property.get_properties.assert_called_once()
        self.cluster_property.get_properties_metadata.assert_called_once()
        mock_print.assert_called_once_with(
            dedent(
                """\
                Cluster Properties: cib-bootstrap-options
                  property_advanced=default (default)
                  property_name=value1"""
            )
        )

    @mock.patch("pcs.cli.cluster_property.command.deprecation_warning")
    def test_defaults_option(self, mock_warn, mock_print):
        self._call_cmd([], {"defaults": True})
        self.cluster_property.get_properties.assert_not_called()
        self.cluster_property.get_properties_metadata.assert_called_once()
        mock_print.assert_called_once_with(
            dedent(
                """\
                property_advanced=default
                property_name=default"""
            )
        )
        mock_warn.assert_called_once_with(
            "Option --defaults is deprecated and will be "
            "removed. Please use command 'pcs property defaults' instead."
        )

    def test_output_format_json(self, mock_print):
        self._call_cmd([], {"output-format": "json"})
        self.cluster_property.get_properties.assert_called_once()
        self.cluster_property.get_properties_metadata.assert_not_called()
        mock_print.assert_called_once_with(
            json.dumps(dto.to_dict(FIXTURE_PROPERTIES_CONFIG))
        )

    def test_unsupported_option(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], {"force": True})
        self.assertEqual(
            cm.exception.message,
            ("Specified option '--force' is not supported in this command"),
        )
        self.cluster_property.get_properties.assert_not_called()
        self.cluster_property.get_properties_metadata.assert_not_called()
        mock_print.assert_not_called()

    def test_args_and_option(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["arg1"], {"all": True})
        self.assertEqual(
            cm.exception.message,
            (
                "cannot specify properties when using '--all', '--defaults', "
                "'--output-format'"
            ),
        )
        self.cluster_property.get_properties.assert_not_called()
        self.cluster_property.get_properties_metadata.assert_not_called()
        mock_print.assert_not_called()

    def test_unsupported_output_format(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], {"output-format": "unsupported"})
        self.assertEqual(
            cm.exception.message,
            (
                "Unknown value 'unsupported' for '--output-format' option. "
                "Supported values are: 'cmd', 'json', 'text'"
            ),
        )
        self.cluster_property.get_properties.assert_not_called()
        self.cluster_property.get_properties_metadata.assert_not_called()
        mock_print.assert_not_called()

    def test_all_modifiers(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(
                [], {"all": True, "defaults": True, "output-format": "text"}
            )
        self.assertEqual(
            cm.exception.message,
            (
                "Only one of '--all', '--defaults', '--output-format' can be "
                "used"
            ),
        )
        self.cluster_property.get_properties.assert_not_called()
        self.cluster_property.get_properties_metadata.assert_not_called()
        mock_print.assert_not_called()

    def test_all_and_defaults(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], {"all": True, "defaults": True})
        self.assertEqual(
            cm.exception.message,
            ("Only one of '--all', '--defaults' can be used"),
        )
        self.cluster_property.get_properties.assert_not_called()
        self.cluster_property.get_properties_metadata.assert_not_called()
        mock_print.assert_not_called()

    def test_all_and_output_format(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], {"all": True, "output-format": True})
        self.assertEqual(
            cm.exception.message,
            ("Only one of '--all', '--output-format' can be used"),
        )
        self.cluster_property.get_properties.assert_not_called()
        self.cluster_property.get_properties_metadata.assert_not_called()
        mock_print.assert_not_called()

    def test_defaults_and_output_format(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], {"defaults": True, "output-format": True})
        self.assertEqual(
            cm.exception.message,
            ("Only one of '--defaults', '--output-format' can be used"),
        )
        self.cluster_property.get_properties.assert_not_called()
        self.cluster_property.get_properties_metadata.assert_not_called()
        mock_print.assert_not_called()


@mock.patch("pcs.cli.cluster_property.command.print")
class TestDefaults(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster_property"])
        self.cluster_property = mock.MagicMock(
            spec_set=["get_properties_metadata"]
        )
        self.cluster_property.get_properties_metadata.return_value = (
            FIXTURE_PROPERTY_METADATA
        )
        self.lib.cluster_property = self.cluster_property

    def _call_cmd(self, argv, modifiers=None):
        cluster_property.defaults(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def test_no_args(self, mock_print):
        self._call_cmd([])
        self.cluster_property.get_properties_metadata.assert_called_once()
        mock_print.assert_called_once_with("property_name=default")

    def test_full_option(self, mock_print):
        self._call_cmd([], {"full": True})
        self.cluster_property.get_properties_metadata.assert_called_once()
        mock_print.assert_called_once_with(
            "property_advanced=default\nproperty_name=default"
        )

    def test_filter_properties(self, mock_print):
        self._call_cmd(["property_name", "property_advanced"])
        self.cluster_property.get_properties_metadata.assert_called_once()
        mock_print.assert_called_once_with(
            "property_advanced=default\nproperty_name=default"
        )

    def test_properties_without_defaults(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["arg1", "arg2"])
        self.assertEqual(
            cm.exception.message,
            "No default value for properties: 'arg1', 'arg2'",
        )
        self.cluster_property.get_properties_metadata.assert_called_once()
        mock_print.assert_not_called()

    def test_unsupported_option(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], modifiers={"force": True, "full": True})
        self.assertEqual(
            cm.exception.message,
            "Specified option '--force' is not supported in this command",
        )
        self.cluster_property.get_properties_metadata.assert_not_called()
        mock_print.assert_not_called()

    def test_args_and_full(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["arg1", "arg2"], modifiers={"full": True})
        self.assertEqual(
            cm.exception.message,
            "cannot specify properties when using '--full'",
        )
        self.cluster_property.get_properties_metadata.assert_not_called()
        mock_print.assert_not_called()


@mock.patch("pcs.cli.cluster_property.command.print")
class TestDescribe(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster_property"])
        self.cluster_property = mock.MagicMock(
            spec_set=["get_properties_metadata"]
        )
        self.cluster_property.get_properties_metadata.return_value = (
            FIXTURE_PROPERTY_METADATA
        )
        self.lib.cluster_property = self.cluster_property
        self.text_output = dedent(
            """\
            property_name
              Description: No description available
              Type: string
              Default: default"""
        )
        self.text_output_advanced = dedent(
            """\
            property_advanced (advanced use only)
              Description: No description available
              Type: string
              Default: default
            property_name
              Description: No description available
              Type: string
              Default: default"""
        )

    def _call_cmd(self, argv, modifiers=None):
        cluster_property.describe(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def test_no_args(self, mock_print):
        self._call_cmd([])
        self.cluster_property.get_properties_metadata.assert_called_once()
        mock_print.assert_called_once_with(self.text_output)

    def test_full_option(self, mock_print):
        self._call_cmd([], {"full": True})
        self.cluster_property.get_properties_metadata.assert_called_once()
        mock_print.assert_called_once_with(self.text_output_advanced)

    def test_filter_properties(self, mock_print):
        self._call_cmd(["property_name", "property_advanced"])
        self.cluster_property.get_properties_metadata.assert_called_once()
        mock_print.assert_called_once_with(self.text_output_advanced)

    def test_properties_without_metadata(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["arg1", "arg2"])
        self.assertEqual(
            cm.exception.message,
            "No description for properties: 'arg1', 'arg2'",
        )
        self.cluster_property.get_properties_metadata.assert_called_once()
        mock_print.assert_not_called()

    def test_supported_output_format_json(self, mock_print):
        self._call_cmd([], modifiers={"output-format": "json"})
        self.cluster_property.get_properties_metadata.assert_called_once_with()
        mock_print.assert_called_once_with(
            json.dumps(dto.to_dict(FIXTURE_PROPERTY_METADATA))
        )

    def test_unsupported_output_format(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], modifiers={"output-format": "cmd"})
        self.assertEqual(
            cm.exception.message,
            "Unknown value 'cmd' for '--output-format' option. Supported values"
            " are: 'json', 'text'",
        )
        self.cluster_property.get_properties_metadata.assert_not_called()
        mock_print.assert_not_called()

    def test_unsupported_option(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], modifiers={"force": True, "full": True})
        self.assertEqual(
            cm.exception.message,
            "Specified option '--force' is not supported in this command",
        )
        self.cluster_property.get_properties_metadata.assert_not_called()
        mock_print.assert_not_called()

    def test_args_and_full(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["arg1", "arg2"], modifiers={"full": True})
        self.assertEqual(
            cm.exception.message,
            "cannot specify properties when using '--full'",
        )
        self.cluster_property.get_properties_metadata.assert_not_called()
        mock_print.assert_not_called()

    def test_output_format_json_and_full(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(
                [], modifiers={"output-format": "json", "full": True}
            )
        self.assertEqual(
            cm.exception.message,
            "property filtering is not supported with --output-format=json",
        )
        self.cluster_property.get_properties_metadata.assert_not_called()
        mock_print.assert_not_called()


@mock.patch("pcs.cli.cluster_property.command.print")
class TestPrintClusterPropertiesDefinitionLegacy(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster_property"])
        self.cluster_property = mock.MagicMock(
            spec_set=["get_cluster_properties_definition_legacy"]
        )
        self.cluster_property.get_cluster_properties_definition_legacy.return_value = {}
        self.lib.cluster_property = self.cluster_property

    def _call_cmd(self, argv, modifiers=None):
        cluster_property.print_cluster_properties_definition_legacy(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def test_args(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["args"])
        self.assertIsNone(cm.exception.message)
        self.cluster_property.get_cluster_properties_definition_legacy.assert_not_called()
        mock_print.assert_not_called()

    def test_options(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], modifiers={"force": True, "full": True})
        self.assertEqual(
            cm.exception.message,
            (
                "Specified options '--force', '--full' are not supported in "
                "this command"
            ),
        )
        self.cluster_property.get_cluster_properties_definition_legacy.assert_not_called()
        mock_print.assert_not_called()

    def test_no_args(self, mock_print):
        self._call_cmd([])
        self.cluster_property.get_cluster_properties_definition_legacy.assert_called_once()
        mock_print.assert_called_once_with("{}")
