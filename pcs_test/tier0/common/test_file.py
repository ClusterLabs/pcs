import errno
import fcntl
from unittest import mock, TestCase

from pcs.common.file import (
    FileAlreadyExists,
    FileMetadata,
    RawFile,
    RawFileError,
)
from pcs_test.tools.misc import create_patcher


FILE_TYPE_CODE = "file type code"
FILE_PATH = "file path"
FILE_OWNER = "owner name"
FILE_GROUP = "group name"
FILE_PERMISSIONS = "file permissions"
FILE_IS_BINARY = False

patch_file = create_patcher("pcs.common.file")


def fixture_metadata(
    owner=FILE_OWNER,
    group=FILE_GROUP,
    permissions=FILE_PERMISSIONS,
    binary=FILE_IS_BINARY,
):
    return FileMetadata(
        FILE_TYPE_CODE, FILE_PATH, owner, group, permissions, binary
    )


class RawFileExists(TestCase):
    @patch_file("os.path.exists")
    def test_return_true_if_file_exists(self, mock_exists):
        mock_exists.return_value = True
        self.assertTrue(RawFile(fixture_metadata()).exists())
        mock_exists.assert_called_once_with(FILE_PATH)

    @patch_file("os.path.exists")
    def test_return_false_if_file_does_not_exist(self, mock_exists):
        mock_exists.return_value = False
        self.assertFalse(RawFile(fixture_metadata()).exists())
        mock_exists.assert_called_once_with(FILE_PATH)


@patch_file("fcntl.flock")
class RawFileRead(TestCase):
    def assert_read_in_correct_mode(self, mock_flock, raw_file, mode):
        file_data = "some file data"
        returned_data = file_data.encode("utf-8")
        if "b" in mode:
            file_data = file_data.encode("utf-8")
        mock_open = mock.mock_open()
        with patch_file("open", mock_open):
            mock_open().read.return_value = file_data
            mock_open().fileno.return_value = 123
            self.assertEqual(returned_data, raw_file.read())
            mock_open().read.assert_called_once_with()
        mock_open.assert_has_calls([mock.call(FILE_PATH, mode)])
        mock_flock.assert_called_once_with(123, fcntl.LOCK_SH)

    def test_success_text(self, mock_flock):
        self.assert_read_in_correct_mode(
            mock_flock, RawFile(fixture_metadata()), "r",
        )

    def test_success_binary(self, mock_flock):
        self.assert_read_in_correct_mode(
            mock_flock, RawFile(fixture_metadata(binary=True)), "rb",
        )

    def test_cannot_open(self, mock_flock):
        raw_file = RawFile(fixture_metadata())
        mock_open = mock.mock_open()
        with patch_file("open", mock_open):
            mock_open.side_effect = OSError(1, "some error", FILE_PATH)
            with self.assertRaises(RawFileError) as cm:
                raw_file.read()
                mock_open().read.assert_not_called()
        mock_open.assert_has_calls([mock.call(FILE_PATH, "r")])
        mock_flock.assert_not_called()
        self.assertEqual(cm.exception.metadata, raw_file.metadata)
        self.assertEqual(cm.exception.action, RawFileError.ACTION_READ)
        self.assertEqual(cm.exception.reason, f"some error: '{FILE_PATH}'")

    def test_cannot_lock(self, mock_flock):
        raw_file = RawFile(fixture_metadata())
        mock_flock.side_effect = OSError(1, "some error", FILE_PATH)
        mock_open = mock.mock_open()
        with patch_file("open", mock_open):
            mock_open().fileno.return_value = 123
            with self.assertRaises(RawFileError) as cm:
                raw_file.read()
                mock_open().read.assert_not_called()
        mock_open.assert_has_calls([mock.call(FILE_PATH, "r")])
        mock_flock.assert_called_once_with(123, fcntl.LOCK_SH)
        self.assertEqual(cm.exception.metadata, raw_file.metadata)
        self.assertEqual(cm.exception.action, RawFileError.ACTION_READ)
        self.assertEqual(cm.exception.reason, f"some error: '{FILE_PATH}'")

    def test_cannot_read(self, mock_flock):
        raw_file = RawFile(fixture_metadata())
        mock_open = mock.mock_open()
        with patch_file("open", mock_open):
            mock_open().read.side_effect = OSError(1, "some error", FILE_PATH)
            mock_open().fileno.return_value = 123
            with self.assertRaises(RawFileError) as cm:
                raw_file.read()
            mock_open().read.assert_called_once_with()
        mock_open.assert_has_calls([mock.call(FILE_PATH, "r")])
        mock_flock.assert_called_once_with(123, fcntl.LOCK_SH)
        self.assertEqual(cm.exception.metadata, raw_file.metadata)
        self.assertEqual(cm.exception.action, RawFileError.ACTION_READ)
        self.assertEqual(cm.exception.reason, f"some error: '{FILE_PATH}'")


@patch_file("fcntl.flock")
@patch_file("shutil.chown")
@patch_file("os.chmod")
class RawFileWrite(TestCase):
    fileno = 123

    def assert_success(self, mock_flock, raw_file, mode, can_overwrite):
        file_data = "some file data".encode("utf-8")
        written_data = file_data
        if not "b" in mode:
            written_data = written_data.decode("utf-8")
        mock_open = mock.mock_open()
        with patch_file("open", mock_open):
            mock_open().fileno.return_value = self.fileno
            raw_file.write(file_data, can_overwrite=can_overwrite)
            mock_open().write.assert_called_once_with(written_data)
        mock_open.assert_has_calls([mock.call(FILE_PATH, mode)])
        mock_flock.assert_called_once_with(self.fileno, fcntl.LOCK_EX)

    def test_success_minimal(self, mock_chmod, mock_chown, mock_flock):
        self.assert_success(
            mock_flock,
            RawFile(fixture_metadata(owner=None, group=None, permissions=None)),
            "x",
            False,
        )
        mock_chown.assert_not_called()
        mock_chmod.assert_not_called()

    def test_success_minimal_binary(self, mock_chmod, mock_chown, mock_flock):
        self.assert_success(
            mock_flock,
            RawFile(
                fixture_metadata(
                    owner=None, group=None, permissions=None, binary=True
                )
            ),
            "xb",
            False,
        )
        mock_chown.assert_not_called()
        mock_chmod.assert_not_called()

    def test_success_overwrite(self, mock_chmod, mock_chown, mock_flock):
        self.assert_success(
            mock_flock,
            RawFile(fixture_metadata(owner=None, group=None, permissions=None)),
            "w",
            True,
        )
        mock_chown.assert_not_called()
        mock_chmod.assert_not_called()

    def test_success_overwrite_binary(self, mock_chmod, mock_chown, mock_flock):
        self.assert_success(
            mock_flock,
            RawFile(
                fixture_metadata(
                    owner=None, group=None, permissions=None, binary=True
                )
            ),
            "wb",
            True,
        )
        mock_chown.assert_not_called()
        mock_chmod.assert_not_called()

    def test_success_owner_user(self, mock_chmod, mock_chown, mock_flock):
        self.assert_success(
            mock_flock,
            RawFile(fixture_metadata(group=None, permissions=None)),
            "x",
            False,
        )
        mock_chown.assert_called_once_with(FILE_PATH, FILE_OWNER, None)
        mock_chmod.assert_not_called()

    def test_success_owner_group(self, mock_chmod, mock_chown, mock_flock):
        self.assert_success(
            mock_flock,
            RawFile(fixture_metadata(owner=None, permissions=None)),
            "x",
            False,
        )
        mock_chown.assert_called_once_with(FILE_PATH, None, FILE_GROUP)
        mock_chmod.assert_not_called()

    def test_success_owner_both(self, mock_chmod, mock_chown, mock_flock):
        self.assert_success(
            mock_flock, RawFile(fixture_metadata(permissions=None)), "x", False
        )
        mock_chown.assert_called_once_with(FILE_PATH, FILE_OWNER, FILE_GROUP)
        mock_chmod.assert_not_called()

    def test_success_permissions(self, mock_chmod, mock_chown, mock_flock):
        self.assert_success(
            mock_flock,
            RawFile(fixture_metadata(owner=None, group=None)),
            "x",
            False,
        )
        mock_chown.assert_not_called()
        mock_chmod.assert_called_once_with(self.fileno, FILE_PERMISSIONS)

    def test_success_chown_permissions(
        self, mock_chmod, mock_chown, mock_flock
    ):
        self.assert_success(mock_flock, RawFile(fixture_metadata()), "x", False)
        mock_chown.assert_called_once_with(FILE_PATH, FILE_OWNER, FILE_GROUP)
        mock_chmod.assert_called_once_with(self.fileno, FILE_PERMISSIONS)

    def test_already_exists(self, mock_chmod, mock_chown, mock_flock):
        raw_file = RawFile(fixture_metadata())
        mock_open = mock.mock_open()
        with patch_file("open", mock_open):
            mock_open.side_effect = OSError(
                errno.EEXIST, "some error", FILE_PATH
            )
            with self.assertRaises(FileAlreadyExists) as cm:
                raw_file.write(b"data")
                mock_open().write.assert_not_called()
        mock_open.assert_has_calls([mock.call(FILE_PATH, "x")])
        mock_flock.assert_not_called()
        mock_chown.assert_not_called()
        mock_chmod.assert_not_called()
        self.assertEqual(cm.exception.metadata, raw_file.metadata)
        self.assertEqual(cm.exception.action, RawFileError.ACTION_WRITE)
        self.assertEqual(cm.exception.reason, "")

    def test_cannot_open(self, mock_chmod, mock_chown, mock_flock):
        raw_file = RawFile(fixture_metadata())
        mock_open = mock.mock_open()
        with patch_file("open", mock_open):
            mock_open.side_effect = OSError(1, "some error", FILE_PATH)
            with self.assertRaises(RawFileError) as cm:
                raw_file.write(b"data")
                mock_open().write.assert_not_called()
        mock_open.assert_has_calls([mock.call(FILE_PATH, "x")])
        mock_flock.assert_not_called()
        mock_chown.assert_not_called()
        mock_chmod.assert_not_called()
        self.assertEqual(cm.exception.metadata, raw_file.metadata)
        self.assertEqual(cm.exception.action, RawFileError.ACTION_WRITE)
        self.assertEqual(cm.exception.reason, f"some error: '{FILE_PATH}'")

    def test_cannot_lock(self, mock_chmod, mock_chown, mock_flock):
        raw_file = RawFile(fixture_metadata())
        mock_flock.side_effect = OSError(1, "some error", FILE_PATH)
        mock_open = mock.mock_open()
        with patch_file("open", mock_open):
            mock_open().fileno.return_value = self.fileno
            with self.assertRaises(RawFileError) as cm:
                raw_file.write(b"data")
                mock_open().write.assert_not_called()
        mock_open.assert_has_calls([mock.call(FILE_PATH, "x")])
        mock_flock.assert_called_once_with(self.fileno, fcntl.LOCK_EX)
        mock_chown.assert_not_called()
        mock_chmod.assert_not_called()
        self.assertEqual(cm.exception.metadata, raw_file.metadata)
        self.assertEqual(cm.exception.action, RawFileError.ACTION_WRITE)
        self.assertEqual(cm.exception.reason, f"some error: '{FILE_PATH}'")

    def test_cannot_chown_bad_user(self, mock_chmod, mock_chown, mock_flock):
        raw_file = RawFile(fixture_metadata())
        mock_chown.side_effect = LookupError("some error")
        mock_open = mock.mock_open()
        with patch_file("open", mock_open):
            mock_open().fileno.return_value = self.fileno
            with self.assertRaises(RawFileError) as cm:
                raw_file.write(b"data")
                mock_open().write.assert_not_called()
        mock_open.assert_has_calls([mock.call(FILE_PATH, "x")])
        mock_flock.assert_called_once_with(self.fileno, fcntl.LOCK_EX)
        mock_chown.assert_called_once_with(FILE_PATH, FILE_OWNER, FILE_GROUP)
        mock_chmod.assert_not_called()
        self.assertEqual(cm.exception.metadata, raw_file.metadata)
        self.assertEqual(cm.exception.action, RawFileError.ACTION_CHOWN)
        self.assertEqual(cm.exception.reason, "some error")

    def test_cannot_chown(self, mock_chmod, mock_chown, mock_flock):
        raw_file = RawFile(fixture_metadata())
        mock_chown.side_effect = OSError(1, "some error", FILE_PATH)
        mock_open = mock.mock_open()
        with patch_file("open", mock_open):
            mock_open().fileno.return_value = self.fileno
            with self.assertRaises(RawFileError) as cm:
                raw_file.write(b"data")
                mock_open().write.assert_not_called()
        mock_open.assert_has_calls([mock.call(FILE_PATH, "x")])
        mock_flock.assert_called_once_with(self.fileno, fcntl.LOCK_EX)
        mock_chown.assert_called_once_with(FILE_PATH, FILE_OWNER, FILE_GROUP)
        mock_chmod.assert_not_called()
        self.assertEqual(cm.exception.metadata, raw_file.metadata)
        self.assertEqual(cm.exception.action, RawFileError.ACTION_CHOWN)
        self.assertEqual(cm.exception.reason, f"some error: '{FILE_PATH}'")

    def test_cannot_chmod(self, mock_chmod, mock_chown, mock_flock):
        raw_file = RawFile(fixture_metadata())
        mock_chmod.side_effect = OSError(1, "some error", FILE_PATH)
        mock_open = mock.mock_open()
        with patch_file("open", mock_open):
            mock_open().fileno.return_value = self.fileno
            with self.assertRaises(RawFileError) as cm:
                raw_file.write(b"data")
                mock_open().write.assert_not_called()
        mock_open.assert_has_calls([mock.call(FILE_PATH, "x")])
        mock_flock.assert_called_once_with(self.fileno, fcntl.LOCK_EX)
        mock_chown.assert_called_once_with(FILE_PATH, FILE_OWNER, FILE_GROUP)
        mock_chmod.assert_called_once_with(self.fileno, FILE_PERMISSIONS)
        self.assertEqual(cm.exception.metadata, raw_file.metadata)
        self.assertEqual(cm.exception.action, RawFileError.ACTION_CHMOD)
        self.assertEqual(cm.exception.reason, f"some error: '{FILE_PATH}'")

    def test_cannot_write(self, mock_chmod, mock_chown, mock_flock):
        raw_file = RawFile(fixture_metadata())
        mock_open = mock.mock_open()
        with patch_file("open", mock_open):
            mock_open().fileno.return_value = self.fileno
            mock_open().write.side_effect = OSError(1, "some error", FILE_PATH)
            with self.assertRaises(RawFileError) as cm:
                raw_file.write(b"data")
            mock_open().write.assert_called_once_with("data")
        mock_open.assert_has_calls([mock.call(FILE_PATH, "x")])
        mock_flock.assert_called_once_with(self.fileno, fcntl.LOCK_EX)
        mock_chown.assert_called_once_with(FILE_PATH, FILE_OWNER, FILE_GROUP)
        mock_chmod.assert_called_once_with(self.fileno, FILE_PERMISSIONS)
        self.assertEqual(cm.exception.metadata, raw_file.metadata)
        self.assertEqual(cm.exception.action, RawFileError.ACTION_WRITE)
        self.assertEqual(cm.exception.reason, f"some error: '{FILE_PATH}'")


@patch_file("os.remove")
class RawFileRemove(TestCase):
    # pylint: disable=no-self-use
    def test_success(self, mock_remove):
        RawFile(fixture_metadata()).remove()
        mock_remove.assert_called_once_with(FILE_PATH)

    def test_file_not_found(self, mock_remove):
        mock_remove.side_effect = OSError(errno.ENOENT, "some error", FILE_PATH)
        RawFile(fixture_metadata()).remove(fail_if_file_not_found=False)
        mock_remove.assert_called_once_with(FILE_PATH)

    def test_file_not_found_fail(self, mock_remove):
        raw_file = RawFile(fixture_metadata())
        mock_remove.side_effect = OSError(errno.ENOENT, "some error", FILE_PATH)
        with self.assertRaises(RawFileError) as cm:
            raw_file.remove(fail_if_file_not_found=True)
        mock_remove.assert_called_once_with(FILE_PATH)
        self.assertEqual(cm.exception.metadata, raw_file.metadata)
        self.assertEqual(cm.exception.action, RawFileError.ACTION_REMOVE)
        self.assertEqual(cm.exception.reason, f"some error: '{FILE_PATH}'")

    def test_cannot_remove(self, mock_remove):
        raw_file = RawFile(fixture_metadata())
        mock_remove.side_effect = OSError(1, "some error", FILE_PATH)
        with self.assertRaises(RawFileError) as cm:
            raw_file.remove(fail_if_file_not_found=True)
        mock_remove.assert_called_once_with(FILE_PATH)
        self.assertEqual(cm.exception.metadata, raw_file.metadata)
        self.assertEqual(cm.exception.action, RawFileError.ACTION_REMOVE)
        self.assertEqual(cm.exception.reason, f"some error: '{FILE_PATH}'")
