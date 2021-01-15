import json
import re
from unittest import TestCase

from pcs import settings
from pcs.common import file_type_codes
from pcs.common.reports import codes as report_codes
from pcs.common.dr import DrRole
from pcs.common.file import RawFileError
from pcs.lib.commands import dr

from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools import fixture


REASON = "error msg"


class CheckLive(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def assert_live_required(self, forbidden_options):
        self.env_assist.assert_raise_library_error(
            lambda: dr.status_all_sites_plaintext(self.env_assist.get_env()),
            [
                fixture.error(
                    report_codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=forbidden_options,
                )
            ],
            expected_in_processor=False,
        )

    def test_mock_corosync(self):
        self.config.env.set_corosync_conf_data("corosync conf")
        self.assert_live_required([file_type_codes.COROSYNC_CONF])

    def test_mock_cib(self):
        self.config.env.set_cib_data("<cib />")
        self.assert_live_required([file_type_codes.CIB])

    def test_mock(self):
        self.config.env.set_corosync_conf_data("corosync conf")
        self.config.env.set_cib_data("<cib />")
        self.assert_live_required(
            [
                file_type_codes.CIB,
                file_type_codes.COROSYNC_CONF,
            ]
        )


class FixtureMixin:
    def _set_up(self, local_node_count=2):
        self.local_node_name_list = [
            f"node{i}" for i in range(1, local_node_count + 1)
        ]
        self.remote_node_name_list = ["recovery-node"]
        self.config.env.set_known_nodes(
            self.local_node_name_list + self.remote_node_name_list
        )
        self.local_status = "local cluster\nstatus\n"
        self.remote_status = "remote cluster\nstatus\n"

    def _fixture_load_configs(self):
        (
            self.config.raw_file.exists(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
            )
            .raw_file.read(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
                content="""
                    {
                        "local": {
                            "role": "PRIMARY"
                        },
                        "remote_sites": [
                            {
                                "nodes": [
                                    {
                                        "name": "recovery-node"
                                    }
                                ],
                                "role": "RECOVERY"
                            }
                        ]
                    }
                """,
            )
            .corosync_conf.load(node_name_list=self.local_node_name_list)
        )

    def _fixture_result(self, local_success=True, remote_success=True):
        return [
            {
                "local_site": True,
                "site_role": DrRole.PRIMARY,
                "status_plaintext": self.local_status if local_success else "",
                "status_successfully_obtained": local_success,
            },
            {
                "local_site": False,
                "site_role": DrRole.RECOVERY,
                "status_plaintext": (
                    self.remote_status if remote_success else ""
                ),
                "status_successfully_obtained": remote_success,
            },
        ]


class Success(FixtureMixin, TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self._set_up()

    def _assert_success(self, hide_inactive_resources, verbose):
        self._fixture_load_configs()
        (
            self.config.http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.local",
                node_labels=self.local_node_name_list[:1],
                hide_inactive_resources=hide_inactive_resources,
                verbose=verbose,
                cluster_status_plaintext=self.local_status,
            ).http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.remote",
                node_labels=self.remote_node_name_list[:1],
                hide_inactive_resources=hide_inactive_resources,
                verbose=verbose,
                cluster_status_plaintext=self.remote_status,
            )
        )
        result = dr.status_all_sites_plaintext(
            self.env_assist.get_env(),
            hide_inactive_resources=hide_inactive_resources,
            verbose=verbose,
        )
        self.assertEqual(result, self._fixture_result())

    def test_success_minimal(self):
        self._assert_success(False, False)

    def test_success_full(self):
        self._assert_success(False, True)

    def test_success_hide_inactive(self):
        self._assert_success(True, False)

    def test_success_all_flags(self):
        self._assert_success(True, True)

    def test_local_not_running_first_node(self):
        self._fixture_load_configs()
        (
            self.config.http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.local",
                cluster_status_plaintext=self.local_status,
                communication_list=[
                    [
                        dict(
                            label=self.local_node_name_list[0],
                            output=json.dumps(
                                dict(
                                    status="error",
                                    status_msg="",
                                    data=None,
                                    report_list=[
                                        {
                                            "severity": "ERROR",
                                            "code": "CRM_MON_ERROR",
                                            "info": {
                                                "reason": REASON,
                                            },
                                            "forceable": None,
                                            "report_text": "translated report",
                                        }
                                    ],
                                )
                            ),
                        )
                    ],
                    [
                        dict(
                            label=self.local_node_name_list[1],
                        )
                    ],
                ],
            ).http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.remote",
                node_labels=self.remote_node_name_list[:1],
                cluster_status_plaintext=self.remote_status,
            )
        )
        result = dr.status_all_sites_plaintext(self.env_assist.get_env())
        self.assertEqual(result, self._fixture_result())
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.local_node_name_list[0],
                    command="remote/cluster_status_plaintext",
                    reason="translated report",
                ),
            ]
        )

    def test_local_not_running(self):
        self._fixture_load_configs()
        (
            self.config.http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.local",
                cmd_status="error",
                cmd_status_msg="",
                cluster_status_plaintext="",
                report_list=[
                    {
                        "severity": "ERROR",
                        "code": "CRM_MON_ERROR",
                        "info": {
                            "reason": REASON,
                        },
                        "forceable": None,
                        "report_text": "translated report",
                    }
                ],
                communication_list=[
                    [
                        dict(
                            label=self.local_node_name_list[0],
                        )
                    ],
                    [
                        dict(
                            label=self.local_node_name_list[1],
                        )
                    ],
                ],
            ).http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.remote",
                node_labels=self.remote_node_name_list[:1],
                cluster_status_plaintext=self.remote_status,
            )
        )
        result = dr.status_all_sites_plaintext(self.env_assist.get_env())
        self.assertEqual(result, self._fixture_result(local_success=False))
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=node,
                    command="remote/cluster_status_plaintext",
                    reason="translated report",
                )
                for node in self.local_node_name_list
            ]
        )

    def test_remote_not_running(self):
        self._fixture_load_configs()
        (
            self.config.http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.local",
                node_labels=self.local_node_name_list[:1],
                cluster_status_plaintext=self.local_status,
            ).http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.remote",
                node_labels=self.remote_node_name_list[:1],
                cmd_status="error",
                cmd_status_msg="",
                cluster_status_plaintext="",
                report_list=[
                    {
                        "severity": "ERROR",
                        "code": "CRM_MON_ERROR",
                        "info": {
                            "reason": REASON,
                        },
                        "forceable": None,
                        "report_text": "translated report",
                    }
                ],
            )
        )
        result = dr.status_all_sites_plaintext(self.env_assist.get_env())
        self.assertEqual(result, self._fixture_result(remote_success=False))
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=node,
                    command="remote/cluster_status_plaintext",
                    reason="translated report",
                )
                for node in self.remote_node_name_list
            ]
        )

    def test_both_not_running(self):
        self._fixture_load_configs()
        (
            self.config.http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.local",
                cmd_status="error",
                cmd_status_msg="",
                cluster_status_plaintext="",
                report_list=[
                    {
                        "severity": "ERROR",
                        "code": "CRM_MON_ERROR",
                        "info": {
                            "reason": REASON,
                        },
                        "forceable": None,
                        "report_text": "translated report",
                    }
                ],
                communication_list=[
                    [
                        dict(
                            label=self.local_node_name_list[0],
                        )
                    ],
                    [
                        dict(
                            label=self.local_node_name_list[1],
                        )
                    ],
                ],
            ).http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.remote",
                node_labels=self.remote_node_name_list[:1],
                cmd_status="error",
                cmd_status_msg="",
                cluster_status_plaintext="",
                report_list=[
                    {
                        "severity": "ERROR",
                        "code": "CRM_MON_ERROR",
                        "info": {
                            "reason": REASON,
                        },
                        "forceable": None,
                        "report_text": "translated report",
                    }
                ],
            )
        )
        result = dr.status_all_sites_plaintext(self.env_assist.get_env())
        self.assertEqual(
            result,
            self._fixture_result(local_success=False, remote_success=False),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=node,
                    command="remote/cluster_status_plaintext",
                    reason="translated report",
                )
                for node in (
                    self.local_node_name_list + self.remote_node_name_list
                )
            ]
        )


class CommunicationIssue(FixtureMixin, TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self._set_up()

    def test_unknown_node(self):
        self.config.env.set_known_nodes(
            self.local_node_name_list[1:] + self.remote_node_name_list
        )
        self._fixture_load_configs()
        (
            self.config.http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.local",
                node_labels=self.local_node_name_list[1:],
                cluster_status_plaintext=self.local_status,
            ).http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.remote",
                node_labels=self.remote_node_name_list[:1],
                cluster_status_plaintext=self.remote_status,
            )
        )
        result = dr.status_all_sites_plaintext(self.env_assist.get_env())
        self.assertEqual(result, self._fixture_result())
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.HOST_NOT_FOUND,
                    host_list=["node1"],
                ),
            ]
        )

    def test_unknown_all_nodes_in_site(self):
        self.config.env.set_known_nodes(self.local_node_name_list)
        self._fixture_load_configs()
        self.env_assist.assert_raise_library_error(
            lambda: dr.status_all_sites_plaintext(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.HOST_NOT_FOUND,
                    host_list=self.remote_node_name_list,
                ),
                fixture.error(
                    report_codes.NONE_HOST_FOUND,
                ),
            ]
        )

    def test_missing_node_names(self):
        self._fixture_load_configs()
        coro_call = self.config.calls.get("corosync_conf.load")
        (
            self.config.http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.local",
                node_labels=[],
            ).http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.remote",
                node_labels=self.remote_node_name_list[:1],
                cluster_status_plaintext=self.remote_status,
            )
        )
        coro_call.content = re.sub(r"name: node\d", "", coro_call.content)
        result = dr.status_all_sites_plaintext(self.env_assist.get_env())
        self.assertEqual(result, self._fixture_result(local_success=False))
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=False,
                ),
            ]
        )

    def test_node_issues(self):
        self._set_up(local_node_count=7)
        self._fixture_load_configs()
        (
            self.config.http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.local",
                cluster_status_plaintext=self.local_status,
                communication_list=[
                    [
                        dict(
                            label=self.local_node_name_list[0],
                            was_connected=False,
                        )
                    ],
                    [
                        dict(
                            label=self.local_node_name_list[1],
                            response_code=401,
                        )
                    ],
                    [
                        dict(
                            label=self.local_node_name_list[2],
                            response_code=500,
                        )
                    ],
                    [
                        dict(
                            label=self.local_node_name_list[3],
                            response_code=404,
                        )
                    ],
                    [
                        dict(
                            label=self.local_node_name_list[4],
                            output="invalid data",
                        )
                    ],
                    [
                        dict(
                            label=self.local_node_name_list[5],
                            output=json.dumps(dict(status="success")),
                        )
                    ],
                    [
                        dict(
                            label=self.local_node_name_list[6],
                        )
                    ],
                ],
            ).http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.remote",
                node_labels=self.remote_node_name_list[:1],
                cluster_status_plaintext=self.remote_status,
            )
        )
        result = dr.status_all_sites_plaintext(self.env_assist.get_env())
        self.assertEqual(result, self._fixture_result())
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    command="remote/cluster_status_plaintext",
                    node="node1",
                    reason=None,
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED,
                    command="remote/cluster_status_plaintext",
                    node="node2",
                    reason="HTTP error: 401",
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR,
                    command="remote/cluster_status_plaintext",
                    node="node3",
                    reason="HTTP error: 500",
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNSUPPORTED_COMMAND,
                    command="remote/cluster_status_plaintext",
                    node="node4",
                    reason="HTTP error: 404",
                ),
                fixture.warn(
                    report_codes.INVALID_RESPONSE_FORMAT,
                    node="node5",
                ),
                fixture.warn(
                    report_codes.INVALID_RESPONSE_FORMAT,
                    node="node6",
                ),
            ]
        )

    def test_local_site_down(self):
        self._fixture_load_configs()
        (
            self.config.http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.local",
                cluster_status_plaintext=self.local_status,
                communication_list=[
                    [
                        dict(
                            label=self.local_node_name_list[0],
                            was_connected=False,
                        )
                    ],
                    [
                        dict(
                            label=self.local_node_name_list[1],
                            was_connected=False,
                        )
                    ],
                ],
            ).http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.remote",
                node_labels=self.remote_node_name_list[:1],
                cluster_status_plaintext=self.remote_status,
            )
        )
        result = dr.status_all_sites_plaintext(self.env_assist.get_env())
        self.assertEqual(result, self._fixture_result(local_success=False))
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    command="remote/cluster_status_plaintext",
                    node="node1",
                    reason=None,
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    command="remote/cluster_status_plaintext",
                    node="node2",
                    reason=None,
                ),
            ]
        )

    def test_remote_site_down(self):
        self._fixture_load_configs()
        (
            self.config.http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.local",
                node_labels=self.local_node_name_list[:1],
                cluster_status_plaintext=self.local_status,
            ).http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.remote",
                cluster_status_plaintext=self.remote_status,
                communication_list=[
                    [
                        dict(
                            label=self.remote_node_name_list[0],
                            was_connected=False,
                        )
                    ],
                ],
            )
        )
        result = dr.status_all_sites_plaintext(self.env_assist.get_env())
        self.assertEqual(result, self._fixture_result(remote_success=False))
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    command="remote/cluster_status_plaintext",
                    node="recovery-node",
                    reason=None,
                ),
            ]
        )

    def test_both_sites_down(self):
        self._fixture_load_configs()
        (
            self.config.http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.local",
                cluster_status_plaintext=self.local_status,
                communication_list=[
                    [
                        dict(
                            label=self.local_node_name_list[0],
                            was_connected=False,
                        )
                    ],
                    [
                        dict(
                            label=self.local_node_name_list[1],
                            was_connected=False,
                        )
                    ],
                ],
            ).http.status.get_full_cluster_status_plaintext(
                name="http.status.get_full_cluster_status_plaintext.remote",
                cluster_status_plaintext=self.remote_status,
                communication_list=[
                    [
                        dict(
                            label=self.remote_node_name_list[0],
                            was_connected=False,
                        )
                    ],
                ],
            )
        )
        result = dr.status_all_sites_plaintext(self.env_assist.get_env())
        self.assertEqual(
            result,
            self._fixture_result(local_success=False, remote_success=False),
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    command="remote/cluster_status_plaintext",
                    node="node1",
                    reason=None,
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    command="remote/cluster_status_plaintext",
                    node="node2",
                    reason=None,
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    command="remote/cluster_status_plaintext",
                    node="recovery-node",
                    reason=None,
                ),
            ]
        )


class FatalConfigIssue(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_config_missing(self):
        (
            self.config.raw_file.exists(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
                exists=False,
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.status_all_sites_plaintext(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.DR_CONFIG_DOES_NOT_EXIST,
                ),
            ]
        )

    def test_config_read_error(self):
        (
            self.config.raw_file.exists(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
            ).raw_file.read(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
                exception_msg=REASON,
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.status_all_sites_plaintext(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_DR_CONFIG,
                    file_path=settings.pcsd_dr_config_location,
                    operation=RawFileError.ACTION_READ,
                    reason=REASON,
                ),
            ]
        )

    def test_config_parse_error(self):
        (
            self.config.raw_file.exists(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
            ).raw_file.read(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
                content="bad content",
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.status_all_sites_plaintext(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.PARSE_ERROR_JSON_FILE,
                    file_type_code=file_type_codes.PCS_DR_CONFIG,
                    file_path=settings.pcsd_dr_config_location,
                    line_number=1,
                    column_number=1,
                    position=0,
                    reason="Expecting value",
                    full_msg="Expecting value: line 1 column 1 (char 0)",
                ),
            ]
        )

    def test_corosync_conf_read_error(self):
        (
            self.config.raw_file.exists(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
            )
            .raw_file.read(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
                content="{}",
            )
            .corosync_conf.load_content("", exception_msg=REASON)
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.status_all_sites_plaintext(self.env_assist.get_env()),
            [
                fixture.error(
                    report_codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.COROSYNC_CONF,
                    operation=RawFileError.ACTION_READ,
                    reason=REASON,
                    file_path=settings.corosync_conf_file,
                ),
            ],
            expected_in_processor=False,
        )

    def test_corosync_conf_parse_error(self):
        (
            self.config.raw_file.exists(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
            )
            .raw_file.read(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
                content="{}",
            )
            .corosync_conf.load_content("wrong {\n  corosync")
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.status_all_sites_plaintext(self.env_assist.get_env()),
            [
                fixture.error(
                    # pylint: disable=line-too-long
                    report_codes.PARSE_ERROR_COROSYNC_CONF_LINE_IS_NOT_SECTION_NOR_KEY_VALUE
                ),
            ],
            expected_in_processor=False,
        )
