from hashlib import md5
from unittest import TestCase, mock

from pcs.common.pacemaker.cibsecret import (
    CibResourceSecretDto,
    CibResourceSecretListDto,
)
from pcs.common.reports import codes as report_codes
from pcs.common.reports.const import (
    CIB_SECRET_REASON_BAD_CHECKSUM,
    CIB_SECRET_REASON_CANNOT_READ_CHECKSUM_FILE,
    CIB_SECRET_REASON_CANNOT_READ_VALUE_FILE,
)
from pcs.lib.commands import resource

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.custom_mock import (
    CibResourceSecretMock,
    CibResourceSecretMockSpec,
)


@mock.patch("pcs.lib.pacemaker.live.Path.read_text", autospec=True)
class GetCibsecrets(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.maxDiff = None

    def command(self, queries):
        return resource.get_cibsecrets(self.env_assist.get_env(), queries)

    def checksum(self, value):
        return md5(value.encode(), usedforsecurity=False).hexdigest()

    def test_empty_queries(self, mock_read_text):
        queries = []
        self.assertEqual(
            self.command(queries), CibResourceSecretListDto(resource_secrets=[])
        )
        mock_read_text.assert_not_called()

    def test_get_multiple_secrets_success(self, mock_read_text):
        queries = [
            ("R1", "secret1"),
            ("R2", "secret3"),
            ("R2", "secret2"),
            ("R2", "secret3"),
            ("R1", "secret4"),
        ]
        secrets_mock = CibResourceSecretMock(
            [
                CibResourceSecretMockSpec(
                    "R1", "secret1", "secret1_value", None
                ),
                CibResourceSecretMockSpec(
                    "R2", "secret3", "secret3_value", None
                ),
                CibResourceSecretMockSpec(
                    "R2", "secret2", "secret2_value", None
                ),
                CibResourceSecretMockSpec(
                    "R1", "secret4", "secret4_value", None
                ),
            ]
        )
        mock_read_text.side_effect = secrets_mock.get_read_text_side_effect()
        self.assertEqual(
            self.command(queries),
            CibResourceSecretListDto(
                resource_secrets=[
                    CibResourceSecretDto(
                        resource_id="R1", name="secret1", value="secret1_value"
                    ),
                    CibResourceSecretDto(
                        resource_id="R2", name="secret3", value="secret3_value"
                    ),
                    CibResourceSecretDto(
                        resource_id="R2", name="secret2", value="secret2_value"
                    ),
                    CibResourceSecretDto(
                        resource_id="R1", name="secret4", value="secret4_value"
                    ),
                ]
            ),
        )
        expected_calls = secrets_mock.get_read_text_calls()
        mock_read_text.assert_has_calls(expected_calls)
        self.assertEqual(mock_read_text.call_count, len(expected_calls))

    def test_file_errors(self, mock_read_text):
        queries = [
            ("R1", "ok_secret"),
            ("R1", "value_not_found"),
            ("R1", "value_permission_error"),
            ("R1", "value_os_error"),
            ("R2", "ok_secret2"),
            ("R2", "checksum_not_found"),
            ("R2", "checksum_permission_error"),
            ("R2", "checksum_os_error"),
            ("R2", "checksum_bad"),
        ]
        secrets_mock = CibResourceSecretMock(
            [
                CibResourceSecretMockSpec(
                    "R1", "ok_secret", "ok_secret_value", None
                ),
                CibResourceSecretMockSpec(
                    "R1", "value_not_found", FileNotFoundError(), None
                ),
                CibResourceSecretMockSpec(
                    "R1", "value_permission_error", PermissionError(), None
                ),
                CibResourceSecretMockSpec(
                    "R1", "value_os_error", OSError(), None
                ),
                CibResourceSecretMockSpec(
                    "R2", "ok_secret2", "ok_secret2_value", None
                ),
                CibResourceSecretMockSpec(
                    "R2", "checksum_not_found", "value", FileNotFoundError()
                ),
                CibResourceSecretMockSpec(
                    "R2",
                    "checksum_permission_error",
                    "value",
                    PermissionError(),
                ),
                CibResourceSecretMockSpec(
                    "R2", "checksum_os_error", "value", OSError()
                ),
                CibResourceSecretMockSpec(
                    "R2", "checksum_bad", "value", "bad_checksum"
                ),
            ]
        )
        mock_read_text.side_effect = secrets_mock.get_read_text_side_effect()
        self.assertEqual(
            self.command(queries),
            CibResourceSecretListDto(
                resource_secrets=[
                    CibResourceSecretDto(
                        resource_id="R1",
                        name="ok_secret",
                        value="ok_secret_value",
                    ),
                    CibResourceSecretDto(
                        resource_id="R2",
                        name="ok_secret2",
                        value="ok_secret2_value",
                    ),
                ]
            ),
        )
        expected_calls = secrets_mock.get_read_text_calls()
        mock_read_text.assert_has_calls(expected_calls)
        self.assertEqual(mock_read_text.call_count, len(expected_calls))
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.CIB_RESOURCE_SECRET_UNABLE_TO_GET,
                    resource_id="R1",
                    secret_name="value_not_found",
                    reason=CIB_SECRET_REASON_CANNOT_READ_VALUE_FILE,
                ),
                fixture.warn(
                    report_codes.CIB_RESOURCE_SECRET_UNABLE_TO_GET,
                    resource_id="R1",
                    secret_name="value_os_error",
                    reason=CIB_SECRET_REASON_CANNOT_READ_VALUE_FILE,
                ),
                fixture.warn(
                    report_codes.CIB_RESOURCE_SECRET_UNABLE_TO_GET,
                    resource_id="R1",
                    secret_name="value_permission_error",
                    reason=CIB_SECRET_REASON_CANNOT_READ_VALUE_FILE,
                ),
                fixture.warn(
                    report_codes.CIB_RESOURCE_SECRET_UNABLE_TO_GET,
                    resource_id="R2",
                    secret_name="checksum_not_found",
                    reason=CIB_SECRET_REASON_CANNOT_READ_CHECKSUM_FILE,
                ),
                fixture.warn(
                    report_codes.CIB_RESOURCE_SECRET_UNABLE_TO_GET,
                    resource_id="R2",
                    secret_name="checksum_os_error",
                    reason=CIB_SECRET_REASON_CANNOT_READ_CHECKSUM_FILE,
                ),
                fixture.warn(
                    report_codes.CIB_RESOURCE_SECRET_UNABLE_TO_GET,
                    resource_id="R2",
                    secret_name="checksum_permission_error",
                    reason=CIB_SECRET_REASON_CANNOT_READ_CHECKSUM_FILE,
                ),
                fixture.warn(
                    report_codes.CIB_RESOURCE_SECRET_UNABLE_TO_GET,
                    resource_id="R2",
                    secret_name="checksum_bad",
                    reason=CIB_SECRET_REASON_BAD_CHECKSUM,
                ),
            ]
        )

    def test_files_with_trailig_whitespace(self, mock_read_text):
        queries = [
            ("R1", "whitespace1"),
            ("R1", "whitespace2"),
        ]
        secrets_mock = CibResourceSecretMock(
            [
                CibResourceSecretMockSpec(
                    "R1",
                    "whitespace1",
                    "whitespace1_value \t\n\r\v\f",
                    self.checksum("whitespace1_value"),
                ),
                CibResourceSecretMockSpec(
                    "R1",
                    "whitespace2",
                    "whitespace2_value",
                    f"{self.checksum('whitespace2_value')} \t\n\r\v\f",
                ),
            ]
        )
        mock_read_text.side_effect = secrets_mock.get_read_text_side_effect()
        self.assertEqual(
            self.command(queries),
            CibResourceSecretListDto(
                resource_secrets=[
                    CibResourceSecretDto(
                        resource_id="R1",
                        name="whitespace1",
                        value="whitespace1_value",
                    ),
                    CibResourceSecretDto(
                        resource_id="R1",
                        name="whitespace2",
                        value="whitespace2_value",
                    ),
                ]
            ),
        )
        expected_calls = secrets_mock.get_read_text_calls()
        mock_read_text.assert_has_calls(expected_calls)
        self.assertEqual(mock_read_text.call_count, len(expected_calls))

    def test_traversal_path(self, mock_read_text):
        queries = [
            (".././secrets/R1", "../R8/secret1"),
            ("../secrets/R1", "../R8/secret1"),
            ("../../../../../etc/", "passwd"),
            ("R1", "../../../../../../etc/passwd"),
        ]
        self.assertEqual(
            self.command(queries), CibResourceSecretListDto(resource_secrets=[])
        )
        mock_read_text.assert_not_called()
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.CIB_RESOURCE_SECRET_UNABLE_TO_GET,
                    resource_id=".././secrets/R1",
                    secret_name="../R8/secret1",
                    reason=CIB_SECRET_REASON_CANNOT_READ_VALUE_FILE,
                ),
                fixture.warn(
                    report_codes.CIB_RESOURCE_SECRET_UNABLE_TO_GET,
                    resource_id="../secrets/R1",
                    secret_name="../R8/secret1",
                    reason=CIB_SECRET_REASON_CANNOT_READ_VALUE_FILE,
                ),
                fixture.warn(
                    report_codes.CIB_RESOURCE_SECRET_UNABLE_TO_GET,
                    resource_id="../../../../../etc/",
                    secret_name="passwd",
                    reason=CIB_SECRET_REASON_CANNOT_READ_VALUE_FILE,
                ),
                fixture.warn(
                    report_codes.CIB_RESOURCE_SECRET_UNABLE_TO_GET,
                    resource_id="R1",
                    secret_name="../../../../../../etc/passwd",
                    reason=CIB_SECRET_REASON_CANNOT_READ_VALUE_FILE,
                ),
            ]
        )
