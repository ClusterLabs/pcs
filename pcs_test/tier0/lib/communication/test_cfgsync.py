import json
from typing import Optional
from unittest import TestCase

import pycurl

from pcs.common import file_type_codes, reports
from pcs.common.cfgsync_dto import SyncConfigsDto
from pcs.common.communication.const import (
    COM_STATUS_ERROR,
    COM_STATUS_SUCCESS,
    COM_STATUS_UNKNOWN_CMD,
)
from pcs.common.communication.dto import InternalCommunicationResultDto
from pcs.common.communication.types import CommunicationResultStatus
from pcs.common.interface.dto import to_dict
from pcs.common.node_communicator import (
    Request,
    RequestData,
    RequestTarget,
    Response,
)
from pcs.lib.communication.cfgsync import (
    ConfigInfo,
    GetConfigs,
)

from pcs_test.tools import fixture
from pcs_test.tools.custom_mock import (
    MockCurlSimple,
    MockLibraryReportProcessor,
)


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


def fixture_fallback_request(node_label="NODE"):
    return Request(
        RequestTarget(node_label),
        RequestData(
            action="remote/get_configs",
            structured_data=[("cluster_name", "test")],
        ),
    )


def fixture_request_apiv1(node_label="NODE"):
    return Request(
        RequestTarget(node_label),
        RequestData(
            "api/v1/cfgsync-get-configs/v1",
            data=json.dumps({"cluster_name": "test"}),
        ),
    )


def fixture_response(response_code=200, output="", request=None):
    return Response(
        MockCurlSimple(
            info={pycurl.RESPONSE_CODE: response_code},
            output=output,
            request=request,
        ),
        was_connected=True,
    )


def fixture_fallback_response(
    response_code: int = 200, output="", node_label="NODE"
):
    return fixture_response(
        response_code, output, request=fixture_fallback_request(node_label)
    )


def fixture_apiv1_response(
    response_code: int = 200,
    com_status=COM_STATUS_SUCCESS,
    status_msg=None,
    data="",
    node_label="NODE",
    report_list=None,
):
    return fixture_response(
        response_code,
        output=fixture_communication_result_string(
            status=com_status,
            status_msg=status_msg,
            data=data,
            report_list=report_list or [],
        ),
        request=fixture_request_apiv1(node_label),
    )


class GetConfigsApiv1ResponseProcessing(TestCase):
    def setUp(self):
        self.reporter = MockLibraryReportProcessor()
        self.cmd = GetConfigs(self.reporter, "test")

    def assert_response(self, real, expected):
        self.assertEqual(real.action, expected.action)
        self.assertEqual(real.target.label, expected.target.label)
        self.assertEqual(real.target.dest_list, expected.target.dest_list)
        self.assertEqual(real.data, expected.data)

    def test_empty_response(self):
        requests = self.cmd.on_response(fixture_apiv1_response())
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports(
            [fixture.error(reports.codes.INVALID_RESPONSE_FORMAT, node="NODE")]
        )

    def test_404_returns_fallback_request(self):
        requests = self.cmd.on_response(
            fixture_apiv1_response(response_code=404)
        )

        self.assertEqual(len(requests), 1)
        self.assert_response(requests[0], fixture_fallback_request())
        self.reporter.assert_reports([])

    def test_unknown_cmd_fallback_request(self):
        requests = self.cmd.on_response(
            fixture_apiv1_response(com_status=COM_STATUS_UNKNOWN_CMD)
        )

        self.assertEqual(len(requests), 1)
        self.assert_response(requests[0], fixture_fallback_request())
        self.reporter.assert_reports([])

    def test_single_response_with_files(self):
        requests = self.cmd.on_response(
            fixture_apiv1_response(
                data=SyncConfigsDto(
                    cluster_name="test",
                    configs={
                        file_type_codes.PCS_KNOWN_HOSTS: "foo",
                        file_type_codes.PCS_SETTINGS_CONF: "bar",
                    },
                )
            )
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(
            result.config_files,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [ConfigInfo("NODE", "foo")],
                file_type_codes.PCS_SETTINGS_CONF: [ConfigInfo("NODE", "bar")],
            },
        )
        self.reporter.assert_reports([])

    def test_multiple_responses_with_files(self):
        requests = self.cmd.on_response(
            fixture_apiv1_response(
                node_label="NODE-1",
                data=SyncConfigsDto(
                    cluster_name="test",
                    configs={
                        file_type_codes.PCS_KNOWN_HOSTS: "foo-1",
                        file_type_codes.PCS_SETTINGS_CONF: "bar-1",
                    },
                ),
            )
        )
        requests.extend(
            self.cmd.on_response(
                fixture_apiv1_response(
                    node_label="NODE-2",
                    data=SyncConfigsDto(
                        cluster_name="test",
                        configs={
                            file_type_codes.PCS_KNOWN_HOSTS: "foo-2",
                            file_type_codes.PCS_SETTINGS_CONF: "bar-2",
                        },
                    ),
                )
            )
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertTrue(result.was_successful)
        self.assertEqual(
            result.config_files,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [
                    ConfigInfo("NODE-1", "foo-1"),
                    ConfigInfo("NODE-2", "foo-2"),
                ],
                file_type_codes.PCS_SETTINGS_CONF: [
                    ConfigInfo("NODE-1", "bar-1"),
                    ConfigInfo("NODE-2", "bar-2"),
                ],
            },
        )
        self.reporter.assert_reports([])

    def test_invalid_apiv1_format(self):
        requests = self.cmd.on_response(
            fixture_response(output="invalid", request=fixture_request_apiv1())
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports(
            [fixture.error(reports.codes.INVALID_RESPONSE_FORMAT, node="NODE")]
        )

    def test_invalid_apiv1_data(self):
        requests = self.cmd.on_response(fixture_apiv1_response(data="invalid"))
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports(
            [fixture.error(reports.codes.INVALID_RESPONSE_FORMAT, node="NODE")]
        )

    def test_incorrect_cluster_name(self):
        requests = self.cmd.on_response(
            fixture_apiv1_response(data=SyncConfigsDto("bad-name", {}))
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_REPORTS_UNEXPECTED_CLUSTER_NAME,
                    cluster_name="test",
                    context=reports.dto.ReportItemContextDto(node="NODE"),
                )
            ]
        )

    def test_communication_error(self):
        requests = self.cmd.on_response(
            fixture_apiv1_response(response_code=500)
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR,
                    node="NODE",
                    command="api/v1/cfgsync-get-configs/v1",
                    reason="HTTP error: 500",
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                )
            ]
        )

    def test_reports_from_response_no_errors(self):
        requests = self.cmd.on_response(
            fixture_apiv1_response(
                report_list=[
                    reports.ReportItem.warning(
                        reports.messages.NodeReportsUnexpectedClusterName(
                            "WARN"
                        )
                    ).to_dto()
                ],
                data=SyncConfigsDto(
                    cluster_name="test",
                    configs={
                        file_type_codes.PCS_KNOWN_HOSTS: "foo",
                        file_type_codes.PCS_SETTINGS_CONF: "bar",
                    },
                ),
            )
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(
            result.config_files,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [ConfigInfo("NODE", "foo")],
                file_type_codes.PCS_SETTINGS_CONF: [ConfigInfo("NODE", "bar")],
            },
        )
        self.reporter.assert_reports(
            [
                fixture.warn(
                    reports.codes.NODE_REPORTS_UNEXPECTED_CLUSTER_NAME,
                    cluster_name="WARN",
                    context=reports.dto.ReportItemContextDto(node="NODE"),
                )
            ]
        )

    def test_reports_from_response_errors(self):
        requests = self.cmd.on_response(
            fixture_apiv1_response(
                report_list=[
                    reports.ReportItem.error(
                        reports.messages.NodeReportsUnexpectedClusterName(
                            "ERROR"
                        )
                    ).to_dto()
                ],
                data=SyncConfigsDto(
                    cluster_name="test",
                    configs={
                        file_type_codes.PCS_KNOWN_HOSTS: "foo",
                        file_type_codes.PCS_SETTINGS_CONF: "bar",
                    },
                ),
            )
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_REPORTS_UNEXPECTED_CLUSTER_NAME,
                    cluster_name="ERROR",
                    context=reports.dto.ReportItemContextDto(node="NODE"),
                )
            ]
        )

    def test_apiv1_communication_error(self):
        requests = self.cmd.on_response(
            fixture_apiv1_response(
                com_status=COM_STATUS_ERROR, status_msg="Some error"
            )
        )
        result = self.cmd.on_complete()
        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node="NODE",
                    command="api/v1/cfgsync-get-configs/v1",
                    reason="Some error",
                )
            ]
        )


class GetConfigsFallbackResponseProcessing(TestCase):
    def setUp(self):
        self.reporter = MockLibraryReportProcessor()
        self.cmd = GetConfigs(self.reporter, "test")

    def test_empty_response(self):
        requests = self.cmd.on_response(fixture_fallback_response())
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports(
            [fixture.error(reports.codes.INVALID_RESPONSE_FORMAT, node="NODE")]
        )

    def test_single_response_with_files(self):
        requests = self.cmd.on_response(
            fixture_fallback_response(
                output=json.dumps(
                    {
                        "status": "ok",
                        "cluster_name": "test",
                        "configs": {
                            "known-hosts": {
                                "type": "file",
                                "text": "foo",
                            },
                            "pcs_settings.conf": {
                                "type": "file",
                                "text": "bar",
                            },
                        },
                    }
                )
            )
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(
            result.config_files,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [ConfigInfo("NODE", "foo")],
                file_type_codes.PCS_SETTINGS_CONF: [ConfigInfo("NODE", "bar")],
            },
        )
        self.reporter.assert_reports([])

    def test_multiple_responses_with_files(self):
        requests = self.cmd.on_response(
            fixture_fallback_response(
                node_label="NODE-1",
                output=json.dumps(
                    {
                        "status": "ok",
                        "cluster_name": "test",
                        "configs": {
                            "known-hosts": {
                                "type": "file",
                                "text": "foo-1",
                            },
                            "pcs_settings.conf": {
                                "type": "file",
                                "text": "bar-1",
                            },
                        },
                    }
                ),
            )
        )
        requests.extend(
            self.cmd.on_response(
                fixture_fallback_response(
                    node_label="NODE-2",
                    output=json.dumps(
                        {
                            "status": "ok",
                            "cluster_name": "test",
                            "configs": {
                                "known-hosts": {
                                    "type": "file",
                                    "text": "foo-2",
                                },
                                "pcs_settings.conf": {
                                    "type": "file",
                                    "text": "bar-2",
                                },
                            },
                        }
                    ),
                )
            )
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertTrue(result.was_successful)
        self.assertEqual(
            result.config_files,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [
                    ConfigInfo("NODE-1", "foo-1"),
                    ConfigInfo("NODE-2", "foo-2"),
                ],
                file_type_codes.PCS_SETTINGS_CONF: [
                    ConfigInfo("NODE-1", "bar-1"),
                    ConfigInfo("NODE-2", "bar-2"),
                ],
            },
        )
        self.reporter.assert_reports([])

    def test_communication_error(self):
        requests = self.cmd.on_response(
            fixture_fallback_response(response_code=500)
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR,
                    node="NODE",
                    command="remote/get_configs",
                    reason="HTTP error: 500",
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                )
            ]
        )

    def test_404(self):
        requests = self.cmd.on_response(
            fixture_fallback_response(response_code=404)
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNSUPPORTED_COMMAND,
                    node="NODE",
                    command="remote/get_configs",
                    reason="HTTP error: 404",
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                )
            ]
        )

    def test_not_in_cluster_status(self):
        requests = self.cmd.on_response(
            fixture_fallback_response(
                output=json.dumps({"status": "not_in_cluster"})
            )
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_REPORTS_UNEXPECTED_CLUSTER_NAME,
                    cluster_name="test",
                    context=reports.dto.ReportItemContextDto(node="NODE"),
                )
            ]
        )

    def test_wrong_cluster_name_status(self):
        requests = self.cmd.on_response(
            fixture_fallback_response(
                output=json.dumps({"status": "wrong_cluster_name"})
            )
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_REPORTS_UNEXPECTED_CLUSTER_NAME,
                    cluster_name="test",
                    context=reports.dto.ReportItemContextDto(node="NODE"),
                )
            ]
        )

    def test_wrong_cluster_name(self):
        requests = self.cmd.on_response(
            fixture_fallback_response(
                output=json.dumps({"status": "ok", "cluster_name": "bad-name"})
            )
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_REPORTS_UNEXPECTED_CLUSTER_NAME,
                    cluster_name="test",
                    context=reports.dto.ReportItemContextDto(node="NODE"),
                )
            ]
        )

    def test_unknown_file(self):
        requests = self.cmd.on_response(
            fixture_fallback_response(
                output=json.dumps(
                    {
                        "status": "ok",
                        "cluster_name": "test",
                        "configs": {
                            "foobar": {"type": "file", "text": "foo"},
                        },
                    }
                )
            )
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports([])

    def test_not_a_file(self):
        requests = self.cmd.on_response(
            fixture_fallback_response(
                output=json.dumps(
                    {
                        "status": "ok",
                        "cluster_name": "test",
                        "configs": {
                            "known-hosts": {
                                "type": "not-a-file",
                                "text": "foo",
                            },
                        },
                    }
                )
            )
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports([])

    def test_invalid_data(self):
        requests = self.cmd.on_response(
            fixture_fallback_response(
                # the 'configs' key is missing
                output=json.dumps({"status": "ok", "cluster_name": "test"})
            )
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(result.config_files, {})
        self.reporter.assert_reports(
            [fixture.error(reports.codes.INVALID_RESPONSE_FORMAT, node="NODE")]
        )


class GetConfigsResponseProcessing(TestCase):
    def setUp(self):
        self.reporter = MockLibraryReportProcessor()
        self.cmd = GetConfigs(self.reporter, "test")

    def test_multiple_responses_mixed_apiv1_fallback(self):
        requests = self.cmd.on_response(
            fixture_apiv1_response(
                node_label="NODE-1",
                data=SyncConfigsDto(
                    cluster_name="test",
                    configs={
                        file_type_codes.PCS_KNOWN_HOSTS: "foo-1",
                        file_type_codes.PCS_SETTINGS_CONF: "bar-1",
                    },
                ),
            )
        )
        requests.extend(
            self.cmd.on_response(
                fixture_fallback_response(
                    node_label="NODE-2",
                    output=json.dumps(
                        {
                            "status": "ok",
                            "cluster_name": "test",
                            "configs": {
                                "known-hosts": {
                                    "type": "file",
                                    "text": "foo-2",
                                },
                                "pcs_settings.conf": {
                                    "type": "file",
                                    "text": "bar-2",
                                },
                            },
                        }
                    ),
                )
            )
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertTrue(result.was_successful)
        self.assertEqual(
            result.config_files,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [
                    ConfigInfo("NODE-1", "foo-1"),
                    ConfigInfo("NODE-2", "foo-2"),
                ],
                file_type_codes.PCS_SETTINGS_CONF: [
                    ConfigInfo("NODE-1", "bar-1"),
                    ConfigInfo("NODE-2", "bar-2"),
                ],
            },
        )
        self.reporter.assert_reports([])

    def test_multiple_responses_one_failed(self):
        requests = self.cmd.on_response(
            fixture_apiv1_response(
                node_label="NODE-1",
                data=SyncConfigsDto(
                    cluster_name="test",
                    configs={
                        file_type_codes.PCS_KNOWN_HOSTS: "foo-1",
                        file_type_codes.PCS_SETTINGS_CONF: "bar-1",
                    },
                ),
            )
        )
        requests.extend(
            self.cmd.on_response(
                fixture_apiv1_response(response_code=500, node_label="NODE-2")
            )
        )
        result = self.cmd.on_complete()

        self.assertEqual(requests, [])
        self.assertFalse(result.was_successful)
        self.assertEqual(
            result.config_files,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [
                    ConfigInfo("NODE-1", "foo-1")
                ],
                file_type_codes.PCS_SETTINGS_CONF: [
                    ConfigInfo("NODE-1", "bar-1")
                ],
            },
        )
        self.reporter.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR,
                    node="NODE-2",
                    command="api/v1/cfgsync-get-configs/v1",
                    reason="HTTP error: 500",
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                )
            ]
        )
