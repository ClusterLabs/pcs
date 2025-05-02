from unittest import TestCase

from pcs.lib import resource_agent as ra


class ResourceAgentName(TestCase):
    def test_full_name_3_parts(self):
        self.assertEqual(
            ra.ResourceAgentName("standard", "provider", "type").full_name,
            "standard:provider:type",
        )

    def test_full_name_2_parts_none(self):
        self.assertEqual(
            ra.ResourceAgentName("standard", None, "type").full_name,
            "standard:type",
        )

    def test_full_name_2_parts_empty(self):
        self.assertEqual(
            ra.ResourceAgentName("standard", "", "type").full_name,
            "standard:type",
        )

    def test_is_ocf_yes(self):
        self.assertTrue(
            ra.ResourceAgentName("ocf", "pacemaker", "Dummy").is_ocf
        )

    def test_is_ocf_no(self):
        self.assertFalse(
            ra.ResourceAgentName("systemd", None, "chronyd").is_ocf
        )

    def test_is_stonith_yes(self):
        self.assertTrue(
            ra.ResourceAgentName("stonith", "pacemaker", "Dummy").is_stonith
        )

    def test_is_stonith_no(self):
        self.assertFalse(
            ra.ResourceAgentName("lsb", None, "fence_xvm").is_stonith
        )

    def test_is_fake_pcmk_agent_yes(self):
        self.assertTrue(
            ra.ResourceAgentName(
                ra.const.FAKE_AGENT_STANDARD, None, "Dummy"
            ).is_pcmk_fake_agent
        )

    def test_is_fake_pcmk_agent_no(self):
        self.assertFalse(
            ra.ResourceAgentName("pacemaker", None, "fenced").is_pcmk_fake_agent
        )


def _fixture_metadata(name, actions):
    return ra.ResourceAgentMetadata(
        name,
        agent_exists=True,
        ocf_version=ra.const.OCF_1_0,
        shortdesc=None,
        longdesc=None,
        parameters=[],
        actions=actions,
    )


def _fixture_action(name, automatic, on_target):
    return ra.ResourceAgentAction(
        name=name,
        timeout=None,
        interval=None,
        role=None,
        start_delay=None,
        depth=None,
        automatic=automatic,
        on_target=on_target,
    )


class ProvidesUnfencing(TestCase):
    def test_not_stonith(self):
        self.assertFalse(
            _fixture_metadata(
                ra.ResourceAgentName("ocf", "pacemaker", "Dummy"),
                [_fixture_action("on", True, True)],
            ).provides_unfencing
        )

    def test_not_automatic(self):
        self.assertFalse(
            _fixture_metadata(
                ra.ResourceAgentName("stonith", None, "fence_xvm"),
                [_fixture_action("on", False, True)],
            ).provides_unfencing
        )

    def test_not_on_target(self):
        self.assertFalse(
            _fixture_metadata(
                ra.ResourceAgentName("stonith", None, "fence_xvm"),
                [_fixture_action("on", True, False)],
            ).provides_unfencing
        )

    def test_not_action_on(self):
        self.assertFalse(
            _fixture_metadata(
                ra.ResourceAgentName("stonith", None, "fence_xvm"),
                [_fixture_action("off", True, True)],
            ).provides_unfencing
        )

    def test_true(self):
        self.assertTrue(
            _fixture_metadata(
                ra.ResourceAgentName("stonith", None, "fence_xvm"),
                [
                    _fixture_action("on", False, True),
                    _fixture_action("on", True, False),
                    _fixture_action("off", True, True),
                    _fixture_action("on", True, True),
                ],
            ).provides_unfencing
        )


class ProvidesPromotability(TestCase):
    def test_both_actions_missing(self):
        self.assertFalse(
            _fixture_metadata(
                ra.ResourceAgentName("systemd", None, "pacemaker"),
                [_fixture_action("on", False, False)],
            ).provides_promotability
        )

    def test_only_promote_action(self):
        self.assertFalse(
            _fixture_metadata(
                ra.ResourceAgentName("ocf", "heartbeat", "Dummy"),
                [
                    _fixture_action("off", False, False),
                    _fixture_action("promote", False, False),
                ],
            ).provides_promotability
        )

    def test_only_demote_action(self):
        self.assertFalse(
            _fixture_metadata(
                ra.ResourceAgentName("ocf", "heartbeat", "Dummy"),
                [
                    _fixture_action("off", False, False),
                    _fixture_action("monitor", False, False),
                    _fixture_action("demote", False, False),
                ],
            ).provides_promotability
        )

    def test_both_actions(self):
        self.assertTrue(
            _fixture_metadata(
                ra.ResourceAgentName("ocf", "pacemaker", "Dummy"),
                [
                    _fixture_action("on", False, False),
                    _fixture_action("off", False, False),
                    _fixture_action("monitor", False, False),
                    _fixture_action("demote", False, False),
                    _fixture_action("promote", False, False),
                ],
            ).provides_promotability
        )


class UniqueParameterGroups(TestCase):
    @staticmethod
    def _fixture_metadata(parameters):
        return ra.ResourceAgentMetadata(
            ra.ResourceAgentName("ocf", "pacemaker", "Dummy"),
            agent_exists=True,
            ocf_version=ra.const.OCF_1_0,
            shortdesc=None,
            longdesc=None,
            parameters=parameters,
            actions=[],
        )

    @staticmethod
    def _fixture_parameter(name, unique_group):
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
            unique_group=unique_group,
            reloadable=False,
        )

    def test_no_groups(self):
        self.assertEqual(
            self._fixture_metadata(
                [
                    self._fixture_parameter("param_1", None),
                    self._fixture_parameter("param_2", None),
                    self._fixture_parameter("param_3", None),
                ]
            ).unique_parameter_groups,
            {},
        )

    def test_groups(self):
        self.assertEqual(
            self._fixture_metadata(
                [
                    self._fixture_parameter("param_1", None),
                    self._fixture_parameter("param_2", "group_A"),
                    self._fixture_parameter("param_3", None),
                    self._fixture_parameter("param_4", ""),
                    self._fixture_parameter("param_5", "group_B"),
                    self._fixture_parameter("param_6", "group_A"),
                ]
            ).unique_parameter_groups,
            {
                "group_A": {"param_2", "param_6"},
                "group_B": {"param_5"},
            },
        )
