from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

from pcs.cli.pacemaker import env
from pcs.common import report_codes, env_file_role_codes
from pcs.lib.errors import LibraryEnvError, ReportItem
from pcs.test.tools.pcs_unittest import mock
from pcs.test.tools.misc import create_setup_patch_mixin

SetupPatchMixin = create_setup_patch_mixin(env)

AUTHKEY_PATH = "/local/file/authkey"

class MiddlewareConfig(TestCase, SetupPatchMixin):
    def setUp(self):
        self.write = self.setup_patch("env_file.write")
        self.read = self.setup_patch("env_file.read")
        self.process_no_existing_file_expectation = self.setup_patch(
            "env_file.process_no_existing_file_expectation"
        )

    def test_sucessfully_care_about_local_file(self):
        def next_in_line(env):
            env.pacemaker["modified_env"] = {
                "authkey": {
                    "content": "file content",
                    "no_existing_file_expected": False,
                },
            }
            return "call result"

        mock_env = mock.MagicMock()
        middleware = env.middleware_config(AUTHKEY_PATH)

        self.assertEqual("call result", middleware(next_in_line, mock_env))
        self.assertEqual(self.read.mock_calls, [mock.call(AUTHKEY_PATH)])
        self.assertEqual(self.process_no_existing_file_expectation.mock_calls, [
            mock.call(
                'pacemaker authkey',
                {
                    'content': 'file content',
                    'no_existing_file_expected': False
                },
                AUTHKEY_PATH
            ),
        ])
        self.assertEqual(self.write.mock_calls, [
            mock.call(
                {
                    'content': 'file content',
                    'no_existing_file_expected': False
                },
                AUTHKEY_PATH
            ),
        ])

    def test_catch_exactly_his_exception(self):
        report_missing = self.setup_patch("env_file.report_missing")
        next_in_line = mock.Mock(side_effect=LibraryEnvError(
            ReportItem.error(report_codes.FILE_DOES_NOT_EXIST, info={
                "file_role": env_file_role_codes.PACEMAKER_AUTHKEY,
            }),
            ReportItem.error("OTHER ERROR", info={}),
        ))
        mock_env = mock.MagicMock()
        self.read.return_value = {"content": None}

        middleware = env.middleware_config(AUTHKEY_PATH)
        raised_exception = []
        def run_middleware():
            try:
                middleware(next_in_line, mock_env)
            except Exception as e:
                raised_exception.append(e)
                raise e
        self.assertRaises(LibraryEnvError, run_middleware)
        self.assertEqual(1, len(raised_exception[0].unprocessed))
        self.assertEqual("OTHER ERROR", raised_exception[0].unprocessed[0].code)
        self.assertEqual(
            report_missing.mock_calls,
            [mock.call('Pacemaker authkey', AUTHKEY_PATH)]
        )
