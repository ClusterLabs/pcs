from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

from pcs.common import report_codes
from pcs.lib.booth import env
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.settings import booth_config_dir as BOOTH_CONFIG_DIR
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.pcs_mock import mock


class GetConfigFileNameTest(TestCase):
    def test_refuse_when_name_starts_with_slash(self):
        assert_raise_library_error(
            lambda: env.get_config_file_name("/booth"),
            (
                severities.ERROR,
                report_codes.BOOTH_INVALID_NAME,
                {
                    "name": "/booth",
                }
            ),
        )

    @mock.patch("pcs.lib.booth.env.os.path.exists")
    def test_refuse_when_standard_dir_does_not_exist(self, mock_path_exists):
        mock_path_exists.return_value = False
        assert_raise_library_error(
            lambda: env.get_config_file_name("booth"),
            (
                severities.ERROR,
                report_codes.BOOTH_CONFIG_DIR_DOES_NOT_EXISTS,
                {
                    "dir": BOOTH_CONFIG_DIR,
                }
            ),
        )

class BoothEnvTest(TestCase):
    @mock.patch("pcs.lib.booth.env.RealFile")
    def test_get_content_from_file(self, mock_real_file):
        mock_real_file.return_value = mock.MagicMock(
            read=mock.MagicMock(return_value=["content"])
        )
        self.assertEqual(
            ["content"],
            env.BoothEnv("report processor", env_data={"name": "booth"})
                .get_config_content()
        )

    @mock.patch("pcs.lib.booth.env.RealFile")
    def test_create_config(self, mock_real_file):
        mock_file = mock.MagicMock(
            assert_no_conflict_with_existing=mock.MagicMock(),
            write=mock.MagicMock(),
        )
        mock_real_file.return_value = mock_file


        env.BoothEnv(
            "report processor",
            env_data={"name": "booth"}
        ).create_config(["a"], can_overwrite_existing=True)

        mock_file.write.assert_called_once_with(["a"])
        mock_file.assert_no_conflict_with_existing.assert_called_once_with(
            "report processor",
            True
        )

    @mock.patch("pcs.lib.booth.env.RealFile")
    def test_push_config(self, mock_real_file):
        mock_file = mock.MagicMock(
            assert_no_conflict_with_existing=mock.MagicMock(),
            write=mock.MagicMock(),
        )
        mock_real_file.return_value = mock_file
        env.BoothEnv(
            "report processor",
            env_data={"name": "booth"}
        ).push_config("a")
        mock_file.write.assert_called_once_with("a")



    def test_export_config_file_when_was_present_in_env_data(self):
        self.assertEqual(
            env.BoothEnv(
                "report processor",
                {
                    "config_file": {
                        "content": ["a", "b"]
                    }
                }
            ).export(),
            {
                "config_file": {
                    "content": ["a", "b"],
                    "can_overwrite_existing_file": False,
                    "no_existing_file_expected": False,
                }
            }
        )

    def test_do_not_export_config_file_when_no_provided(self):
        self.assertEqual(
            env.BoothEnv("report processor", {"name": "booth"}).export(),
            {}
        )
