import os
from unittest import TestCase, mock

from pcs.cli import client
from pcs.cli.common.errors import CmdLineInputError
from pcs.common import reports
from pcs.common.file_type_codes import PCS_KNOWN_HOSTS
from pcs.common.host import Destination, PcsKnownHost
from pcs.lib.host.config.exporter import Exporter as KnownHostsExporter
from pcs.lib.host.config.types import KnownHosts

from pcs_test.tools import fixture
from pcs_test.tools.command_env.calls import CallListBuilder, Queue
from pcs_test.tools.command_env.mock_node_communicator import (
    NodeCommunicator,
    place_multinode_call,
)
from pcs_test.tools.command_env.mock_raw_file import (
    RawFileExistsCall,
    RawFileReadCall,
    RawFileWriteCall,
    get_raw_file_mock,
)
from pcs_test.tools.custom_mock import MockLibraryReportProcessor
from pcs_test.tools.misc import dict_to_modifiers


def fixture_known_hosts_file_content(
    data_version, hosts: dict[str, PcsKnownHost]
) -> str:
    return KnownHostsExporter.export(
        KnownHosts(
            format_version=1, data_version=data_version, known_hosts=hosts
        )
    ).decode("utf-8")


class LocalAuthCmd(TestCase):
    def setUp(self):
        self.path = os.path.expanduser("~/.pcs/known-hosts")

        self.mock_print_to_stderr = mock.patch(
            "pcs.cli.reports.output.print_to_stderr"
        ).start()
        self.mock_geteuid = mock.patch(
            "pcs.cli.client.os.geteuid", return_value=123
        ).start()
        self.mock_get_user_and_pass = mock.patch(
            "pcs.utils.get_user_and_pass",
            return_value=("hacluster", "password"),
        ).start()
        self.mock_report_processor = (
            mock.patch(
                "pcs.cli.client.ReportProcessorToConsole",
                return_value=MockLibraryReportProcessor(),
            )
            .start()
            .return_value
        )
        self.mock_mkdir = mock.patch("pcs.cli.client.os.mkdir").start()
        self.mock_chmod = mock.patch("pcs.cli.client.os.chmod").start()

        self.addCleanup(mock.patch.stopall)

    def fixture_auth_call(self, successful: bool = True):
        calls = CallListBuilder()
        place_multinode_call(
            calls,
            action="remote/auth",
            node_labels=["localhost"],
            output="TOKEN" if successful else "",
            param_list=[("username", "hacluster"), ("password", "password")],
            name="auth",
        )

        mock.patch(
            "pcs.cli.client._get_node_communicator",
            return_value=NodeCommunicator(Queue(calls)),
        ).start()

    def test_superuser(self):
        self.mock_geteuid.return_value = 0

        with self.assertRaises(SystemExit) as cm:
            client.local_auth_cmd(None, [], dict_to_modifiers({}))

        self.assertEqual(cm.exception.code, 1)
        self.mock_print_to_stderr.assert_called_once()
        self.mock_get_user_and_pass.assert_not_called()
        self.mock_mkdir.assert_not_called()
        self.mock_chmod.assert_not_called()

    def test_too_many_args(self):
        with self.assertRaises(CmdLineInputError):
            client.local_auth_cmd(None, [123, 456], dict_to_modifiers({}))
        self.mock_print_to_stderr.assert_not_called()
        self.mock_get_user_and_pass.assert_not_called()
        self.mock_mkdir.assert_not_called()
        self.mock_chmod.assert_not_called()

    def test_arg_not_a_port_number(self):
        with self.assertRaises(CmdLineInputError):
            client.local_auth_cmd(None, ["abc"], dict_to_modifiers({}))
        self.mock_print_to_stderr.assert_not_called()
        self.mock_get_user_and_pass.assert_not_called()
        self.mock_mkdir.assert_not_called()
        self.mock_chmod.assert_not_called()

    def test_bad_credentials(self):
        self.fixture_auth_call(False)

        with self.assertRaises(SystemExit) as cm:
            client.local_auth_cmd(None, [], dict_to_modifiers({}))
        self.assertEqual(cm.exception.code, 1)

        self.mock_report_processor.assert_reports(
            [
                fixture.error(
                    reports.codes.INCORRECT_CREDENTIALS,
                    context=reports.dto.ReportItemContextDto("localhost"),
                )
            ]
        )
        self.mock_get_user_and_pass.assert_called_once_with()
        self.mock_print_to_stderr.assert_not_called()
        self.mock_mkdir.assert_not_called()
        self.mock_chmod.assert_not_called()

    def test_success(self):
        self.fixture_auth_call()
        calls = CallListBuilder()
        calls.place(
            "exists",
            RawFileExistsCall(file_type_code=PCS_KNOWN_HOSTS, path=self.path),
        )
        calls.place(
            "read",
            RawFileReadCall(
                PCS_KNOWN_HOSTS,
                self.path,
                content=fixture_known_hosts_file_content(1, {}),
            ),
        )
        calls.place(
            "write",
            RawFileWriteCall(
                PCS_KNOWN_HOSTS,
                self.path,
                file_data=fixture_known_hosts_file_content(
                    1,
                    {
                        "localhost": PcsKnownHost(
                            "localhost",
                            "TOKEN",
                            [Destination("localhost", 2224)],
                        )
                    },
                ).encode("utf-8"),
                can_overwrite=True,
            ),
        )

        mock.patch(
            "pcs.cli.client.RawFile", new=get_raw_file_mock(Queue(calls))
        ).start()

        client.local_auth_cmd(None, [], dict_to_modifiers({}))

        self.mock_report_processor.assert_reports(
            [
                fixture.info(
                    reports.codes.AUTHORIZATION_SUCCESSFUL,
                    context=reports.dto.ReportItemContextDto("localhost"),
                )
            ]
        )
        self.mock_print_to_stderr.assert_not_called()
        self.mock_get_user_and_pass.assert_called_once_with()
        self.mock_mkdir.assert_called_once_with(
            os.path.expanduser("~/.pcs"), 0o700
        )
        self.mock_chmod.assert_called_once_with(
            os.path.expanduser("~/.pcs"), 0o700
        )

    def test_file_no_existed(self):
        self.fixture_auth_call()
        calls = CallListBuilder()
        calls.place(
            "exists",
            RawFileExistsCall(
                file_type_code=PCS_KNOWN_HOSTS, path=self.path, exists=False
            ),
        )
        calls.place(
            "write",
            RawFileWriteCall(
                PCS_KNOWN_HOSTS,
                self.path,
                file_data=fixture_known_hosts_file_content(
                    1,
                    {
                        "localhost": PcsKnownHost(
                            "localhost",
                            "TOKEN",
                            [Destination("localhost", 2224)],
                        )
                    },
                ).encode("utf-8"),
                can_overwrite=True,
            ),
        )

        mock.patch(
            "pcs.cli.client.RawFile", new=get_raw_file_mock(Queue(calls))
        ).start()

        client.local_auth_cmd(None, [], dict_to_modifiers({}))

        self.mock_report_processor.assert_reports(
            [
                fixture.info(
                    reports.codes.AUTHORIZATION_SUCCESSFUL,
                    context=reports.dto.ReportItemContextDto("localhost"),
                )
            ]
        )
        self.mock_print_to_stderr.assert_not_called()
        self.mock_get_user_and_pass.assert_called_once_with()
        self.mock_mkdir.assert_called_once_with(
            os.path.expanduser("~/.pcs"), 0o700
        )
        self.mock_chmod.assert_called_once_with(
            os.path.expanduser("~/.pcs"), 0o700
        )

    def test_file_read_error(self):
        self.fixture_auth_call()
        calls = CallListBuilder()
        calls.place(
            "exists",
            RawFileExistsCall(file_type_code=PCS_KNOWN_HOSTS, path=self.path),
        )
        calls.place(
            "read",
            RawFileReadCall(PCS_KNOWN_HOSTS, self.path, exception_msg="Error"),
        )

        mock.patch(
            "pcs.cli.client.RawFile", new=get_raw_file_mock(Queue(calls))
        ).start()

        with self.assertRaises(SystemExit) as cm:
            client.local_auth_cmd(None, [], dict_to_modifiers({}))
        self.assertEqual(cm.exception.code, 1)

        self.mock_report_processor.assert_reports(
            [
                fixture.info(
                    reports.codes.AUTHORIZATION_SUCCESSFUL,
                    context=reports.dto.ReportItemContextDto("localhost"),
                ),
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    operation="read",
                    reason="Error",
                    file_path=self.path,
                ),
            ]
        )
        self.mock_print_to_stderr.assert_not_called()
        self.mock_get_user_and_pass.assert_called_once_with()
        self.mock_mkdir.assert_not_called()
        self.mock_chmod.assert_not_called()

    def test_file_write_error(self):
        self.fixture_auth_call()
        calls = CallListBuilder()
        calls.place(
            "exists",
            RawFileExistsCall(file_type_code=PCS_KNOWN_HOSTS, path=self.path),
        )
        calls.place(
            "read",
            RawFileReadCall(
                PCS_KNOWN_HOSTS,
                self.path,
                content=fixture_known_hosts_file_content(1, {}),
            ),
        )
        calls.place(
            "write",
            RawFileWriteCall(
                PCS_KNOWN_HOSTS,
                self.path,
                file_data=fixture_known_hosts_file_content(
                    1,
                    {
                        "localhost": PcsKnownHost(
                            "localhost",
                            "TOKEN",
                            [Destination("localhost", 2224)],
                        )
                    },
                ).encode("utf-8"),
                can_overwrite=True,
                exception_msg="Error",
            ),
        )

        mock.patch(
            "pcs.cli.client.RawFile", new=get_raw_file_mock(Queue(calls))
        ).start()

        with self.assertRaises(SystemExit) as cm:
            client.local_auth_cmd(None, [], dict_to_modifiers({}))
        self.assertEqual(cm.exception.code, 1)

        self.mock_report_processor.assert_reports(
            [
                fixture.info(
                    reports.codes.AUTHORIZATION_SUCCESSFUL,
                    context=reports.dto.ReportItemContextDto("localhost"),
                ),
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    operation="write",
                    reason="Error",
                    file_path=self.path,
                ),
            ]
        )
        self.mock_print_to_stderr.assert_not_called()
        self.mock_get_user_and_pass.assert_called_once_with()
        self.mock_mkdir.assert_called_once_with(
            os.path.expanduser("~/.pcs"), 0o700
        )
        self.mock_chmod.assert_called_once_with(
            os.path.expanduser("~/.pcs"), 0o700
        )

    def test_cannot_create_folder(self):
        self.mock_mkdir.side_effect = FileNotFoundError()
        self.fixture_auth_call()
        calls = CallListBuilder()
        calls.place(
            "exists",
            RawFileExistsCall(file_type_code=PCS_KNOWN_HOSTS, path=self.path),
        )
        calls.place(
            "read",
            RawFileReadCall(
                PCS_KNOWN_HOSTS,
                self.path,
                content=fixture_known_hosts_file_content(1, {}),
            ),
        )

        mock.patch(
            "pcs.cli.client.RawFile", new=get_raw_file_mock(Queue(calls))
        ).start()

        with self.assertRaises(SystemExit) as cm:
            client.local_auth_cmd(None, [], dict_to_modifiers({}))

        self.mock_report_processor.assert_reports(
            [
                fixture.info(
                    reports.codes.AUTHORIZATION_SUCCESSFUL,
                    context=reports.dto.ReportItemContextDto("localhost"),
                )
            ]
        )
        self.assertEqual(cm.exception.code, 1)
        self.mock_print_to_stderr.assert_called_once_with(
            "Error: FileNotFoundError"
        )
        self.mock_get_user_and_pass.assert_called_once_with()
        self.mock_mkdir.assert_called_once_with(
            os.path.expanduser("~/.pcs"), 0o700
        )
        self.mock_chmod.assert_not_called()

    def test_folder_already_exists(self):
        self.mock_mkdir.side_effect = FileExistsError()
        self.fixture_auth_call()
        calls = CallListBuilder()
        calls.place(
            "exists",
            RawFileExistsCall(file_type_code=PCS_KNOWN_HOSTS, path=self.path),
        )
        calls.place(
            "read",
            RawFileReadCall(
                PCS_KNOWN_HOSTS,
                self.path,
                content=fixture_known_hosts_file_content(1, {}),
            ),
        )
        calls.place(
            "write",
            RawFileWriteCall(
                PCS_KNOWN_HOSTS,
                self.path,
                file_data=fixture_known_hosts_file_content(
                    1,
                    {
                        "localhost": PcsKnownHost(
                            "localhost",
                            "TOKEN",
                            [Destination("localhost", 2224)],
                        )
                    },
                ).encode("utf-8"),
                can_overwrite=True,
            ),
        )

        mock.patch(
            "pcs.cli.client.RawFile", new=get_raw_file_mock(Queue(calls))
        ).start()

        client.local_auth_cmd(None, [], dict_to_modifiers({}))

        self.mock_report_processor.assert_reports(
            [
                fixture.info(
                    reports.codes.AUTHORIZATION_SUCCESSFUL,
                    context=reports.dto.ReportItemContextDto("localhost"),
                )
            ]
        )
        self.mock_print_to_stderr.assert_not_called()
        self.mock_get_user_and_pass.assert_called_once_with()
        self.mock_mkdir.assert_called_once_with(
            os.path.expanduser("~/.pcs"), 0o700
        )
        self.mock_chmod.assert_called_once_with(
            os.path.expanduser("~/.pcs"), 0o700
        )
