from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

from pcs.common import report_codes
from pcs.lib.env_file import RealFile, GhostFile
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import(
    assert_raise_library_error,
    assert_report_item_list_equal
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.pcs_unittest import mock


class GhostFileReadTest(TestCase):
    def test_raises_when_trying_read_nonexistent_file(self):
        assert_raise_library_error(
            lambda: GhostFile("some role", content=None).read(),
            (
                severities.ERROR,
                report_codes.FILE_DOES_NOT_EXIST,
                {
                    "file_role": "some role",
                }
            ),
        )

@mock.patch("pcs.lib.env_file.os.path.exists", return_value=True)
class RealFileAssertNoConflictWithExistingTest(TestCase):
    def check(self, report_processor, can_overwrite_existing=False):
        real_file = RealFile("some role", "/etc/booth/some-name.conf")
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
                    "file_path": "/etc/booth/some-name.conf"
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
                "file_path": "/etc/booth/some-name.conf"
            },
        )])

class RealFileWriteTest(TestCase):
    def test_success_write_content_to_path(self):
        mock_open = mock.mock_open()
        mock_file_operation = mock.Mock()
        with mock.patch("pcs.lib.env_file.open", mock_open, create=True):
            RealFile("some role", "/etc/booth/some-name.conf").write(
                "config content",
                file_operation=mock_file_operation
            )
            mock_open.assert_called_once_with("/etc/booth/some-name.conf", "w")
            mock_open().write.assert_called_once_with("config content")
            mock_file_operation.assert_called_once_with(
                "/etc/booth/some-name.conf"
            )

    def test_success_binary(self):
        mock_open = mock.mock_open()
        mock_file_operation = mock.Mock()
        with mock.patch("pcs.lib.env_file.open", mock_open, create=True):
            RealFile("some role", "/etc/booth/some-name.conf").write(
                "config content".encode("utf-8"),
                file_operation=mock_file_operation,
                is_binary=True
            )
            mock_open.assert_called_once_with("/etc/booth/some-name.conf", "wb")
            mock_open().write.assert_called_once_with(
                "config content".encode("utf-8")
            )
            mock_file_operation.assert_called_once_with(
                "/etc/booth/some-name.conf"
            )

    def test_raises_when_could_not_write(self):
        assert_raise_library_error(
            lambda:
            RealFile("some role", "/no/existing/file.path").write(["content"]),
            (
                severities.ERROR,
                report_codes.FILE_IO_ERROR,
                {
                    "reason":
                        "No such file or directory: '/no/existing/file.path'"
                    ,
                }
            )
        )

class RealFileReadTest(TestCase):
    def test_success_read_content_from_file(self):
        mock_open = mock.mock_open()
        with mock.patch("pcs.lib.env_file.open", mock_open, create=True):
            mock_open().read.return_value = "test booth\nconfig"
            self.assertEqual(
                "test booth\nconfig",
                RealFile("some role", "/path/to.file").read()
            )

    def test_raises_when_could_not_read(self):
        assert_raise_library_error(
            lambda: RealFile("some role", "/no/existing/file.path").read(),
            (
                severities.ERROR,
                report_codes.FILE_IO_ERROR,
                {
                    "reason":
                        "No such file or directory: '/no/existing/file.path'"
                    ,
                }
            )
        )

class RealFileRemoveTest(TestCase):
    @mock.patch("pcs.lib.env_file.os.remove")
    @mock.patch("pcs.lib.env_file.os.path.exists", return_value=True)
    def test_success_remove_file(self, _, mock_remove):
        RealFile("some role", "/path/to.file").remove()
        mock_remove.assert_called_once_with("/path/to.file")

    @mock.patch(
        "pcs.lib.env_file.os.remove",
        side_effect=EnvironmentError(1, "mock remove failed", "/path/to.file")
    )
    @mock.patch("pcs.lib.env_file.os.path.exists", return_value=True)
    def test_raise_library_error_when_remove_failed(self, _, dummy):
        assert_raise_library_error(
            lambda: RealFile("some role", "/path/to.file").remove(),
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

    @mock.patch("pcs.lib.env_file.os.path.exists", return_value=False)
    def test_existence_is_required(self, _):
        assert_raise_library_error(
            lambda: RealFile("some role", "/path/to.file").remove(),
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

    @mock.patch("pcs.lib.env_file.os.path.exists", return_value=False)
    def test_noexistent_can_be_silenced(self, _):
        RealFile("some role", "/path/to.file").remove(silence_no_existence=True)
