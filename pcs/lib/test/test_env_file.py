from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.pcs_unittest import TestCase

from pcs.common import report_codes
from pcs.lib import env_file
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.misc import create_patcher
from pcs.test.tools.assertions import(
    assert_raise_library_error,
    assert_report_item_list_equal
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.pcs_unittest import mock


patch_env_file = create_patcher(env_file)

FILE_PATH = "/path/to.file"
MISSING_PATH = "/no/existing/file.path"
CONF_PATH = "/etc/booth/some-name.conf"

class GhostFileInit(TestCase):
    def test_is_not_binary_default(self):
        ghost_file = env_file.GhostFile("some role", content=None)
        self.assertFalse(ghost_file.export()["is_binary"])

    def test_accepts_is_binary_attribute(self):
        ghost_file = env_file.GhostFile(
            "some role",
            content=None,
            is_binary=True
        )
        self.assertTrue(ghost_file.export()["is_binary"])

class GhostFileReadTest(TestCase):
    def test_raises_when_trying_read_nonexistent_file(self):
        assert_raise_library_error(
            lambda: env_file.GhostFile("some role", content=None).read(),
            (
                severities.ERROR,
                report_codes.FILE_DOES_NOT_EXIST,
                {
                    "file_role": "some role",
                }
            ),
        )

class GhostFileExists(TestCase):
    def test_return_true_if_file_exists(self):
        self.assertTrue(env_file.GhostFile("some_role", "any content").exists)

    def test_return_False_if_file_exists(self):
        self.assertFalse(env_file.GhostFile("some_role").exists)

    def test_return_True_after_write(self):
        ghost_file = env_file.GhostFile("some_role")
        ghost_file.write("any content")
        self.assertTrue(ghost_file.exists)

class RealFileExists(TestCase):
    @patch_env_file("os.path.exists", return_value=True)
    def test_return_true_if_file_exists(self, exists):
        self.assertTrue(env_file.RealFile("some role", FILE_PATH).exists)

    @patch_env_file("os.path.exists", return_value=False)
    def test_return_false_if_file_does_not_exist(self, exists):
        self.assertFalse(env_file.RealFile("some role", FILE_PATH).exists)

@patch_env_file("os.path.exists", return_value=True)
class RealFileAssertNoConflictWithExistingTest(TestCase):
    def check(self, report_processor, can_overwrite_existing=False):
        real_file = env_file.RealFile("some role", CONF_PATH)
        real_file.assert_no_conflict_with_existing(
            report_processor,
            can_overwrite_existing
        )

    def test_success_when_config_not_exists(self, mock_exists):
        mock_exists.return_value = False
        report_processor=MockLibraryReportProcessor()
        self.check(report_processor)
        assert_report_item_list_equal(report_processor.report_item_list, [])

    def test_raises_when_config_exists_and_overwrite_not_allowed(self, mock_ex):
        assert_raise_library_error(
            lambda: self.check(MockLibraryReportProcessor()),
            (
                severities.ERROR,
                report_codes.FILE_ALREADY_EXISTS,
                {
                    "file_path": CONF_PATH
                },
                report_codes.FORCE_FILE_OVERWRITE,
            ),
        )

    def test_warn_when_config_exists_and_overwrite_allowed(self, mock_exists):
        report_processor=MockLibraryReportProcessor()
        self.check(report_processor, can_overwrite_existing=True)
        assert_report_item_list_equal(report_processor.report_item_list, [(
            severities.WARNING,
            report_codes.FILE_ALREADY_EXISTS,
            {
                "file_path": CONF_PATH
            },
        )])

class RealFileWriteTest(TestCase):
    def test_success_write_content_to_path(self):
        mock_open = mock.mock_open()
        mock_file_operation = mock.Mock()
        with patch_env_file("open", mock_open, create=True):
            env_file.RealFile("some role", CONF_PATH).write(
                "config content",
                file_operation=mock_file_operation
            )
            mock_open.assert_called_once_with(CONF_PATH, "w")
            mock_open().write.assert_called_once_with("config content")
            mock_file_operation.assert_called_once_with(CONF_PATH)

    def test_success_binary(self):
        mock_open = mock.mock_open()
        mock_file_operation = mock.Mock()
        with patch_env_file("open", mock_open, create=True):
            env_file.RealFile("some role", CONF_PATH, is_binary=True).write(
                "config content".encode("utf-8"),
                file_operation=mock_file_operation,
            )
            mock_open.assert_called_once_with(CONF_PATH, "wb")
            mock_open().write.assert_called_once_with(
                "config content".encode("utf-8")
            )
            mock_file_operation.assert_called_once_with(CONF_PATH)

    def test_raises_when_could_not_write(self):
        assert_raise_library_error(
            lambda:
            env_file.RealFile("some role", MISSING_PATH).write(["content"]),
            (
                severities.ERROR,
                report_codes.FILE_IO_ERROR,
                {
                    "reason":
                        "No such file or directory: '{0}'".format(MISSING_PATH)
                    ,
                }
            )
        )

class RealFileReadTest(TestCase):
    def assert_read_in_correct_mode(self, real_file, mode):
        mock_open = mock.mock_open()
        with patch_env_file("open", mock_open, create=True):
            mock_open().read.return_value = "test booth\nconfig"
            self.assertEqual("test booth\nconfig", real_file.read())
        mock_open.assert_has_calls([mock.call(FILE_PATH, mode)])

    def test_success_read_content_from_file(self):
        self.assert_read_in_correct_mode(
            env_file.RealFile("some role", FILE_PATH, is_binary=False),
            mode="r"
        )

    def test_success_read_content_from_binary_file(self):
        self.assert_read_in_correct_mode(
            env_file.RealFile("some role", FILE_PATH, is_binary=True),
            mode="rb"
        )

    def test_raises_when_could_not_read(self):
        assert_raise_library_error(
            lambda: env_file.RealFile("some role", MISSING_PATH).read(),
            (
                severities.ERROR,
                report_codes.FILE_IO_ERROR,
                {
                    "reason":
                        "No such file or directory: '{0}'".format(MISSING_PATH)
                    ,
                }
            )
        )

class RealFileRemoveTest(TestCase):
    @patch_env_file("os.remove")
    @patch_env_file("os.path.exists", return_value=True)
    def test_success_remove_file(self, _, mock_remove):
        env_file.RealFile("some role", FILE_PATH).remove()
        mock_remove.assert_called_once_with(FILE_PATH)

    @patch_env_file(
        "os.remove",
        side_effect=EnvironmentError(1, "mock remove failed", FILE_PATH)
    )
    @patch_env_file("os.path.exists", return_value=True)
    def test_raise_library_error_when_remove_failed(self, _, dummy):
        assert_raise_library_error(
            lambda: env_file.RealFile("some role", FILE_PATH).remove(),
            (
                severities.ERROR,
                report_codes.FILE_IO_ERROR,
                {
                    'reason': "mock remove failed: '/path/to.file'",
                    'file_role': 'some role',
                    'file_path': '/path/to.file'
                }
            )
        )

    @patch_env_file("os.path.exists", return_value=False)
    def test_existence_is_required(self, _):
        assert_raise_library_error(
            lambda: env_file.RealFile("some role", FILE_PATH).remove(),
            (
                severities.ERROR,
                report_codes.FILE_IO_ERROR,
                {
                    'reason': "File does not exist",
                    'file_role': 'some role',
                    'file_path': '/path/to.file'
                }
            )
        )

    @patch_env_file("os.path.exists", return_value=False)
    def test_noexistent_can_be_silenced(self, _):
        env_file.RealFile("some role", FILE_PATH).remove(
            silence_no_existence=True
        )
