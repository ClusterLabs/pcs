from unittest import (
    TestCase,
    mock,
)

from pcs.common import const
from pcs.lib import resource_agent as ra


class GetAdditionalTraceParameters(TestCase):
    def _assert_param_names(self, parameters, expected_names):
        self.assertEqual([param.name for param in parameters], expected_names)

    @staticmethod
    def _fixture_parameter(name):
        return ra.ResourceAgentParameter(
            name,
            shortdesc=None,
            longdesc=None,
            type="string",
            default=None,
            enum_values=None,
            required=False,
            advanced=False,
            deprecated=False,
            deprecated_by=[],
            deprecated_desc=None,
            unique_group=None,
            reloadable=False,
        )

    def test_no_input_params(self):
        self._assert_param_names(
            ra.pcs_transform.get_additional_trace_parameters([]),
            ["trace_ra", "trace_file"],
        )

    def test_return_both(self):
        self._assert_param_names(
            ra.pcs_transform.get_additional_trace_parameters(
                [
                    self._fixture_parameter("param1"),
                    self._fixture_parameter("trace"),
                ]
            ),
            ["trace_ra", "trace_file"],
        )

    def test_return_trace_file(self):
        self._assert_param_names(
            ra.pcs_transform.get_additional_trace_parameters(
                [
                    self._fixture_parameter("param1"),
                    self._fixture_parameter("trace_ra"),
                ]
            ),
            ["trace_file"],
        )

    def test_return_trace_ra(self):
        self._assert_param_names(
            ra.pcs_transform.get_additional_trace_parameters(
                [
                    self._fixture_parameter("param1"),
                    self._fixture_parameter("trace_file"),
                ]
            ),
            ["trace_ra"],
        )

    def test_return_none(self):
        self._assert_param_names(
            ra.pcs_transform.get_additional_trace_parameters(
                [
                    self._fixture_parameter("param1"),
                    self._fixture_parameter("trace_file"),
                    self._fixture_parameter("trace_ra"),
                ]
            ),
            [],
        )


ra_pkg = "pcs.lib.resource_agent.pcs_transform"


@mock.patch(f"{ra_pkg}._metadata_make_stonith_port_parameter_not_required")
@mock.patch(f"{ra_pkg}._metadata_make_stonith_action_parameter_deprecated")
@mock.patch(f"{ra_pkg}._metadata_remove_unwanted_stonith_parameters")
@mock.patch(f"{ra_pkg}._metadata_parameter_extract_advanced_from_desc")
@mock.patch(f"{ra_pkg}._metadata_parameter_join_short_long_desc")
@mock.patch(f"{ra_pkg}._metadata_parameter_deduplicate_desc")
@mock.patch(f"{ra_pkg}._metadata_parameter_remove_select_enum_values_from_desc")
@mock.patch(f"{ra_pkg}._metadata_parameter_extract_enum_values_from_desc")
@mock.patch(f"{ra_pkg}._metadata_action_translate_role")
class OcfUnifiedToPcs(TestCase):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    @staticmethod
    def _fixture_metadata(name):
        return ra.ResourceAgentMetadata(
            name,
            agent_exists=True,
            ocf_version=ra.const.OCF_1_0,
            shortdesc=None,
            longdesc=None,
            parameters=[],
            actions=[],
        )

    def test_resource(  # noqa: PLR0913
        self,
        mock_action_role,
        mock_parameter_enum,
        mock_parameter_select,
        mock_parameter_dedup_desc,
        mock_parameter_desc,
        mock_parameter_advanced,
        mock_stonith_parameters,
        mock_stonith_action,
        mock_stonith_port,
    ):
        mock_action_role.return_value = "from action role"
        mock_parameter_enum.return_value = "from parameter enum"
        mock_parameter_select.return_value = "from parameter select"
        mock_parameter_dedup_desc.return_value = "from parameter dedup desc"
        mock_parameter_desc.return_value = "from parameter desc"
        mock_parameter_advanced.return_value = "from parameter advanced"
        mock_stonith_parameters.return_value = "from stonith parameters"
        mock_stonith_action.return_value = "from stonith action"
        mock_stonith_port.return_value = "from stonith port"

        metadata = self._fixture_metadata(
            ra.ResourceAgentName("ocf", "pacemaker", "Dummy")
        )
        self.assertEqual(
            ra.pcs_transform.ocf_unified_to_pcs(metadata),
            "from action role",
        )

        mock_action_role.assert_called_once_with(metadata)
        mock_parameter_enum.assert_not_called()
        mock_parameter_select.assert_not_called()
        mock_parameter_dedup_desc.assert_not_called()
        mock_parameter_desc.assert_not_called()
        mock_parameter_advanced.assert_not_called()
        mock_stonith_parameters.assert_not_called()
        mock_stonith_action.assert_not_called()
        mock_stonith_port.assert_not_called()

    def test_stonith(  # noqa: PLR0913
        self,
        mock_action_role,
        mock_parameter_enum,
        mock_parameter_select,
        mock_parameter_dedup_desc,
        mock_parameter_desc,
        mock_parameter_advanced,
        mock_stonith_parameters,
        mock_stonith_action,
        mock_stonith_port,
    ):
        mock_action_role.return_value = "from action role"
        mock_parameter_enum.return_value = "from parameter enum"
        mock_parameter_select.return_value = "from parameter select"
        mock_parameter_dedup_desc.return_value = "from parameter dedup desc"
        mock_parameter_desc.return_value = "from parameter desc"
        mock_parameter_advanced.return_value = "from parameter advanced"
        mock_stonith_parameters.return_value = "from stonith parameters"
        mock_stonith_action.return_value = "from stonith action"
        mock_stonith_port.return_value = "from stonith port"

        metadata = self._fixture_metadata(
            ra.ResourceAgentName("stonith", None, "fence_xvm")
        )
        self.assertEqual(
            ra.pcs_transform.ocf_unified_to_pcs(metadata),
            "from stonith port",
        )

        mock_action_role.assert_called_once_with(metadata)
        mock_parameter_enum.assert_not_called()
        mock_parameter_select.assert_not_called()
        mock_parameter_dedup_desc.assert_not_called()
        mock_parameter_desc.assert_not_called()
        mock_parameter_advanced.assert_not_called()
        mock_stonith_parameters.assert_called_once_with("from action role")
        mock_stonith_action.assert_called_once_with("from stonith parameters")
        mock_stonith_port.assert_called_once_with("from stonith action")

    def test_pcmk_fake(  # noqa: PLR0913
        self,
        mock_action_role,
        mock_parameter_enum,
        mock_parameter_select,
        mock_parameter_dedup_desc,
        mock_parameter_desc,
        mock_parameter_advanced,
        mock_stonith_parameters,
        mock_stonith_action,
        mock_stonith_port,
    ):
        mock_action_role.return_value = "from action role"
        mock_parameter_enum.return_value = "from parameter enum"
        mock_parameter_select.return_value = "from parameter select"
        mock_parameter_dedup_desc.return_value = "from parameter dedup desc"
        mock_parameter_desc.return_value = "from parameter desc"
        mock_parameter_advanced.return_value = "from parameter advanced"
        mock_stonith_parameters.return_value = "from stonith parameters"
        mock_stonith_action.return_value = "from stonith action"
        mock_stonith_port.return_value = "from stonith port"

        metadata = self._fixture_metadata(
            ra.ResourceAgentName(
                ra.const.FAKE_AGENT_STANDARD, None, ra.const.PACEMAKER_FENCED
            )
        )
        self.assertEqual(
            ra.pcs_transform.ocf_unified_to_pcs(metadata),
            "from parameter desc",
        )

        mock_action_role.assert_called_once_with(metadata)
        mock_parameter_enum.assert_called_once_with("from action role")
        mock_parameter_select.assert_called_once_with("from parameter enum")
        mock_parameter_dedup_desc.assert_called_once_with(
            "from parameter select"
        )
        mock_parameter_advanced.assert_called_once_with(
            "from parameter dedup desc"
        )
        mock_parameter_desc.assert_called_once_with("from parameter advanced")
        mock_stonith_parameters.assert_not_called()
        mock_stonith_action.assert_not_called()
        mock_stonith_port.assert_not_called()


class MetadataActionTranslateRole(TestCase):
    @staticmethod
    def _fixture_metadata(actions):
        return ra.ResourceAgentMetadata(
            ra.ResourceAgentName("standard", "provider", "type"),
            agent_exists=True,
            ocf_version=ra.const.OCF_1_0,
            shortdesc=None,
            longdesc=None,
            parameters=[],
            actions=actions,
        )

    @staticmethod
    def _fixture_action(role, interval):
        return ra.ResourceAgentAction(
            name="monitor",
            timeout=None,
            interval=interval,
            role=role,
            start_delay=None,
            depth=None,
            automatic=False,
            on_target=False,
        )

    def test_no_actions(self):
        metadata_in = self._fixture_metadata([])
        metadata_out = self._fixture_metadata([])
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_action_translate_role(metadata_in),
            metadata_out,
        )

    def test_role_old_in_agent(self):
        metadata_in = self._fixture_metadata(
            [
                self._fixture_action(const.PCMK_ROLE_PROMOTED_LEGACY, "10"),
                self._fixture_action(const.PCMK_ROLE_UNPROMOTED_LEGACY, "11"),
            ]
        )
        metadata_out = self._fixture_metadata(
            [
                self._fixture_action(const.PCMK_ROLE_PROMOTED, "10"),
                self._fixture_action(const.PCMK_ROLE_UNPROMOTED, "11"),
            ]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_action_translate_role(metadata_in),
            metadata_out,
        )

    def test_role_new_in_agent(self):
        metadata_in = self._fixture_metadata(
            [
                self._fixture_action(const.PCMK_ROLE_PROMOTED, "10"),
                self._fixture_action(const.PCMK_ROLE_UNPROMOTED, "11"),
            ]
        )
        metadata_out = self._fixture_metadata(
            [
                self._fixture_action(const.PCMK_ROLE_PROMOTED, "10"),
                self._fixture_action(const.PCMK_ROLE_UNPROMOTED, "11"),
            ]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_action_translate_role(metadata_in),
            metadata_out,
        )


class MetadataParameterExtractAdvancedFromDesc(TestCase):
    advanced_str_list = ["Advanced use only:", "*** Advanced Use Only ***"]

    @staticmethod
    def _fixture_metadata(parameters):
        return ra.ResourceAgentMetadata(
            ra.ResourceAgentName("standard", "provider", "type"),
            agent_exists=True,
            ocf_version=ra.const.OCF_1_0,
            shortdesc=None,
            longdesc=None,
            parameters=parameters,
            actions=[],
        )

    @staticmethod
    def _fixture_parameter(shortdesc, longdesc, advanced):
        return ra.ResourceAgentParameter(
            name="test-parameter",
            shortdesc=shortdesc,
            longdesc=longdesc,
            type="string",
            default=None,
            enum_values=None,
            required=False,
            advanced=advanced,
            deprecated=False,
            deprecated_by=[],
            deprecated_desc=None,
            unique_group=None,
            reloadable=False,
        )

    def test_no_parameters(self):
        metadata_in = self._fixture_metadata([])
        metadata_out = self._fixture_metadata([])
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_extract_advanced_from_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_no_shortdesc(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter(None, None, False)]
        )
        metadata_out = self._fixture_metadata(
            [self._fixture_parameter(None, None, False)]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_extract_advanced_from_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_no_advanced_str(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter("some shortdesc", None, False)]
        )
        metadata_out = self._fixture_metadata(
            [self._fixture_parameter("some shortdesc", None, False)]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_extract_advanced_from_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_only_advanced_str_in_shortedsc(self):
        for advanced_str in self.advanced_str_list:
            with self.subTest(advanced_str=advanced_str):
                metadata_in = self._fixture_metadata(
                    [self._fixture_parameter(f"{advanced_str}", None, False)]
                )
                metadata_out = self._fixture_metadata(
                    [self._fixture_parameter(None, None, True)]
                )
                self.assertEqual(
                    # pylint: disable=protected-access
                    ra.pcs_transform._metadata_parameter_extract_advanced_from_desc(
                        metadata_in
                    ),
                    metadata_out,
                )

    def _assert_advanced_extracted(self, advanced_str, advanced_from_xml):
        metadata_in = self._fixture_metadata(
            [
                self._fixture_parameter(
                    f"{advanced_str}    some shortdesc", None, advanced_from_xml
                )
            ]
        )
        metadata_out = self._fixture_metadata(
            [self._fixture_parameter("some shortdesc", None, True)]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_extract_advanced_from_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_advanced_str_in_shortedsc(self):
        for advanced_str in self.advanced_str_list:
            with self.subTest(advanced_str=advanced_str):
                self._assert_advanced_extracted(advanced_str, False)

    def test_advanced_str_in_shortdesc_advanced_already_true(self):
        for advanced_str in self.advanced_str_list:
            with self.subTest(advanced_str=advanced_str):
                self._assert_advanced_extracted(advanced_str, True)

    def test_advanced_str_in_shortdesc_end(self):
        for advanced_str in self.advanced_str_list:
            with self.subTest(advanced_str=advanced_str):
                metadata_in = self._fixture_metadata(
                    [
                        self._fixture_parameter(
                            f"some shortdesc {advanced_str}", None, False
                        )
                    ]
                )
                metadata_out = self._fixture_metadata(
                    [
                        self._fixture_parameter(
                            f"some shortdesc {advanced_str}", None, False
                        )
                    ]
                )
                self.assertEqual(
                    # pylint: disable=protected-access
                    ra.pcs_transform._metadata_parameter_extract_advanced_from_desc(
                        metadata_in
                    ),
                    metadata_out,
                )

    def test_advanced_str_in_longdesc(self):
        for advanced_str in self.advanced_str_list:
            with self.subTest(advanced_str=advanced_str):
                metadata_in = self._fixture_metadata(
                    [
                        self._fixture_parameter(
                            None, f"{advanced_str}: some longdesc", False
                        )
                    ]
                )
                metadata_out = self._fixture_metadata(
                    [
                        self._fixture_parameter(
                            None, f"{advanced_str}: some longdesc", False
                        )
                    ]
                )
                self.assertEqual(
                    # pylint: disable=protected-access
                    ra.pcs_transform._metadata_parameter_extract_advanced_from_desc(
                        metadata_in
                    ),
                    metadata_out,
                )


class MetadataParameterExtractEnumValuesFromDesc(TestCase):
    longdesc = "longdesc  Allowed values: stop, freeze, ignore, demote, suicide"
    new_longdesc = "longdesc"
    enum_values = ["stop", "freeze", "ignore", "demote", "suicide"]

    @staticmethod
    def _fixture_metadata(parameters):
        return ra.ResourceAgentMetadata(
            ra.ResourceAgentName("standard", "provider", "type"),
            agent_exists=True,
            ocf_version=ra.const.OCF_1_0,
            shortdesc=None,
            longdesc=None,
            parameters=parameters,
            actions=[],
        )

    @staticmethod
    def _fixture_parameter(
        param_type, longdesc, default=None, enum_values=None
    ):
        return ra.ResourceAgentParameter(
            name="test-parameter",
            shortdesc=None,
            longdesc=longdesc,
            type=param_type,
            default=default,
            enum_values=enum_values,
            required=False,
            advanced=False,
            deprecated=False,
            deprecated_by=[],
            deprecated_desc=None,
            unique_group=None,
            reloadable=False,
        )

    def test_no_parameters(self):
        metadata_in = self._fixture_metadata([])
        metadata_out = self._fixture_metadata([])
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_extract_enum_values_from_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_not_enum_type(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter("select", self.longdesc)]
        )
        metadata_out = self._fixture_metadata(
            [self._fixture_parameter("select", self.longdesc)]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_extract_enum_values_from_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_enum_type_no_values_in_longdesc(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter("enum", self.new_longdesc)]
        )
        metadata_out = self._fixture_metadata(
            [
                self._fixture_parameter(
                    "select", self.new_longdesc, enum_values=[]
                )
            ]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_extract_enum_values_from_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_enum_type_no_values_in_longdesc_with_default(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter("enum", self.new_longdesc, default="stop")]
        )
        metadata_out = self._fixture_metadata(
            [
                self._fixture_parameter(
                    "select",
                    self.new_longdesc,
                    default="stop",
                    enum_values=["stop"],
                )
            ]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_extract_enum_values_from_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_enum_type_without_default(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter("enum", self.longdesc)]
        )
        metadata_out = self._fixture_metadata(
            [
                self._fixture_parameter(
                    "select", self.new_longdesc, enum_values=self.enum_values
                )
            ]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_extract_enum_values_from_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_enum_type_with_default_in_longdesc(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter("enum", self.longdesc, default="stop")]
        )
        metadata_out = self._fixture_metadata(
            [
                self._fixture_parameter(
                    "select",
                    self.new_longdesc,
                    default="stop",
                    enum_values=self.enum_values,
                )
            ]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_extract_enum_values_from_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_enum_type_with_default_not_in_longdesc(self):
        metadata_in = self._fixture_metadata(
            [
                self._fixture_parameter(
                    "enum", self.longdesc.replace(" stop,", ""), default="stop"
                )
            ]
        )
        enum_values = list(self.enum_values)
        enum_values.remove("stop")
        metadata_out = self._fixture_metadata(
            [
                self._fixture_parameter(
                    "select",
                    self.new_longdesc,
                    default="stop",
                    enum_values=enum_values + ["stop"],
                )
            ]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_extract_enum_values_from_desc(
                metadata_in
            ),
            metadata_out,
        )


class MetadataParameterRemoveSelectEnumValuesFromDesc(TestCase):
    longdesc = "longdesc  Allowed values: stop, freeze, ignore, demote, suicide"
    new_longdesc = "longdesc"

    @staticmethod
    def _fixture_metadata(parameters):
        return ra.ResourceAgentMetadata(
            ra.ResourceAgentName("standard", "provider", "type"),
            agent_exists=True,
            ocf_version=ra.const.OCF_1_0,
            shortdesc=None,
            longdesc=None,
            parameters=parameters,
            actions=[],
        )

    @staticmethod
    def _fixture_parameter(param_type, longdesc):
        return ra.ResourceAgentParameter(
            name="test-parameter",
            shortdesc=None,
            longdesc=longdesc,
            type=param_type,
            default=None,
            enum_values=None,
            required=False,
            advanced=False,
            deprecated=False,
            deprecated_by=[],
            deprecated_desc=None,
            unique_group=None,
            reloadable=False,
        )

    def test_no_parameters(self):
        metadata_in = self._fixture_metadata([])
        metadata_out = self._fixture_metadata([])
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_remove_select_enum_values_from_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_not_select_type(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter("enum", self.longdesc)]
        )
        metadata_out = self._fixture_metadata(
            [self._fixture_parameter("enum", self.longdesc)]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_remove_select_enum_values_from_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_select_type(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter("select", self.longdesc)]
        )
        metadata_out = self._fixture_metadata(
            [self._fixture_parameter("select", self.new_longdesc)]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_remove_select_enum_values_from_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_select_type_no_enum_values(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter("select", "other longdesc")]
        )
        metadata_out = self._fixture_metadata(
            [self._fixture_parameter("select", "other longdesc")]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_remove_select_enum_values_from_desc(
                metadata_in
            ),
            metadata_out,
        )


class MetadataParameterDeduplicateDesc(TestCase):
    @staticmethod
    def _fixture_metadata(parameters):
        return ra.ResourceAgentMetadata(
            ra.ResourceAgentName("standard", "provider", "type"),
            agent_exists=True,
            ocf_version=ra.const.OCF_1_0,
            shortdesc=None,
            longdesc=None,
            parameters=parameters,
            actions=[],
        )

    @staticmethod
    def _fixture_parameter(shortdesc, longdesc):
        return ra.ResourceAgentParameter(
            name="test-parameter",
            shortdesc=shortdesc,
            longdesc=longdesc,
            type="string",
            default=None,
            enum_values=None,
            required=False,
            advanced=False,
            deprecated=False,
            deprecated_by=[],
            deprecated_desc=None,
            unique_group=None,
            reloadable=False,
        )

    def test_no_parameters(self):
        metadata_in = self._fixture_metadata([])
        metadata_out = self._fixture_metadata([])
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_deduplicate_desc(metadata_in),
            metadata_out,
        )

    def test_same_desc(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter("same desc", "same desc")]
        )
        metadata_out = self._fixture_metadata(
            [self._fixture_parameter("same desc", None)]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_deduplicate_desc(metadata_in),
            metadata_out,
        )

    def test_different_desc(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter("shortdesc", "longdesc")]
        )
        metadata_out = self._fixture_metadata(
            [self._fixture_parameter("shortdesc", "longdesc")]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_deduplicate_desc(metadata_in),
            metadata_out,
        )


class MetadataParameterJoinShortLongDesc(TestCase):
    @staticmethod
    def _fixture_metadata(parameters):
        return ra.ResourceAgentMetadata(
            ra.ResourceAgentName("standard", "provider", "type"),
            agent_exists=True,
            ocf_version=ra.const.OCF_1_0,
            shortdesc=None,
            longdesc=None,
            parameters=parameters,
            actions=[],
        )

    @staticmethod
    def _fixture_parameter(shortdesc, longdesc):
        return ra.ResourceAgentParameter(
            name="test-parameter",
            shortdesc=shortdesc,
            longdesc=longdesc,
            type="string",
            default=None,
            enum_values=None,
            required=False,
            advanced=False,
            deprecated=False,
            deprecated_by=[],
            deprecated_desc=None,
            unique_group=None,
            reloadable=False,
        )

    def test_no_parameters(self):
        metadata_in = self._fixture_metadata([])
        metadata_out = self._fixture_metadata([])
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_join_short_long_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_no_shortdesc_no_longdesc(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter(None, None)]
        )
        metadata_out = self._fixture_metadata(
            [self._fixture_parameter(None, None)]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_join_short_long_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_shortdesc_only(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter("shortdesc", None)]
        )
        metadata_out = self._fixture_metadata(
            [self._fixture_parameter("shortdesc", None)]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_join_short_long_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_longdesc_only(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter(None, "longdesc")]
        )
        metadata_out = self._fixture_metadata(
            [self._fixture_parameter(None, "longdesc")]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_join_short_long_desc(
                metadata_in
            ),
            metadata_out,
        )

    def test_shortdesc_and_longdesc(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter("shortdesc", "longdesc")]
        )
        metadata_out = self._fixture_metadata(
            [self._fixture_parameter("shortdesc", "shortdesc.\nlongdesc")]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_parameter_join_short_long_desc(
                metadata_in
            ),
            metadata_out,
        )


class MetadataRemoveUnwantedStonithParameters(TestCase):
    @staticmethod
    def _fixture_metadata(parameters):
        return ra.ResourceAgentMetadata(
            ra.ResourceAgentName("standard", "provider", "type"),
            agent_exists=True,
            ocf_version=ra.const.OCF_1_0,
            shortdesc=None,
            longdesc=None,
            parameters=parameters,
            actions=[],
        )

    @staticmethod
    def _fixture_parameter(name):
        return ra.ResourceAgentParameter(
            name=name,
            shortdesc=None,
            longdesc=None,
            type="string",
            default=None,
            enum_values=None,
            required=False,
            advanced=False,
            deprecated=False,
            deprecated_by=[],
            deprecated_desc=None,
            unique_group=None,
            reloadable=False,
        )

    def test_no_parameters(self):
        metadata_in = self._fixture_metadata([])
        metadata_out = self._fixture_metadata([])
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_remove_unwanted_stonith_parameters(
                metadata_in
            ),
            metadata_out,
        )

    def test_success(self):
        metadata_in = self._fixture_metadata(
            [
                self._fixture_parameter("param1"),
                self._fixture_parameter("help"),
                self._fixture_parameter("param2"),
                self._fixture_parameter("version"),
            ]
        )
        metadata_out = self._fixture_metadata(
            [
                self._fixture_parameter("param1"),
                self._fixture_parameter("param2"),
            ]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_remove_unwanted_stonith_parameters(
                metadata_in
            ),
            metadata_out,
        )


class MetadataMakeStonithActionParameterDeprecated(TestCase):
    @staticmethod
    def _fixture_metadata(parameters):
        return ra.ResourceAgentMetadata(
            ra.ResourceAgentName("standard", "provider", "type"),
            agent_exists=True,
            ocf_version=ra.const.OCF_1_0,
            shortdesc=None,
            longdesc=None,
            parameters=parameters,
            actions=[],
        )

    @staticmethod
    def _fixture_parameter(name, required, advanced, deprecated, deprecated_by):
        return ra.ResourceAgentParameter(
            name,
            shortdesc=None,
            longdesc=None,
            type="string",
            default=None,
            enum_values=None,
            required=required,
            advanced=advanced,
            deprecated=deprecated,
            deprecated_by=deprecated_by,
            deprecated_desc=None,
            unique_group=None,
            reloadable=False,
        )

    def test_no_parameters(self):
        metadata_in = self._fixture_metadata([])
        metadata_out = self._fixture_metadata([])
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_make_stonith_action_parameter_deprecated(
                metadata_in
            ),
            metadata_out,
        )

    def test_no_action_parameter(self):
        metadata_in = self._fixture_metadata(
            [
                self._fixture_parameter(
                    "monitor",
                    required=True,
                    advanced=False,
                    deprecated=False,
                    deprecated_by=[],
                )
            ]
        )
        metadata_out = self._fixture_metadata(
            [
                self._fixture_parameter(
                    "monitor",
                    required=True,
                    advanced=False,
                    deprecated=False,
                    deprecated_by=[],
                )
            ]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_make_stonith_action_parameter_deprecated(
                metadata_in
            ),
            metadata_out,
        )

    def test_action_parameter(self):
        metadata_in = self._fixture_metadata(
            [
                self._fixture_parameter(
                    "action",
                    required=True,
                    advanced=False,
                    deprecated=False,
                    deprecated_by=["new-action"],
                )
            ]
        )
        metadata_out = self._fixture_metadata(
            [
                self._fixture_parameter(
                    "action",
                    required=False,
                    advanced=True,
                    deprecated=True,
                    deprecated_by=(
                        ra.const.STONITH_ACTION_REPLACED_BY + ["new-action"]
                    ),
                )
            ]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_make_stonith_action_parameter_deprecated(
                metadata_in
            ),
            metadata_out,
        )


class MetadataMakeStonithPortParameterNotRequired(TestCase):
    @staticmethod
    def _fixture_metadata(parameters):
        return ra.ResourceAgentMetadata(
            ra.ResourceAgentName("standard", "provider", "type"),
            agent_exists=True,
            ocf_version=ra.const.OCF_1_0,
            shortdesc=None,
            longdesc=None,
            parameters=parameters,
            actions=[],
        )

    @staticmethod
    def _fixture_parameter(name, required, deprecated_by):
        return ra.ResourceAgentParameter(
            name,
            shortdesc=None,
            longdesc=None,
            type="string",
            default=None,
            enum_values=None,
            required=required,
            advanced=False,
            deprecated=bool(deprecated_by),
            deprecated_by=deprecated_by,
            deprecated_desc=None,
            unique_group=None,
            reloadable=False,
        )

    def test_no_parameters(self):
        metadata_in = self._fixture_metadata([])
        metadata_out = self._fixture_metadata([])
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_make_stonith_port_parameter_not_required(
                metadata_in
            ),
            metadata_out,
        )

    def test_no_port_parameter(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter("param", True, [])]
        )
        metadata_out = self._fixture_metadata(
            [self._fixture_parameter("param", True, [])]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_make_stonith_port_parameter_not_required(
                metadata_in
            ),
            metadata_out,
        )

    def test_modify_port_parameter(self):
        metadata_in = self._fixture_metadata(
            [self._fixture_parameter("port", True, [])]
        )
        metadata_out = self._fixture_metadata(
            [self._fixture_parameter("port", False, [])]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_make_stonith_port_parameter_not_required(
                metadata_in
            ),
            metadata_out,
        )

    def test_modify_port_and_deprecations(self):
        metadata_in = self._fixture_metadata(
            [
                self._fixture_parameter("old-port", True, ["port"]),
                self._fixture_parameter("port", True, ["new-port"]),
                self._fixture_parameter(
                    "new-port", True, ["new-port2a", "new-port2b"]
                ),
                self._fixture_parameter("new-port2a", True, []),
                self._fixture_parameter("new-port2b", True, []),
            ]
        )
        metadata_out = self._fixture_metadata(
            [
                self._fixture_parameter("old-port", True, ["port"]),
                self._fixture_parameter("port", False, ["new-port"]),
                self._fixture_parameter(
                    "new-port", False, ["new-port2a", "new-port2b"]
                ),
                self._fixture_parameter("new-port2a", False, []),
                self._fixture_parameter("new-port2b", False, []),
            ]
        )
        self.assertEqual(
            # pylint: disable=protected-access
            ra.pcs_transform._metadata_make_stonith_port_parameter_not_required(
                metadata_in
            ),
            metadata_out,
        )
