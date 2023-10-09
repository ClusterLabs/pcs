from unittest import (
    TestCase,
    mock,
)

from pcs.cli.booth import env
from pcs.common import file_type_codes


class BoothConfTest(TestCase):
    @mock.patch("pcs.cli.reports.output.sys.stderr.write")
    def test_mocked_key_not_config(self, mock_stderr):
        with self.assertRaises(SystemExit):
            env.middleware_config(None, "/local/file/path.key")
        mock_stderr.assert_called_once_with(
            "Error: When --booth-key is specified, --booth-conf must be "
            "specified as well\n"
        )

    @mock.patch("pcs.cli.reports.output.sys.stderr.write")
    def test_mocked_config_not_key(self, mock_stderr):
        with self.assertRaises(SystemExit):
            env.middleware_config("/local/file/path.conf", None)
        mock_stderr.assert_called_once_with(
            "Error: When --booth-conf is specified, --booth-key must be "
            "specified as well\n"
        )

    def test_not_mocked(self):
        def next_in_line(_env):
            self.assertEqual(_env.booth, {})
            return "call result"

        mock_env = mock.MagicMock()

        booth_conf_middleware = env.middleware_config(None, None)
        self.assertEqual(
            "call result", booth_conf_middleware(next_in_line, mock_env)
        )

    @mock.patch.object(env.pcs_file.RawFile, "write", autospec=True)
    @mock.patch.object(env.pcs_file.RawFile, "read", autospec=True)
    @mock.patch.object(env.pcs_file.RawFile, "exists")
    def test_mocked(self, mock_exists, mock_read, mock_write):
        conf_content = "file content".encode("utf-8")
        key_content = "key file content".encode("utf-8")
        conf_path = "/tmp/pcs_test/file/path.conf"
        key_path = "/tmp/pcs_test/file/path.key"
        new_conf = "new conf".encode("utf-8")
        new_key = "new key".encode("utf-8")

        def next_in_line(_env):
            self.assertEqual(
                _env.booth,
                {
                    "config_data": conf_content,
                    "key_data": key_content,
                    "key_path": key_path,
                },
            )
            _env.booth["modified_env"] = {
                "config_file": {"content": new_conf},
                "key_file": {"content": new_key},
            }
            return "call result"

        mock_exists.return_value = True

        def read(this):
            if this.metadata.file_type_code == file_type_codes.BOOTH_KEY:
                return key_content
            if this.metadata.file_type_code == file_type_codes.BOOTH_CONFIG:
                return conf_content
            raise AssertionError(f"Unexpected file type: {this.metadata}")

        mock_read.side_effect = read

        def write(this, data, can_overwrite):
            if this.metadata.file_type_code == file_type_codes.BOOTH_KEY:
                self.assertEqual(data, new_key)
                self.assertTrue(can_overwrite)
                return
            if this.metadata.file_type_code == file_type_codes.BOOTH_CONFIG:
                self.assertEqual(data, new_conf)
                self.assertTrue(can_overwrite)
                return
            raise AssertionError(f"Unexpected file type: {this.metadata}")

        mock_write.side_effect = write

        mock_env = mock.MagicMock()
        booth_conf_middleware = env.middleware_config(conf_path, key_path)

        self.assertEqual(
            "call result", booth_conf_middleware(next_in_line, mock_env)
        )
