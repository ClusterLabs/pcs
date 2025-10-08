import json
from typing import Optional
from unittest import TestCase

from pcs import settings
from pcs.common import reports
from pcs.common.auth import HostAuthData, HostWithTokenAuthData
from pcs.common.communication.const import COM_STATUS_SUCCESS
from pcs.common.communication.dto import InternalCommunicationResultDto
from pcs.common.communication.types import CommunicationResultStatus
from pcs.common.file_type_codes import COROSYNC_CONF, PCS_KNOWN_HOSTS
from pcs.common.host import Destination, PcsKnownHost
from pcs.common.interface.dto import to_dict
from pcs.lib.commands import auth
from pcs.lib.host.config.exporter import Exporter as KnownHostsExporter
from pcs.lib.host.config.types import KnownHosts

from pcs_test.tier0.lib.pcs_cfgsync.test_save_sync import (
    FixtureFetchNewestFileMixin,
)
from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


def fixture_known_hosts_file_content(
    data_version, hosts: dict[str, PcsKnownHost]
) -> str:
    return KnownHostsExporter.export(
        KnownHosts(
            format_version=1, data_version=data_version, known_hosts=hosts
        )
    ).decode("utf-8")


def fixture_communication_result_string(
    status: CommunicationResultStatus = COM_STATUS_SUCCESS,
    status_msg: Optional[str] = None,
    report_list: Optional[reports.dto.ReportItemDto] = None,
    data="",
) -> str:
    return json.dumps(
        to_dict(
            InternalCommunicationResultDto(
                status=status,
                status_msg=status_msg,
                report_list=report_list or [],
                data=data,
            )
        )
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


class AuthHosts(TestCase, FixtureFetchNewestFileMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

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
        self.config.env.set_known_nodes(["node1", "node2"])
        self.config.corosync_conf.load(["node1", "node2"])
        self.config.http.pcs_cfgsync.set_configs(
            "test99",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    2, _FIXTURE_KNOWN_HOSTS | new_tokens
                )
            },
            node_labels=["node1", "node2"],
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
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto(node="node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto(node="node2"),
                ),
            ]
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
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto(node="node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto(node="node2"),
                ),
            ]
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
        self.config.corosync_conf.load(["node1", "node2"])
        self.config.http.pcs_cfgsync.set_configs(
            "test99",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    2,
                    _FIXTURE_KNOWN_HOSTS
                    | {
                        "node3": PcsKnownHost(
                            "node3", "TOKEN", [Destination("node3", 2224)]
                        )
                    },
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
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto(node="node1"),
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
        self.config.corosync_conf.load(["node1", "node2"])

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
                    reports.codes.HOST_NOT_FOUND, host_list=["node1", "node2"]
                ),
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

        remote_file_version = 42
        remote_tokens = {"REMOTE": PcsKnownHost("REMOTE", "REMOTE", [])}

        new_tokens = {
            "NEW": PcsKnownHost("NEW", "TOKEN", [Destination("NEW", 2224)]),
        }

        even_more_new_remote_file_version = 69
        even_more_new_remote_tokens = {"WHAT": PcsKnownHost("WHAT", "WHAT", [])}

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
        self.config.env.set_known_nodes(["node1", "node2"])
        self.config.corosync_conf.load(["node1", "node2"])
        self.config.http.pcs_cfgsync.set_configs(
            "test99",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    local_file_version + 1, local_tokens | new_tokens
                )
            },
            communication_list=[
                {
                    "label": "node1",
                    "output": json.dumps(
                        {
                            "status": "ok",
                            "result": {PCS_KNOWN_HOSTS: "rejected"},
                        }
                    ),
                },
                {"label": "node2"},
            ],
            name="set_configs.1",
        )

        # fetching the newest config from cluster
        remote_file = fixture_known_hosts_file_content(
            remote_file_version, remote_tokens
        )
        self.fixture_fetch_newest_file(
            local_file, remote_file, call_name_suffix="1", cluster_name="test99"
        )

        # sending the merged tokens
        self.config.http.pcs_cfgsync.set_configs(
            "test99",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    remote_file_version + 1,
                    local_tokens | new_tokens | remote_tokens,
                )
            },
            communication_list=[
                {
                    "label": "node1",
                    "output": json.dumps(
                        {
                            "status": "ok",
                            "result": {PCS_KNOWN_HOSTS: "rejected"},
                        }
                    ),
                },
                {"label": "node2"},
            ],
            name="set_configs.2",
        )

        # fetching the even more newest config from cluster
        even_more_new_remote_file = fixture_known_hosts_file_content(
            even_more_new_remote_file_version, even_more_new_remote_tokens
        )
        self.fixture_fetch_newest_file(
            local_file,
            even_more_new_remote_file,
            call_name_suffix="2",
            cluster_name="test99",
        )

        return even_more_new_remote_file

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
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.error(reports.codes.PCS_CFGSYNC_CONFLICT_REPEAT_ACTION),
            ]
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
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    operation="write",
                    reason="error",
                    file_path=settings.pcsd_known_hosts_location,
                ),
                fixture.error(reports.codes.PCS_CFGSYNC_CONFLICT_REPEAT_ACTION),
            ]
        )


class DeauthHosts(TestCase, FixtureFetchNewestFileMixin):
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
        self.config.env.set_known_nodes(["node1", "node2"])
        self.config.corosync_conf.load(["node1", "node2"])
        self.config.http.pcs_cfgsync.set_configs(
            "test99",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    2, {"node1": _FIXTURE_KNOWN_HOSTS["node1"]}
                )
            },
            node_labels=["node1", "node2"],
        )

        auth.deauth_hosts(self.env_assist.get_env(), ["node2"])
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto(node="node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto(node="node2"),
                ),
            ]
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
        self.config.env.set_known_nodes(["node1", "node2"])
        self.config.corosync_conf.load(["node1", "node2"])
        self.config.http.pcs_cfgsync.set_configs(
            "test99",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    2, {"node1": _FIXTURE_KNOWN_HOSTS["node1"]}
                )
            },
            node_labels=["node1", "node2"],
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.deauth_hosts(
                self.env_assist.get_env(), ["node2", "node3"]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND, host_list=["node3"]
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto(node="node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto(node="node2"),
                ),
            ]
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
        self.config.corosync_conf.load(["node1", "node2"])
        self.config.http.pcs_cfgsync.set_configs(
            "test99",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    2, {"node1": _FIXTURE_KNOWN_HOSTS["node1"]}
                )
            },
            node_labels=["node1"],
        )

        self.env_assist.assert_raise_library_error(
            lambda: auth.deauth_hosts(self.env_assist.get_env(), ["node2"])
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND, host_list=["node2"]
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto(node="node1"),
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
        self.config.corosync_conf.load(["node1", "node2"])

        self.env_assist.assert_raise_library_error(
            lambda: auth.deauth_hosts(self.env_assist.get_env(), ["node2"])
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND, host_list=["node1", "node2"]
                ),
                fixture.error(reports.codes.NONE_HOST_FOUND),
            ]
        )

    def fixture_cfgsync_conflict(self):
        local_file_version = 1
        local_tokens = {"LOCAL": PcsKnownHost("LOCAL", "LOCAL", [])}

        remote_file_version = 42
        remote_tokens = {"REMOTE": PcsKnownHost("REMOTE", "REMOTE", [])}

        even_more_new_remote_file_version = 69
        even_more_new_remote_tokens = {"WHAT": PcsKnownHost("WHAT", "WHAT", [])}

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
        self.config.env.set_known_nodes(["node1", "node2"])
        self.config.corosync_conf.load(["node1", "node2"])
        self.config.http.pcs_cfgsync.set_configs(
            "test99",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    local_file_version + 1, {}
                )
            },
            communication_list=[
                {
                    "label": "node1",
                    "output": json.dumps(
                        {
                            "status": "ok",
                            "result": {PCS_KNOWN_HOSTS: "rejected"},
                        }
                    ),
                },
                {"label": "node2"},
            ],
            name="set_configs.1",
        )

        # fetching the newest config from cluster
        remote_file = fixture_known_hosts_file_content(
            remote_file_version, remote_tokens
        )
        self.fixture_fetch_newest_file(
            local_file, remote_file, call_name_suffix="1", cluster_name="test99"
        )

        # sending the merged tokens
        self.config.http.pcs_cfgsync.set_configs(
            "test99",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    remote_file_version + 1,
                    remote_tokens,
                )
            },
            communication_list=[
                {
                    "label": "node1",
                    "output": json.dumps(
                        {
                            "status": "ok",
                            "result": {PCS_KNOWN_HOSTS: "rejected"},
                        }
                    ),
                },
                {"label": "node2"},
            ],
            name="set_configs.2",
        )

        # fetching the even more newest config from cluster
        even_more_new_remote_file = fixture_known_hosts_file_content(
            even_more_new_remote_file_version, even_more_new_remote_tokens
        )
        self.fixture_fetch_newest_file(
            local_file,
            even_more_new_remote_file,
            call_name_suffix="2",
            cluster_name="test99",
        )

        return even_more_new_remote_file

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
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.error(reports.codes.PCS_CFGSYNC_CONFLICT_REPEAT_ACTION),
            ]
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
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    operation="write",
                    reason="error",
                    file_path=settings.pcsd_known_hosts_location,
                ),
                fixture.error(reports.codes.PCS_CFGSYNC_CONFLICT_REPEAT_ACTION),
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
        self.config.env.set_known_nodes(["node1", "node2"])
        self.config.corosync_conf.load(["node1", "node2"])
        self.config.http.pcs_cfgsync.set_configs(
            "test99",
            {PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(2, {})},
            node_labels=["node1", "node2"],
        )

        auth.deauth_all_local_hosts(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto(node="node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto(node="node2"),
                ),
            ]
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
