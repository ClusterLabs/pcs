from unittest import (
    TestCase,
    mock,
)

from pcs.common import reports
from pcs.lib.commands import cluster_property

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

ALLOWED_PROPERTIES = [
    "batch-limit",
    "cluster-delay",
    "cluster-ipc-limit",
    "cluster-recheck-interval",
    "concurrent-fencing",
    "dc-deadtime",
    "election-timeout",
    "enable-acl",
    "enable-startup-probes",
    "fence-reaction",
    "join-finalization-timeout",
    "join-integration-timeout",
    "load-threshold",
    "maintenance-mode",
    "migration-limit",
    "no-quorum-policy",
    "node-action-limit",
    "node-health-base",
    "node-health-green",
    "node-health-red",
    "node-health-strategy",
    "node-health-yellow",
    "pe-error-series-max",
    "pe-input-series-max",
    "pe-warn-series-max",
    "placement-strategy",
    "priority-fencing-delay",
    "remove-after-stop",
    "shutdown-escalation",
    "shutdown-lock",
    "shutdown-lock-limit",
    "start-failure-is-fatal",
    "startup-fencing",
    "stonith-action",
    "stonith-enabled",
    "stonith-max-attempts",
    "stonith-timeout",
    "stonith-watchdog-timeout",
    "stop-all-resources",
    "stop-orphan-actions",
    "stop-orphan-resources",
    "symmetric-cluster",
    "transition-delay",
]


def fixture_property_set(set_id, nvpairs):
    return (
        f'<cluster_property_set id="{set_id}">'
        + "".join(
            [
                f'<nvpair id="{set_id}-{name}" name="{name}" value="{value}"/>'
                for name, value in nvpairs.items()
            ]
        )
        + "</cluster_property_set>"
    )


def fixture_crm_config_properties(set_list):
    return (
        "<crm_config>"
        + "".join(
            [
                fixture_property_set(set_tuple[0], set_tuple[1])
                for set_tuple in set_list
            ]
        )
        + "</crm_config>"
    )


class LoadMetadataMixin:
    def load_fake_agent_metadata(self):
        for fake_agent in [
            "pacemaker-based",
            "pacemaker-controld",
            "pacemaker-schedulerd",
        ]:
            self.config.runner.pcmk.load_fake_agent_metadata(
                name=fake_agent, agent_name=fake_agent
            )


class NotLoadMetadataMixin:
    # pylint: disable=invalid-name
    def load_fake_agent_metadata(self):
        pass


class SetCommandMixin:
    def command(self, prop_dict, force_codes=None):
        cluster_property.set_property(
            self.env_assist.get_env(),
            prop_dict,
            [] if force_codes is None else force_codes,
        )


class StonithWatchdogTimeoutMixin:
    sbd_enabled = None

    def setUp(self):
        # pylint: disable=invalid-name
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"stonith-watchdog-timeout": "10"})]
            )
        )
        self.load_fake_agent_metadata()
        self.config.services.is_enabled("sbd", return_value=self.sbd_enabled)


class CommonSetUnsetMixin:
    def test_no_properties_specified(self):
        self.config.runner.cib.load()
        self.load_fake_agent_metadata()
        self.env_assist.assert_raise_library_error(lambda: self.command({}))
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_ITEMS_NOT_SPECIFIED,
                    container_type="property_set",
                    item_type="property",
                    container_id="cib-bootstrap-options",
                )
            ]
        )

    def test_no_sets_and_cib_bootstrap_options_id_taken(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive class="ocf" id="cib-bootstrap-options"
                        provider="pacemaker" type="Dummy"/>
                </resources>
            """
        )
        self.load_fake_agent_metadata()
        self.env_assist.assert_raise_library_error(
            lambda: self.command({"no-quorum-policy": "freeze"}),
            reports=[
                fixture.error(
                    reports.codes.CANNOT_CREATE_DEFAULT_CLUSTER_PROPERTY_SET
                )
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports([])


class TestSetStonithWatchdogTimeoutSBDIsDisabled(
    LoadMetadataMixin, StonithWatchdogTimeoutMixin, TestCase
):
    sbd_enabled = False

    def test_set_empty(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {})]
            )
        )
        cluster_property.set_property(
            self.env_assist.get_env(),
            {"stonith-watchdog-timeout": ""},
            [],
        )
        self.env_assist.assert_reports([])

    def test_set_zero(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"stonith-watchdog-timeout": "0"})]
            )
        )
        cluster_property.set_property(
            self.env_assist.get_env(),
            {"stonith-watchdog-timeout": "0"},
            [],
        )
        self.env_assist.assert_reports([])

    def test_set_not_zero_or_empty(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_property(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "20"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_SET,
                    reason="sbd_not_set_up",
                )
            ]
        )


class TestUnsetStonithWatchdogTimeoutSBDIsDisabled(
    NotLoadMetadataMixin, StonithWatchdogTimeoutMixin, TestCase
):
    sbd_enabled = False

    def test_unset(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {})]
            )
        )
        cluster_property.unset_property(
            self.env_assist.get_env(), ["stonith-watchdog-timeout"], []
        )
        self.env_assist.assert_reports([])


@mock.patch("pcs.lib.sbd._get_local_sbd_watchdog_timeout", lambda: 10)
@mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
class TestSetStonithWatchdogTimeoutSBDIsEnabledWatchdogOnly(
    LoadMetadataMixin, StonithWatchdogTimeoutMixin, TestCase
):
    sbd_enabled = True

    def test_set_empty(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_property(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": ""},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_UNSET,
                    force_code=reports.codes.FORCE,
                    reason="sbd_set_up_without_devices",
                )
            ]
        )

    def test_set_zero(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_property(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "0"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_UNSET,
                    force_code=reports.codes.FORCE,
                    reason="sbd_set_up_without_devices",
                )
            ]
        )

    def test_less_than_timeout(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_property(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "9"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_TOO_SMALL,
                    force_code=reports.codes.FORCE,
                    cluster_sbd_watchdog_timeout=10,
                    entered_watchdog_timeout="9",
                )
            ]
        )

    def test_equal_to_timeout(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_property(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "10"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_TOO_SMALL,
                    force_code=reports.codes.FORCE,
                    cluster_sbd_watchdog_timeout=10,
                    entered_watchdog_timeout="10",
                )
            ]
        )

    def test_too_small_forced(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"stonith-watchdog-timeout": "9"})]
            )
        )
        cluster_property.set_property(
            self.env_assist.get_env(),
            {"stonith-watchdog-timeout": "9"},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_TOO_SMALL,
                    cluster_sbd_watchdog_timeout=10,
                    entered_watchdog_timeout="9",
                )
            ]
        )

    def test_more_than_timeout(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"stonith-watchdog-timeout": "11"})]
            )
        )
        cluster_property.set_property(
            self.env_assist.get_env(),
            {"stonith-watchdog-timeout": "11"},
            [],
        )
        self.env_assist.assert_reports([])


@mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
class TestUnsetStonithWatchdogTimeoutSBDIsEnabledWatchdogOnly(
    NotLoadMetadataMixin, StonithWatchdogTimeoutMixin, TestCase
):
    sbd_enabled = True

    def test_unset(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.unset_property(
                self.env_assist.get_env(), ["stonith-watchdog-timeout"], []
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_UNSET,
                    force_code=reports.codes.FORCE,
                    reason="sbd_set_up_without_devices",
                )
            ]
        )

    def test_unset_forced(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {})]
            )
        )
        cluster_property.unset_property(
            self.env_assist.get_env(),
            ["stonith-watchdog-timeout"],
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_UNSET,
                    reason="sbd_set_up_without_devices",
                )
            ]
        )


@mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: ["dev1", "dev2"])
class TestSetStonithWatchdogTimeoutSBDIsEnabledSharedDevices(
    LoadMetadataMixin, StonithWatchdogTimeoutMixin, TestCase
):
    sbd_enabled = True

    def test_set_empty(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {})]
            )
        )
        cluster_property.set_property(
            self.env_assist.get_env(),
            {"stonith-watchdog-timeout": ""},
            [],
        )
        self.env_assist.assert_reports([])

    def test_set_to_zero(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"stonith-watchdog-timeout": "0"})]
            )
        )
        cluster_property.set_property(
            self.env_assist.get_env(),
            {"stonith-watchdog-timeout": "0"},
            [],
        )
        self.env_assist.assert_reports([])

    def test_set_not_zero_or_empty(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_property(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "20"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_SET,
                    force_code=reports.codes.FORCE,
                    reason="sbd_set_up_with_devices",
                )
            ]
        )

    def test_set_not_zero_or_empty_forced(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"stonith-watchdog-timeout": "20"})]
            )
        )
        cluster_property.set_property(
            self.env_assist.get_env(),
            {"stonith-watchdog-timeout": "20"},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_SET,
                    reason="sbd_set_up_with_devices",
                )
            ]
        )


@mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: ["dev1", "dev2"])
class TestUnsetStonithWatchdogTimeoutSBDIsEnabledSharedDevices(
    NotLoadMetadataMixin, StonithWatchdogTimeoutMixin, TestCase
):
    sbd_enabled = True

    def test_unset(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {})]
            )
        )
        cluster_property.unset_property(
            self.env_assist.get_env(), ["stonith-watchdog-timeout"], []
        )
        self.env_assist.assert_reports([])


class TestPropertySet(
    LoadMetadataMixin, SetCommandMixin, CommonSetUnsetMixin, TestCase
):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def _set_banned_properties(self, force):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    (
                        "cib-bootstrap-options",
                        {
                            "cluster-infrastructure": "corosync",
                            "cluster-name": "ClusterName",
                            "dc-version": "2.1.4-5.el9-dc6eb4362e",
                            "have-watchdog": "no",
                        },
                    )
                ]
            )
        )
        self.load_fake_agent_metadata()
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_property(
                self.env_assist.get_env(),
                {
                    "cluster-infrastructure": "cman",
                    "cluster-name": "HACluster",
                    "dc-version": "3.14",
                    "have-watchdog": "yes",
                    "no-quorum-policy": "freeze",
                },
                [reports.codes.FORCE] if force else [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=[
                        "cluster-infrastructure",
                        "cluster-name",
                        "dc-version",
                        "have-watchdog",
                    ],
                    allowed=ALLOWED_PROPERTIES,
                    option_type="cluster property",
                    allowed_patterns=[],
                )
            ]
        )

    def test_set_banned_properties(self):
        self._set_banned_properties(False)

    def test_set_banned_properties_forced(self):
        self._set_banned_properties(True)

    def test_set_allowed_properties(self):
        self.config.runner.cib.load()
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [
                    (
                        "cib-bootstrap-options",
                        {
                            "cluster-ipc-limit": "1000",
                            "no-quorum-policy": "freeze",
                            "stonith-max-attempts": "5",
                        },
                    )
                ]
            )
        )
        cluster_property.set_property(
            self.env_assist.get_env(),
            {
                "cluster-ipc-limit": "1000",
                "no-quorum-policy": "freeze",
                "stonith-max-attempts": "5",
            },
            [],
        )
        self.env_assist.assert_reports([])

    def test_set_unallowed_properties(self):
        self.config.runner.cib.load()
        self.load_fake_agent_metadata()
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_property(
                self.env_assist.get_env(),
                {
                    "a": "1",
                    "b": "2",
                    "no-quorum-policy": "freeze",
                },
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    force_code=reports.codes.FORCE,
                    option_names=["a", "b"],
                    allowed=ALLOWED_PROPERTIES,
                    option_type="cluster property",
                    allowed_patterns=[],
                )
            ]
        )

    def test_unallowed_properties_forced(self):
        self.config.runner.cib.load()
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [
                    (
                        "cib-bootstrap-options",
                        {"a": "1", "b": "2", "no-quorum-policy": "freeze"},
                    )
                ]
            ),
        )
        cluster_property.set_property(
            self.env_assist.get_env(),
            {"a": "1", "b": "2", "no-quorum-policy": "freeze"},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["a", "b"],
                    allowed=ALLOWED_PROPERTIES,
                    option_type="cluster property",
                    allowed_patterns=[],
                )
            ]
        )

    def test_set_allowed_properties_multiple_sets(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    ("first", {"a": "1", "b": "2"}),
                    ("second", {"x": "1", "y": "2"}),
                ]
            )
        )
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [
                    (
                        "first",
                        {
                            "a": "1",
                            "b": "2",
                            "cluster-ipc-limit": "1000",
                            "no-quorum-policy": "freeze",
                            "stonith-max-attempts": "5",
                        },
                    ),
                    ("second", {"x": "1", "y": "2"}),
                ]
            )
        )
        cluster_property.set_property(
            self.env_assist.get_env(),
            {
                "cluster-ipc-limit": "1000",
                "no-quorum-policy": "freeze",
                "stonith-max-attempts": "5",
            },
            [],
        )
        self.env_assist.assert_reports([])

    def test_set_unallowed_properties_multiple_sets(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    ("first", {"a": "1"}),
                    ("second", {"x": "1", "y": "2"}),
                ],
            )
        )
        self.load_fake_agent_metadata()
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_property(
                self.env_assist.get_env(),
                {"no-quorum-policy": "freeze", "b": "2", "c": "3"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    force_code=reports.codes.FORCE,
                    option_names=["b", "c"],
                    allowed=ALLOWED_PROPERTIES,
                    option_type="cluster property",
                    allowed_patterns=[],
                )
            ]
        )

    def test_unallowed_properties_multiple_sets_forced(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    ("first", {"a": "1"}),
                    ("second", {"x": "1", "y": "2"}),
                ],
            )
        )
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [
                    (
                        "first",
                        {
                            "a": "1",
                            "b": "2",
                            "c": "3",
                            "no-quorum-policy": "freeze",
                        },
                    ),
                    ("second", {"x": "1", "y": "2"}),
                ],
            ),
        )
        cluster_property.set_property(
            self.env_assist.get_env(),
            {"b": "2", "c": "3", "no-quorum-policy": "freeze"},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["b", "c"],
                    allowed=ALLOWED_PROPERTIES,
                    option_type="cluster property",
                    allowed_patterns=[],
                )
            ]
        )

    def test_set_and_unset_together(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties([("first", {"a": "1"})])
        )
        self.load_fake_agent_metadata()
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_property(
                self.env_assist.get_env(),
                {"a": "", "b": "2", "c": "", "no-quorum-policy": "freeze"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    force_code=reports.codes.FORCE,
                    option_names=["b"],
                    allowed=ALLOWED_PROPERTIES,
                    option_type="cluster property",
                    allowed_patterns=[],
                ),
                fixture.error(
                    reports.codes.OPTIONS_DO_NOT_EXIST,
                    force_code=reports.codes.FORCE,
                    option_names=["c"],
                    option_type="cluster property",
                ),
            ]
        )

    def test_set_and_unset_together_forced(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties([("first", {"a": "1"})])
        )
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [
                    (
                        "first",
                        {
                            "b": "2",
                            "no-quorum-policy": "freeze",
                        },
                    )
                ],
            ),
        )
        cluster_property.set_property(
            self.env_assist.get_env(),
            {"a": "", "b": "2", "c": "", "no-quorum-policy": "freeze"},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["b"],
                    allowed=ALLOWED_PROPERTIES,
                    option_type="cluster property",
                    allowed_patterns=[],
                ),
                fixture.warn(
                    reports.codes.OPTIONS_DO_NOT_EXIST,
                    option_names=["c"],
                    option_type="cluster property",
                ),
            ]
        )

    def _metadata_error(
        self, error_agent, stdout=None, reason=None, unsupported_version=False
    ):
        self.config.runner.cib.load()
        for agent in [
            "pacemaker-based",
            "pacemaker-controld",
            "pacemaker-schedulerd",
        ]:
            if agent == error_agent:
                kwargs = dict(
                    name=agent,
                    agent_name=agent,
                    stdout="" if stdout is None else stdout,
                    stderr="error",
                    returncode=2,
                )
            else:
                kwargs = dict(name=agent, agent_name=agent)
            self.config.runner.pcmk.load_fake_agent_metadata(**kwargs)
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_property(
                self.env_assist.get_env(), {}, []
            )
        )
        if unsupported_version:
            report = fixture.error(
                reports.codes.AGENT_IMPLEMENTS_UNSUPPORTED_OCF_VERSION,
                agent=f"__pcmk_internal:{error_agent}",
                ocf_version="1.2",
                supported_versions=["1.0", "1.1"],
            )
        else:
            report = fixture.error(
                reports.codes.UNABLE_TO_GET_AGENT_METADATA,
                agent=error_agent,
                reason="error" if reason is None else reason,
            )
        self.env_assist.assert_reports([report])

    def test_metadata_error_pacemaker_based(self):
        self._metadata_error("pacemaker-based")

    def test_metadata_error_pacemaker_controld(self):
        self._metadata_error("pacemaker-controld")

    def test_metadata_error_pacemaker_schedulerd(self):
        self._metadata_error("pacemaker-schedulerd")

    def test_metadata_error_xml_syntax_error(self):
        self._metadata_error(
            "pacemaker-schedulerd",
            stdout="not an xml",
            reason=(
                "Start tag expected, '<' not found, line 1, column 1 (<string>,"
                " line 1)"
            ),
        )

    def test_metadata_error_invalid_schema(self):
        self._metadata_error(
            "pacemaker-based",
            stdout="<xml/>",
            reason="Expecting element resource-agent, got xml, line 1",
        )

    def test_metadata_error_invalid_version(self):
        self._metadata_error(
            "pacemaker-controld",
            stdout="""
                <resource-agent name="pacemaker-based">
                    <version>1.2</version>
                </resource-agent>
            """,
            unsupported_version=True,
        )


class RemovePropertyMixin:
    def test_remove_properties(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [("set-id", {"a": "1", "b": "2"})]
            )
        )
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties([("set-id", {})])
        )
        self.command({"a": "", "b": ""})
        self.env_assist.assert_reports([])

    def test_remove_not_configured_properties(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [("set-id", {"a": "1", "b": "2"})]
            )
        )
        self.load_fake_agent_metadata()
        self.env_assist.assert_raise_library_error(
            lambda: self.command({"a": "", "x": "", "y": ""})
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.OPTIONS_DO_NOT_EXIST,
                    force_code=reports.codes.FORCE,
                    option_names=["x", "y"],
                    option_type="cluster property",
                )
            ]
        )

    def test_remove_not_configured_properties_forced(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [("set-id", {"a": "1", "b": "2"})]
            )
        )
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties([("set-id", {"b": "2"})])
        )
        self.command({"a": "", "x": "", "y": ""}, [reports.codes.FORCE])
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.OPTIONS_DO_NOT_EXIST,
                    option_names=["x", "y"],
                    option_type="cluster property",
                )
            ]
        )

    def test_remove_properties_multiple_sets(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    ("first", {"a": "1", "b": "2"}),
                    ("second", {"a": "1", "b": "2"}),
                ]
            )
        )
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [
                    ("first", {"a": "1"}),
                    ("second", {"a": "1", "b": "2"}),
                ]
            )
        )
        self.command({"b": ""})
        self.env_assist.assert_reports([])

    def test_remove_not_configured_properties_multiple_sets(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    ("first", {"a": "1", "b": "2"}),
                    ("second", {"x": "1", "y": "2"}),
                ]
            )
        )
        self.load_fake_agent_metadata()
        self.env_assist.assert_raise_library_error(
            lambda: self.command({"a": "", "x": "", "y": ""})
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.OPTIONS_DO_NOT_EXIST,
                    force_code=reports.codes.FORCE,
                    option_names=["x", "y"],
                    option_type="cluster property",
                )
            ]
        )

    def test_remove_not_configured_properties_multiple_sets_forced(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    ("first", {"a": "1", "b": "2"}),
                    ("second", {"x": "1", "y": "2"}),
                ]
            )
        )
        self.load_fake_agent_metadata()
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [
                    ("first", {"b": "2"}),
                    ("second", {"x": "1", "y": "2"}),
                ]
            )
        )
        self.command({"a": "", "x": "", "y": ""}, [reports.codes.FORCE])
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.OPTIONS_DO_NOT_EXIST,
                    option_names=["x", "y"],
                    option_type="cluster property",
                )
            ]
        )

    def _remove_banned_properties(self, force):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    (
                        "cib-bootstrap-options",
                        {
                            "cluster-infrastructure": "corosync",
                            "cluster-name": "ClusterName",
                            "dc-version": "2.1.4-5.el9-dc6eb4362e",
                            "have-watchdog": "no",
                            "no-quorum-policy": "freeze",
                        },
                    )
                ]
            )
        )
        self.load_fake_agent_metadata()
        self.env_assist.assert_raise_library_error(
            lambda: self.command(
                {
                    "cluster-infrastructure": "",
                    "cluster-name": "",
                    "dc-version": "",
                    "have-watchdog": "",
                    "no-quorum-policy": "",
                },
                [reports.codes.FORCE] if force else [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.CANNOT_DO_ACTION_WITH_FORBIDDEN_OPTIONS,
                    action="remove",
                    specified_options=[
                        "cluster-infrastructure",
                        "cluster-name",
                        "dc-version",
                        "have-watchdog",
                    ],
                    forbidden_options=[
                        "cluster-infrastructure",
                        "cluster-name",
                        "dc-version",
                        "have-watchdog",
                    ],
                    option_type="cluster property",
                )
            ]
        )

    def test_remove_banned_properties(self):
        self._remove_banned_properties(False)

    def test_remove_banned_properties_forced(self):
        self._remove_banned_properties(True)


class TestPropertySetEmptyValues(
    LoadMetadataMixin, SetCommandMixin, RemovePropertyMixin, TestCase
):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)


class TestPropertyUnset(
    NotLoadMetadataMixin, CommonSetUnsetMixin, RemovePropertyMixin, TestCase
):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def command(self, prop_dict, force_codes=None):
        cluster_property.unset_property(
            self.env_assist.get_env(),
            prop_dict.keys(),
            [] if force_codes is None else force_codes,
        )

    def test_duplicate_properties(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [("set_id", {"enable-acl": "true"})]
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.unset_property(
                self.env_assist.get_env(),
                ["enable-acl", "enable-acl", "not-there", "not-there"],
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_ITEMS_DUPLICATION,
                    force_code=reports.codes.FORCE,
                    container_type="property_set",
                    item_type="property",
                    container_id="set_id",
                    duplicate_items_list=["enable-acl", "not-there"],
                ),
                fixture.error(
                    reports.codes.OPTIONS_DO_NOT_EXIST,
                    force_code=reports.codes.FORCE,
                    option_names=["not-there"],
                    option_type="cluster property",
                ),
            ]
        )

    def test_duplicate_properties_forced(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [("set-id", {"enable-acl": "true"})]
            )
        )
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties([("set-id", {})])
        )
        cluster_property.unset_property(
            self.env_assist.get_env(),
            ["enable-acl", "enable-acl", "not-there", "not-there"],
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.ADD_REMOVE_ITEMS_DUPLICATION,
                    container_type="property_set",
                    item_type="property",
                    container_id="set-id",
                    duplicate_items_list=["enable-acl", "not-there"],
                ),
                fixture.warn(
                    reports.codes.OPTIONS_DO_NOT_EXIST,
                    option_names=["not-there"],
                    option_type="cluster property",
                ),
            ]
        )
