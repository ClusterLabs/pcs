from unittest import mock, TestCase

from pcs.cli.booth import env
from pcs.common import report_codes, env_file_role_codes
from pcs.lib.errors import LibraryEnvError, ReportItem
from pcs.test.tools.misc import create_setup_patch_mixin

SetupPatchMixin = create_setup_patch_mixin(env)

class BoothConfTest(TestCase, SetupPatchMixin):
    def setUp(self):
        self.write = self.setup_patch("env_file.write")
        self.read = self.setup_patch("env_file.read")
        self.process_no_existing_file_expectation = self.setup_patch(
            "env_file.process_no_existing_file_expectation"
        )

    def test_sucessfully_care_about_local_file(self):
        def next_in_line(env):
            env.booth["modified_env"] = {
                "config_file": {
                    "content": "file content",
                    "no_existing_file_expected": False,
                },
                "key_file": {
                    "content": "key file content",
                    "no_existing_file_expected": False,
                }
            }
            return "call result"

        mock_env = mock.MagicMock()
        booth_conf_middleware = env.middleware_config(
            "booth-name",
            "/local/file/path.conf",
            "/local/file/path.key",
        )

        self.assertEqual(
            "call result",
            booth_conf_middleware(next_in_line, mock_env)
        )

        self.assertEqual(self.read.mock_calls, [
            mock.call('/local/file/path.conf'),
            mock.call('/local/file/path.key', is_binary=True),
        ])

        self.assertEqual(self.process_no_existing_file_expectation.mock_calls, [
            mock.call(
                'booth config file',
                {
                    'content': 'file content',
                    'no_existing_file_expected': False
                },
                '/local/file/path.conf'
            ),
            mock.call(
                'booth key file',
                {
                    'content': 'key file content',
                    'no_existing_file_expected': False
                },
                '/local/file/path.key'
            ),
        ])

        self.assertEqual(self.write.mock_calls, [
            mock.call(
                {
                    'content': 'key file content',
                    'no_existing_file_expected': False
                },
                '/local/file/path.key'
            ),
            mock.call(
                {
                    'content': 'file content',
                    'no_existing_file_expected': False
                },
                '/local/file/path.conf'
            )
        ])

    def test_catch_exactly_his_exception(self):
        report_missing = self.setup_patch("env_file.report_missing")
        next_in_line = mock.Mock(side_effect=LibraryEnvError(
            ReportItem.error(report_codes.FILE_DOES_NOT_EXIST, info={
                "file_role": env_file_role_codes.BOOTH_CONFIG,
            }),
            ReportItem.error(report_codes.FILE_DOES_NOT_EXIST, info={
                "file_role": env_file_role_codes.BOOTH_KEY,
            }),
            ReportItem.error("OTHER ERROR", info={}),
        ))
        mock_env = mock.MagicMock()
        self.read.return_value = {"content": None}

        booth_conf_middleware = env.middleware_config(
            "booth-name",
            "/local/file/path.conf",
            "/local/file/path.key",
        )
        raised_exception = []
        def run_middleware():
            try:
                booth_conf_middleware(next_in_line, mock_env)
            except Exception as e:
                raised_exception.append(e)
                raise e
        self.assertRaises(LibraryEnvError, run_middleware)
        self.assertEqual(1, len(raised_exception[0].unprocessed))
        self.assertEqual("OTHER ERROR", raised_exception[0].unprocessed[0].code)
        self.assertEqual(report_missing.mock_calls, [
            mock.call('Booth config file', '/local/file/path.conf'),
            mock.call('Booth key file', '/local/file/path.key'),
        ])
