from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

from pcs.cli.booth.env import middleware_config
from pcs.common import report_codes, env_file_role_codes
from pcs.lib.errors import LibraryEnvError, ReportItem
from pcs.test.tools.pcs_unittest import mock


class BoothConfTest(TestCase):
    @mock.patch("pcs.cli.booth.env.os.path.isfile")
    def test_sucessfully_care_about_local_file(self, mock_is_file):
        #setup, fixtures
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
        mock_is_file.return_value = True
        mock_env = mock.MagicMock()

        mock_open = mock.mock_open()
        with mock.patch(
            "pcs.cli.booth.env.open",
            mock_open,
            create=True
        ):
            #run tested code
            booth_conf_middleware = middleware_config(
                "booth-name",
                "/local/file/path.conf",
                "/local/file/path.key",
            )

            self.assertEqual(
                "call result",
                booth_conf_middleware(next_in_line, mock_env)
            )

        #assertions
        self.assertEqual(mock_is_file.mock_calls,[
            mock.call("/local/file/path.conf"),
            mock.call("/local/file/path.key"),
        ])

        self.assertEqual(mock_env.booth["name"], "booth-name")
        self.assertEqual(mock_env.booth["config_file"], {"content": ""})
        self.assertEqual(mock_env.booth["key_file"], {"content": ""})

        self.assertEqual(mock_open.mock_calls, [
            mock.call(u'/local/file/path.conf'),
            mock.call().read(),
            mock.call(u'/local/file/path.key'),
            mock.call().read(),
            mock.call(u'/local/file/path.key', u'w'),
            mock.call().write(u'key file content'),
            mock.call().close(),
            mock.call(u'/local/file/path.conf', u'w'),
            mock.call().write(u'file content'),
            mock.call().close(),
        ])

    @mock.patch("pcs.cli.booth.env.console_report")
    @mock.patch("pcs.cli.booth.env.os.path.isfile")
    def test_catch_exactly_his_exception(
        self, mock_is_file, mock_console_report
    ):
        next_in_line = mock.Mock(side_effect=LibraryEnvError(
            ReportItem.error(report_codes.FILE_DOES_NOT_EXIST, info={
                "file_role": env_file_role_codes.BOOTH_CONFIG,
            }),
            ReportItem.error(report_codes.FILE_DOES_NOT_EXIST, info={
                "file_role": env_file_role_codes.BOOTH_KEY,
            }),
            ReportItem.error("OTHER ERROR", info={}),
        ))
        mock_is_file.return_value = False
        mock_env = mock.MagicMock()

        #run tested code
        booth_conf_middleware = middleware_config(
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

        self.assertEqual(mock_console_report.error.mock_calls, [
            mock.call(
                "Booth config file '/local/file/path.conf' does not exist"
            ),
            mock.call(
                "Booth key file '/local/file/path.key' does not exist"
            ),
        ])
