from unittest import TestCase

from pcs import settings
from pcs.common import reports
from pcs.common.auth import HostAuthData, HostWithTokenAuthData
from pcs.common.file_type_codes import COROSYNC_CONF, PCS_KNOWN_HOSTS
from pcs.common.host import Destination, PcsKnownHost
from pcs.lib.commands import auth
from pcs.lib.host.config.types import KnownHosts

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.fixture_pcs_cfgsync import (
    fixture_expected_save_sync_reports,
    fixture_known_hosts_file_content,
    fixture_save_sync_new_known_hosts_conflict,
    fixture_save_sync_new_known_hosts_error,
    fixture_save_sync_new_known_hosts_success,
)

_FIXTURE_KNOWN_HOSTS = {
    "node1": PcsKnownHost("node1", "aaa", [Destination("node1", 2224)]),
    "node2": PcsKnownHost("node2", "bbb", [Destination("node2", 2224)]),
}


class ReadKnownHostsFile(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_file_exists(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS, settings.pcsd_known_hosts_location
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )

        env = self.env_assist.get_env()
        facade = auth._read_known_hosts_file(env.report_processor)
        self.assertEqual(
            facade.config,
            KnownHosts(
                format_version=1,
                data_version=1,
                known_hosts=_FIXTURE_KNOWN_HOSTS,
            ),
        )

    def test_file_does_not_exist(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS, settings.pcsd_known_hosts_location, exists=False
        )

        env = self.env_assist.get_env()
        facade = auth._read_known_hosts_file(env.report_processor)
        self.assertEqual(
            facade.config,
            KnownHosts(format_version=1, data_version=0, known_hosts={}),
        )

    def test_error_reading_file(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS, settings.pcsd_known_hosts_location
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            exception_msg="some error",
        )

        env = self.env_assist.get_env()
        self.env_assist.assert_raise_library_error(
            lambda: auth._read_known_hosts_file(env.report_processor)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    operation="read",
                    reason="some error",
                    file_path=settings.pcsd_known_hosts_location,
                )
            ],
        )

    def test_error_reading_file_invalid_file_structure(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS, settings.pcsd_known_hosts_location
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS, settings.pcsd_known_hosts_location, content="A"
        )

        env = self.env_assist.get_env()
        self.env_assist.assert_raise_library_error(
            lambda: auth._read_known_hosts_file(env.report_processor)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.PARSE_ERROR_JSON_FILE,
                    file_type_code=PCS_KNOWN_HOSTS,
                    line_number=1,
                    column_number=1,
                    position=0,
                    reason="Expecting value",
                    full_msg="Expecting value: line 1 column 1 (char 0)",
                    file_path=settings.pcsd_known_hosts_location,
                )
            ],
        )


class AuthHostsTokenNoSync(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_adds_new(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS, settings.pcsd_known_hosts_location
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            fixture_known_hosts_file_content(
                2,
                {
                    **_FIXTURE_KNOWN_HOSTS,
                    "node3": PcsKnownHost(
                        "node3", "TOKEN", [Destination("node3", 2224)]
                    ),
                    "node4": PcsKnownHost(
                        "node4", "TOKEN", [Destination("node4", 2224)]
                    ),
                },
            ).encode("utf-8"),
            can_overwrite=True,
        )

        auth.auth_hosts_token_no_sync(
            self.env_assist.get_env(),
            {
                "node3": HostWithTokenAuthData(
                    "TOKEN", [Destination("node3", 2224)]
                ),
                "node4": HostWithTokenAuthData(
                    "TOKEN", [Destination("node4", 2224)]
                ),
            },
        )

    def test_invalid_data_empty_token(self):
        self.env_assist.assert_raise_library_error(
            lambda: auth.auth_hosts_token_no_sync(
                self.env_assist.get_env(),
                {
                    "node2": HostWithTokenAuthData(
                        "", [Destination("node2", 2224)]
                    )
                },
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="token",
                    option_value="",
                    allowed_values="a string (min length: 1) (max length: 512)",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ]
        )

    def test_error_writing_file(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS, settings.pcsd_known_hosts_location
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            fixture_known_hosts_file_content(
                2,
                _FIXTURE_KNOWN_HOSTS
                | {"A": PcsKnownHost("A", "TOKEN", [Destination("A", 2224)])},
            ).encode("utf-8"),
            can_overwrite=True,
            exception_msg="some error",
            exception_action="",
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.auth_hosts_token_no_sync(
                self.env_assist.get_env(),
                {"A": HostWithTokenAuthData("TOKEN", [Destination("A", 2224)])},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    operation="write",
                    reason="some error",
                    file_path=settings.pcsd_known_hosts_location,
                )
            ]
        )


class AuthHosts(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.node_labels = list(_FIXTURE_KNOWN_HOSTS.keys())
        self.config.env.set_known_nodes(self.node_labels)

    def fixture_send_new_tokens_in_cluster(
        self, new_tokens: dict[str, PcsKnownHost]
    ):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF, settings.corosync_conf_file, name="corosync.exists"
        )
        self.config.corosync_conf.load(self.node_labels)
        fixture_save_sync_new_known_hosts_success(
            self.config,
            file_data_version=2,
            known_hosts=_FIXTURE_KNOWN_HOSTS | new_tokens,
            node_labels=self.node_labels,
        )

    def test_success_not_in_cluster(self):
        self.config.http.place_multinode_call(
            node_labels=["node3"],
            output="TOKEN",
            action="remote/auth",
            param_list=[("username", "username"), ("password", "password")],
            name="auth",
        )
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync.exists",
        )
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_data=fixture_known_hosts_file_content(
                2,
                _FIXTURE_KNOWN_HOSTS
                | {
                    "node3": PcsKnownHost(
                        "node3", "TOKEN", [Destination("node3", 2224)]
                    )
                },
            ).encode("utf-8"),
            can_overwrite=True,
        )

        auth.auth_hosts(
            self.env_assist.get_env(),
            {
                "node3": HostAuthData(
                    "username", "password", [Destination("node3", 2224)]
                )
            },
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.AUTHORIZATION_SUCCESSFUL,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
            ]
        )

    def test_not_in_cluster_error_writing_file(self):
        self.config.http.place_multinode_call(
            node_labels=["node3"],
            output="TOKEN",
            action="remote/auth",
            param_list=[("username", "username"), ("password", "password")],
            name="auth",
        )
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync.exists",
        )
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_data=fixture_known_hosts_file_content(
                2,
                _FIXTURE_KNOWN_HOSTS
                | {
                    "node3": PcsKnownHost(
                        "node3", "TOKEN", [Destination("node3", 2224)]
                    )
                },
            ).encode("utf-8"),
            can_overwrite=True,
            exception_msg="some error",
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.auth_hosts(
                self.env_assist.get_env(),
                {
                    "node3": HostAuthData(
                        "username", "password", [Destination("node3", 2224)]
                    )
                },
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.AUTHORIZATION_SUCCESSFUL,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    operation="write",
                    reason="some error",
                    file_path=settings.pcsd_known_hosts_location,
                ),
            ]
        )

    def test_success_in_cluster(self):
        self.config.http.place_multinode_call(
            node_labels=["node3", "node4"],
            output="TOKEN",
            action="remote/auth",
            param_list=[("username", "username"), ("password", "password")],
            name="auth",
        )
        self.fixture_send_new_tokens_in_cluster(
            {
                "node3": PcsKnownHost(
                    "node3", "TOKEN", [Destination("node3", 2224)]
                ),
                "node4": PcsKnownHost(
                    "node4", "TOKEN", [Destination("node4", 2224)]
                ),
            }
        )

        auth.auth_hosts(
            self.env_assist.get_env(),
            {
                "node3": HostAuthData(
                    "username", "password", [Destination("node3", 2224)]
                ),
                "node4": HostAuthData(
                    "username", "password", [Destination("node4", 2224)]
                ),
            },
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.AUTHORIZATION_SUCCESSFUL,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
                fixture.info(
                    reports.codes.AUTHORIZATION_SUCCESSFUL,
                    context=reports.dto.ReportItemContextDto("node4"),
                ),
            ]
            + fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS, node_labels=self.node_labels
            )
        )

    def test_success_only_able_to_auth_some_nodes(self):
        self.config.http.place_multinode_call(
            communication_list=[
                {"label": "node3", "output": "TOKEN"},
                {"label": "node4", "output": ""},
            ],
            action="remote/auth",
            param_list=[("username", "username"), ("password", "password")],
            name="auth",
        )
        self.fixture_send_new_tokens_in_cluster(
            {
                "node3": PcsKnownHost(
                    "node3", "TOKEN", [Destination("node3", 2224)]
                )
            }
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.auth_hosts(
                self.env_assist.get_env(),
                {
                    "node3": HostAuthData(
                        "username", "password", [Destination("node3", 2224)]
                    ),
                    "node4": HostAuthData(
                        "username", "password", [Destination("node4", 2224)]
                    ),
                },
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.AUTHORIZATION_SUCCESSFUL,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
                fixture.error(
                    reports.codes.INCORRECT_CREDENTIALS,
                    context=reports.dto.ReportItemContextDto("node4"),
                ),
            ]
            + fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS, node_labels=self.node_labels
            )
        )

    def test_unable_to_auth_any_host(self):
        self.config.http.place_multinode_call(
            node_labels=["node3", "node4"],
            output="",  # empty token means that auth was not successful
            action="remote/auth",
            param_list=[("username", "username"), ("password", "password")],
            name="auth",
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.auth_hosts(
                self.env_assist.get_env(),
                {
                    "node3": HostAuthData(
                        "username", "password", [Destination("node3", 2224)]
                    ),
                    "node4": HostAuthData(
                        "username", "password", [Destination("node4", 2224)]
                    ),
                },
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INCORRECT_CREDENTIALS,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
                fixture.error(
                    reports.codes.INCORRECT_CREDENTIALS,
                    context=reports.dto.ReportItemContextDto("node4"),
                ),
            ]
        )

    def test_invalid_auth_data(self):
        self.env_assist.assert_raise_library_error(
            lambda: auth.auth_hosts(
                self.env_assist.get_env(),
                {
                    "node1": HostAuthData("username", "password", []),
                    "node2": HostAuthData(
                        "username", "password", [Destination("", 80)]
                    ),
                },
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="dest_list",
                    option_value="[]",
                    allowed_values="non-empty list of destinations for node 'node1'",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="addr",
                    option_value="",
                    allowed_values="address for node 'node2'",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_some_cluster_nodes_not_known_to_pcs(self):
        self.config.http.place_multinode_call(
            node_labels=["node3"],
            output="TOKEN",
            action="remote/auth",
            param_list=[("username", "username"), ("password", "password")],
            name="auth",
        )
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF, settings.corosync_conf_file, name="corosync.exists"
        )
        self.config.env.set_known_nodes(["node1"])
        self.config.corosync_conf.load(self.node_labels)
        fixture_save_sync_new_known_hosts_success(
            self.config,
            file_data_version=2,
            known_hosts=_FIXTURE_KNOWN_HOSTS
            | {
                "node3": PcsKnownHost(
                    "node3", "TOKEN", [Destination("node3", 2224)]
                )
            },
            node_labels=["node1"],
        )
        self.env_assist.assert_raise_library_error(
            lambda: auth.auth_hosts(
                self.env_assist.get_env(),
                {
                    "node3": HostAuthData(
                        "username", "password", [Destination("node3", 2224)]
                    )
                },
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.AUTHORIZATION_SUCCESSFUL,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
                fixture.error(
                    reports.codes.HOST_NOT_FOUND, host_list=["node2"]
                ),
            ]
            + fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS, node_labels=["node1"]
            )
            + [
                fixture.error(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES_FAILED,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node2"],
                ),
            ]
        )

    def test_no_cluster_nodes_not_known_to_pcs(self):
        self.config.http.place_multinode_call(
            node_labels=["node3"],
            output="TOKEN",
            action="remote/auth",
            param_list=[("username", "username"), ("password", "password")],
            name="auth",
        )
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF, settings.corosync_conf_file, name="corosync.exists"
        )
        self.config.env.set_known_nodes([])
        self.config.corosync_conf.load(self.node_labels)

        self.env_assist.assert_raise_library_error(
            lambda: auth.auth_hosts(
                self.env_assist.get_env(),
                {
                    "node3": HostAuthData(
                        "username", "password", [Destination("node3", 2224)]
                    )
                },
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.AUTHORIZATION_SUCCESSFUL,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
                fixture.error(
                    reports.codes.HOST_NOT_FOUND, host_list=self.node_labels
                ),
                fixture.error(reports.codes.NONE_HOST_FOUND),
            ]
        )

    def fixture_cfgsync_conflict(self) -> str:
        self.config.http.place_multinode_call(
            node_labels=["NEW"],
            output="TOKEN",
            action="remote/auth",
            param_list=[("username", "username"), ("password", "password")],
            name="auth",
        )
        local_file_version = 1
        local_tokens = {"LOCAL": PcsKnownHost("LOCAL", "LOCAL", [])}

        new_tokens = {
            "NEW": PcsKnownHost("NEW", "TOKEN", [Destination("NEW", 2224)]),
        }

        local_file = fixture_known_hosts_file_content(
            local_file_version, local_tokens
        )
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=local_file,
        )
        self.config.raw_file.exists(
            COROSYNC_CONF, settings.corosync_conf_file, name="corosync.exists"
        )
        self.config.corosync_conf.load(self.node_labels)

        return fixture_save_sync_new_known_hosts_conflict(
            self.config,
            cluster_name="test99",
            node_labels=["node1", "node2"],
            file_data_version=local_file_version,
            initial_local_known_hosts=local_tokens,
            new_hosts=new_tokens,
        )

    def test_conflict_upon_conflict(self):
        file_to_save = self.fixture_cfgsync_conflict()
        # write the new file
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_to_save.encode("utf-8"),
            can_overwrite=True,
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.auth_hosts(
                self.env_assist.get_env(),
                {
                    "NEW": HostAuthData(
                        "username", "password", [Destination("NEW", 2224)]
                    )
                },
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.AUTHORIZATION_SUCCESSFUL,
                    context=reports.dto.ReportItemContextDto("NEW"),
                )
            ]
            + fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                node_labels=self.node_labels,
                expected_result="conflict",
                conflict_is_error=False,
            )
            + fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                node_labels=self.node_labels,
                expected_result="conflict",
                conflict_is_error=True,
            )
        )

    def test_conflict_upon_conflict_error_saving_new_file(self):
        file_to_save = self.fixture_cfgsync_conflict()
        # write the new file
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_to_save.encode("utf-8"),
            can_overwrite=True,
            exception_msg="error",
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.auth_hosts(
                self.env_assist.get_env(),
                {
                    "NEW": HostAuthData(
                        "username", "password", [Destination("NEW", 2224)]
                    )
                },
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.AUTHORIZATION_SUCCESSFUL,
                    context=reports.dto.ReportItemContextDto("NEW"),
                )
            ]
            + fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                node_labels=self.node_labels,
                expected_result="conflict",
                conflict_is_error=False,
            )
            + fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                node_labels=self.node_labels,
                expected_result="conflict",
                conflict_is_error=True,
            )
            + [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    operation="write",
                    reason="error",
                    file_path=settings.pcsd_known_hosts_location,
                ),
            ]
        )


class DeauthHosts(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.node_labels = list(_FIXTURE_KNOWN_HOSTS.keys())
        self.config.env.set_known_nodes(self.node_labels)

    def test_success_not_in_cluster(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync.exists",
        )
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_data=fixture_known_hosts_file_content(
                2, {"node1": _FIXTURE_KNOWN_HOSTS["node1"]}
            ).encode("utf-8"),
            can_overwrite=True,
        )

        auth.deauth_hosts(self.env_assist.get_env(), ["node2"])

    def test_not_in_cluster_error_writing_file(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync.exists",
        )
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_data=fixture_known_hosts_file_content(
                2, {"node1": _FIXTURE_KNOWN_HOSTS["node1"]}
            ).encode("utf-8"),
            can_overwrite=True,
            exception_msg="some error",
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.deauth_hosts(self.env_assist.get_env(), ["node2"])
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    operation="write",
                    reason="some error",
                    file_path=settings.pcsd_known_hosts_location,
                ),
            ]
        )

    def test_success_in_cluster(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF, settings.corosync_conf_file, name="corosync.exists"
        )
        self.config.corosync_conf.load(self.node_labels)
        fixture_save_sync_new_known_hosts_success(
            self.config,
            file_data_version=2,
            known_hosts={"node1": _FIXTURE_KNOWN_HOSTS["node1"]},
            node_labels=self.node_labels,
        )

        auth.deauth_hosts(self.env_assist.get_env(), ["node2"])
        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                node_labels=self.node_labels,
            )
        )

    def test_some_hosts_not_found(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF, settings.corosync_conf_file, name="corosync.exists"
        )
        self.config.corosync_conf.load(self.node_labels)
        fixture_save_sync_new_known_hosts_success(
            self.config,
            file_data_version=2,
            known_hosts={"node1": _FIXTURE_KNOWN_HOSTS["node1"]},
            node_labels=self.node_labels,
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.deauth_hosts(
                self.env_assist.get_env(), ["node2", "node3"]
            )
        )
        self.env_assist.assert_reports(
            [fixture.error(reports.codes.HOST_NOT_FOUND, host_list=["node3"])]
            + fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                node_labels=self.node_labels,
            )
        )

    def test_no_hosts_found(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.deauth_hosts(
                self.env_assist.get_env(), ["node3", "node4"]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND, host_list=["node3", "node4"]
                )
            ]
        )

    def test_no_hosts_specified(self):
        self.env_assist.assert_raise_library_error(
            lambda: auth.deauth_hosts(self.env_assist.get_env(), [])
        )
        self.env_assist.assert_reports(
            [fixture.error(reports.codes.NO_HOST_SPECIFIED)]
        )

    def test_some_cluster_nodes_not_known_to_pcs(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF, settings.corosync_conf_file, name="corosync.exists"
        )
        self.config.env.set_known_nodes(["node1"])
        self.config.corosync_conf.load(self.node_labels)
        fixture_save_sync_new_known_hosts_success(
            self.config,
            file_data_version=2,
            known_hosts={"node1": _FIXTURE_KNOWN_HOSTS["node1"]},
            node_labels=["node1"],
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.deauth_hosts(self.env_assist.get_env(), ["node2"])
        )
        self.env_assist.assert_reports(
            [fixture.error(reports.codes.HOST_NOT_FOUND, host_list=["node2"])]
            + fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                node_labels=["node1"],
            )
            + [
                fixture.error(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES_FAILED,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node2"],
                ),
            ]
        )

    def test_no_cluster_nodes_not_known_to_pcs(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF, settings.corosync_conf_file, name="corosync.exists"
        )
        self.config.env.set_known_nodes([])
        self.config.corosync_conf.load(self.node_labels)

        self.env_assist.assert_raise_library_error(
            lambda: auth.deauth_hosts(self.env_assist.get_env(), ["node2"])
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND, host_list=self.node_labels
                ),
                fixture.error(reports.codes.NONE_HOST_FOUND),
            ]
        )

    def fixture_cfgsync_conflict(self):
        local_file_version = 1
        local_tokens = {"LOCAL": PcsKnownHost("LOCAL", "LOCAL", [])}

        local_file = fixture_known_hosts_file_content(
            local_file_version, local_tokens
        )
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=local_file,
        )
        self.config.raw_file.exists(
            COROSYNC_CONF, settings.corosync_conf_file, name="corosync.exists"
        )
        self.config.corosync_conf.load(self.node_labels)

        return fixture_save_sync_new_known_hosts_conflict(
            self.config,
            cluster_name="test99",
            node_labels=self.node_labels,
            file_data_version=local_file_version,
            initial_local_known_hosts=local_tokens,
            new_hosts={},
            hosts_to_remove=["LOCAL"],
        )

    def test_conflict_upon_conflict(self):
        file_to_save = self.fixture_cfgsync_conflict()
        # write the new file
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_to_save.encode("utf-8"),
            can_overwrite=True,
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.deauth_hosts(self.env_assist.get_env(), ["LOCAL"])
        )
        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                node_labels=self.node_labels,
                expected_result="conflict",
                conflict_is_error=False,
            )
            + fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                node_labels=self.node_labels,
                expected_result="conflict",
                conflict_is_error=True,
            )
        )

    def test_conflict_upon_conflict_error_saving_new_file(self):
        file_to_save = self.fixture_cfgsync_conflict()
        # write the new file
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_to_save.encode("utf-8"),
            can_overwrite=True,
            exception_msg="error",
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.deauth_hosts(self.env_assist.get_env(), ["LOCAL"])
        )
        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                node_labels=self.node_labels,
                expected_result="conflict",
                conflict_is_error=False,
            )
            + fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                node_labels=self.node_labels,
                expected_result="conflict",
                conflict_is_error=True,
            )
            + [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    operation="write",
                    reason="error",
                    file_path=settings.pcsd_known_hosts_location,
                )
            ]
        )


class DeauthAllLocalHosts(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_success_not_in_cluster(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync.exists",
        )
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_data=fixture_known_hosts_file_content(2, {}).encode("utf-8"),
            can_overwrite=True,
        )

        auth.deauth_all_local_hosts(self.env_assist.get_env())

    def test_not_in_cluster_error_writing_file(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync.exists",
        )
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_data=fixture_known_hosts_file_content(2, {}).encode("utf-8"),
            can_overwrite=True,
            exception_msg="some error",
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.deauth_all_local_hosts(self.env_assist.get_env())
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    operation="write",
                    reason="some error",
                    file_path=settings.pcsd_known_hosts_location,
                ),
            ]
        )

    def test_success_in_cluster(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF, settings.corosync_conf_file, name="corosync.exists"
        )
        node_labels = list(_FIXTURE_KNOWN_HOSTS.keys())
        self.config.env.set_known_nodes(node_labels)
        self.config.corosync_conf.load(node_labels)
        fixture_save_sync_new_known_hosts_success(
            self.config,
            file_data_version=2,
            known_hosts={},
            node_labels=["node1", "node2"],
        )

        auth.deauth_all_local_hosts(self.env_assist.get_env())
        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                node_labels=node_labels,
            )
        )

    def test_no_hosts_in_local_file(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, {}),
        )

        auth.deauth_all_local_hosts(self.env_assist.get_env())


class KnownHostsChangeNotInCluster(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_validation_failures(self):
        self.env_assist.assert_raise_library_error(
            lambda: auth.known_hosts_change(
                self.env_assist.get_env(),
                hosts_to_add={
                    "node1": HostWithTokenAuthData(
                        "TOKEN", [Destination("node3", 2224)]
                    )
                },
                hosts_to_remove=["node1"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_CANNOT_ADD_AND_REMOVE_ITEMS_AT_THE_SAME_TIME,
                    container_type=None,
                    container_id=None,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_HOST,
                    item_list=["node1"],
                )
            ]
        )

    def test_success(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync.exists",
        )
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            fixture_known_hosts_file_content(
                2,
                {
                    "node2": _FIXTURE_KNOWN_HOSTS["node2"],
                    "node3": PcsKnownHost(
                        "node3", "TOKEN", [Destination("node3", 2224)]
                    ),
                    "node4": PcsKnownHost(
                        "node4", "TOKEN", [Destination("node4", 2224)]
                    ),
                },
            ).encode("utf-8"),
            can_overwrite=True,
        )

        auth.known_hosts_change(
            self.env_assist.get_env(),
            hosts_to_add={
                "node3": HostWithTokenAuthData(
                    "TOKEN", [Destination("node3", 2224)]
                ),
                "node4": HostWithTokenAuthData(
                    "TOKEN", [Destination("node4", 2224)]
                ),
            },
            hosts_to_remove=["node1"],
        )

    def test_error_reading_file(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            exception_msg="some error",
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.known_hosts_change(
                self.env_assist.get_env(),
                hosts_to_add={
                    "node3": HostWithTokenAuthData(
                        "TOKEN", [Destination("node3", 2224)]
                    ),
                },
                hosts_to_remove=["node1"],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    operation="read",
                    reason="some error",
                    file_path=settings.pcsd_known_hosts_location,
                )
            ],
        )

    def test_error_writing_file(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync.exists",
        )
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            fixture_known_hosts_file_content(
                2,
                {
                    "node2": _FIXTURE_KNOWN_HOSTS["node2"],
                    "node3": PcsKnownHost(
                        "node3", "TOKEN", [Destination("node3", 2224)]
                    ),
                },
            ).encode("utf-8"),
            can_overwrite=True,
            exception_msg="some error",
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.known_hosts_change(
                self.env_assist.get_env(),
                hosts_to_add={
                    "node3": HostWithTokenAuthData(
                        "TOKEN", [Destination("node3", 2224)]
                    ),
                },
                hosts_to_remove=["node1"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    operation="write",
                    reason="some error",
                    file_path=settings.pcsd_known_hosts_location,
                )
            ]
        )


class KnownHostsChangeInCluster(TestCase):
    EXPECTED_KNOWN_HOSTS = {
        "node2": _FIXTURE_KNOWN_HOSTS["node2"],
        "node3": PcsKnownHost("node3", "TOKEN", [Destination("node3", 2224)]),
    }

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.node_labels = list(_FIXTURE_KNOWN_HOSTS.keys())
        self.config.env.set_known_nodes(self.node_labels)

    def fixture_read_local_files(self):
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.exists",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_file_content(1, _FIXTURE_KNOWN_HOSTS),
        )
        self.config.raw_file.exists(
            COROSYNC_CONF, settings.corosync_conf_file, name="corosync.exists"
        )
        self.config.corosync_conf.load(self.node_labels)

    def test_success(self):
        self.fixture_read_local_files()
        fixture_save_sync_new_known_hosts_success(
            self.config,
            file_data_version=2,
            known_hosts=self.EXPECTED_KNOWN_HOSTS,
            node_labels=self.node_labels,
        )

        auth.known_hosts_change(
            self.env_assist.get_env(),
            hosts_to_add={
                "node3": HostWithTokenAuthData(
                    "TOKEN", [Destination("node3", 2224)]
                ),
            },
            hosts_to_remove=["node1"],
        )

        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS, node_labels=self.node_labels
            )
        )

    def test_conflict_syncing_known_hosts(self):
        self.fixture_read_local_files()
        new_file = fixture_save_sync_new_known_hosts_conflict(
            self.config,
            self.node_labels,
            _FIXTURE_KNOWN_HOSTS,
            new_hosts={
                "node3": PcsKnownHost(
                    "node3", "TOKEN", [Destination("node3", 2224)]
                )
            },
            hosts_to_remove=["node1"],
        )
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_data=new_file.encode(),
            can_overwrite=True,
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.known_hosts_change(
                self.env_assist.get_env(),
                hosts_to_add={
                    "node3": HostWithTokenAuthData(
                        "TOKEN", [Destination("node3", 2224)]
                    ),
                },
                hosts_to_remove=["node1"],
            )
        )

        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                expected_result="conflict",
                conflict_is_error=False,
                node_labels=self.node_labels,
            )
            + fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                expected_result="conflict",
                conflict_is_error=True,
                node_labels=self.node_labels,
            )
        )

    def test_conflict_syncing_known_hosts_error_writing_new_file(self):
        self.fixture_read_local_files()
        new_file = fixture_save_sync_new_known_hosts_conflict(
            self.config,
            self.node_labels,
            _FIXTURE_KNOWN_HOSTS,
            new_hosts={
                "node3": PcsKnownHost(
                    "node3", "TOKEN", [Destination("node3", 2224)]
                )
            },
            hosts_to_remove=["node1"],
        )
        self.config.raw_file.write(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_data=new_file.encode(),
            can_overwrite=True,
            exception_msg="some error",
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.known_hosts_change(
                self.env_assist.get_env(),
                hosts_to_add={
                    "node3": HostWithTokenAuthData(
                        "TOKEN", [Destination("node3", 2224)]
                    ),
                },
                hosts_to_remove=["node1"],
            )
        )

        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                expected_result="conflict",
                conflict_is_error=False,
                node_labels=self.node_labels,
            )
            + fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                expected_result="conflict",
                conflict_is_error=True,
                node_labels=self.node_labels,
            )
            + [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    operation="write",
                    reason="some error",
                    file_path=settings.pcsd_known_hosts_location,
                ),
            ]
        )

    def test_error_syncing_known_hosts(self):
        self.fixture_read_local_files()
        fixture_save_sync_new_known_hosts_error(
            self.config,
            self.node_labels,
            file_data_version=2,
            known_hosts=self.EXPECTED_KNOWN_HOSTS,
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.known_hosts_change(
                self.env_assist.get_env(),
                hosts_to_add={
                    "node3": HostWithTokenAuthData(
                        "TOKEN", [Destination("node3", 2224)]
                    ),
                },
                hosts_to_remove=["node1"],
            )
        )

        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=PCS_KNOWN_HOSTS,
                node_labels=self.node_labels,
                expected_result="error",
            )
        )
