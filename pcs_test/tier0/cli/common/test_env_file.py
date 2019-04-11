from unittest import mock, TestCase

from pcs_test.tools.misc import create_patcher, create_setup_patch_mixin

from pcs.cli.common import env_file
from pcs.common import report_codes
from pcs.lib.errors import ReportItem

patch_env_file = create_patcher(env_file)
SetupPatchMixin = create_setup_patch_mixin(patch_env_file)

FILE_PATH = "/path/to/local/file"

class Write(TestCase, SetupPatchMixin):
    def setUp(self):
        self.mock_open = mock.mock_open()
        self.mock_error = self.setup_patch("console_report.error")

    def assert_params_causes_calls(self, env_file_dict, calls, path=FILE_PATH):
        with patch_env_file("open", self.mock_open, create=True):
            env_file.write(env_file_dict, path)
        self.assertEqual(self.mock_open.mock_calls, calls)

    def test_sucessfully_write(self):
        self.assert_params_causes_calls(
            {"content": "filecontent"},
            [
                mock.call(FILE_PATH, "w"),
                mock.call().write("filecontent"),
                mock.call().close(),
            ]
        )

    def test_sucessfully_write_binary(self):
        self.assert_params_causes_calls(
            {"content": "filecontent", "is_binary": True},
            [
                mock.call(FILE_PATH, "wb"),
                mock.call().write("filecontent"),
                mock.call().close(),
            ]
        )

    def test_exit_when_cannot_open_file(self):
        self.mock_open.side_effect = EnvironmentError()
        self.mock_error.side_effect = SystemExit()
        self.assertRaises(
            SystemExit,
            lambda: env_file.write({"content": "filecontent"}, FILE_PATH)
        )

class Read(TestCase, SetupPatchMixin):
    def setUp(self):
        self.is_file = self.setup_patch('os.path.isfile')
        self.mock_open = mock.mock_open(read_data='filecontent')
        self.mock_error = self.setup_patch("console_report.error")

    def assert_returns_content(self, content, is_file):
        self.is_file.return_value = is_file
        with patch_env_file("open", self.mock_open, create=True):
            self.assertEqual(
                content,
                env_file.read(FILE_PATH)
            )

    def test_successfully_read(self):
        self.assert_returns_content({"content": "filecontent"}, is_file=True)

    def test_successfully_return_empty_content(self):
        self.assert_returns_content({"content": None}, is_file=False)

    def test_exit_when_cannot_open_file(self):
        self.mock_open.side_effect = EnvironmentError()
        self.mock_error.side_effect = SystemExit()
        self.assertRaises(SystemExit, lambda: env_file.read(FILE_PATH))

class ProcessNoExistingFileExpectation(TestCase, SetupPatchMixin):
    def setUp(self):
        self.exists = self.setup_patch('os.path.exists')
        self.mock_error = self.setup_patch("console_report.error")

    def run_process(
        self, no_existing_file_expected, file_exists, overwrite=False
    ):
        self.exists.return_value = file_exists
        env_file.process_no_existing_file_expectation(
            "role",
            {
                "no_existing_file_expected": no_existing_file_expected,
                "can_overwrite_existing_file": overwrite,
            },
            FILE_PATH
        )

    def test_do_nothing_when_expectation_does_not_conflict(self):
        self.run_process(no_existing_file_expected=False, file_exists=True)
        self.run_process(no_existing_file_expected=False, file_exists=False)
        self.run_process(no_existing_file_expected=True, file_exists=False)

    def test_overwrite_permission_produce_console_warning(self):
        warn = self.setup_patch("console_report.warn")
        self.run_process(
            no_existing_file_expected=True,
            file_exists=True,
            overwrite=True
        )
        warn.assert_called_once_with("role /path/to/local/file already exists")

    def test_non_overwrittable_conflict_exits(self):
        self.mock_error.side_effect = SystemExit()
        self.assertRaises(
            SystemExit,
            lambda:
            self.run_process(no_existing_file_expected=True, file_exists=True)
        )

class ReportMissing(TestCase):
    @patch_env_file("console_report.error")
    def test_report_to_console(self, error):
        # pylint: disable=no-self-use
        env_file.report_missing("role", "path")
        error.assert_called_once_with("role 'path' does not exist")

class IsMissingReport(TestCase):
    def test_regcognize_missing_report(self):
        self.assertTrue(env_file.is_missing_report(
            ReportItem.error(
                report_codes.FILE_DOES_NOT_EXIST,
                info={"file_role": "role"}
            ),
            "role"
        ))
