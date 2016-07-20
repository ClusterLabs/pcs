from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import grp
import os
import pwd
from unittest import TestCase

from pcs import settings
from pcs.common import report_codes
from pcs.lib.booth import env
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.pcs_mock import mock


class GetConfigFileNameTest(TestCase):
    @mock.patch("pcs.lib.booth.env.os.path.exists")
    def test_refuse_when_name_starts_with_slash(self, mock_path_exists):
        mock_path_exists.return_value = True
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

    @mock.patch("pcs.lib.booth.env.set_keyfile_access")
    @mock.patch("pcs.lib.booth.env.RealFile")
    def test_create_config(self, mock_real_file, mock_set_keyfile_access):
        mock_file = mock.MagicMock(
            assert_no_conflict_with_existing=mock.MagicMock(),
            write=mock.MagicMock(),
        )
        mock_real_file.return_value = mock_file


        env.BoothEnv(
            "report processor",
            env_data={"name": "booth"}
        ).create_config("a", can_overwrite_existing=True)

        self.assertEqual(mock_file.assert_no_conflict_with_existing.mock_calls,[
            mock.call('report processor', True),
        ])
        self.assertEqual(mock_file.write.mock_calls, [mock.call('a')])

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
                        "content": "a\nb",
                    },
                    "key_file": {
                        "content": "secure",
                    },
                    "key_path": "/path/to/file.key",
                }
            ).export(),
            {
                "config_file": {
                    "content": "a\nb",
                    "can_overwrite_existing_file": False,
                    "no_existing_file_expected": False,
                },
                "key_file": {
                    "content": "secure",
                    "can_overwrite_existing_file": False,
                    "no_existing_file_expected": False,
                },
            }
        )

    def test_do_not_export_config_file_when_no_provided(self):
        self.assertEqual(
            env.BoothEnv("report processor", {"name": "booth"}).export(),
            {}
        )

class SetKeyfileAccessTest(TestCase):
    def test_set_neede_file_access(self):
        #setup
        file_path = rc("tmp_keyfile")
        if os.path.exists(file_path):
            os.remove(file_path)
        with open(file_path, "w") as file:
            file.write("content")

        #check assumptions
        stat = os.stat(file_path)
        self.assertNotEqual('400', oct(stat.st_mode)[-3:])
        current_user = pwd.getpwuid(os.getuid())[0]
        if current_user != settings.pacemaker_uname:
            file_user = pwd.getpwuid(stat.st_uid)[0]
            self.assertNotEqual(file_user, settings.pacemaker_uname)
        current_group = grp.getgrgid(os.getgid())[0]
        if current_group != settings.pacemaker_gname:
            file_group = grp.getgrgid(stat.st_gid)[0]
            self.assertNotEqual(file_group, settings.pacemaker_gname)

        #run tested method
        env.set_keyfile_access(file_path)

        #check
        stat = os.stat(file_path)
        self.assertEqual('400', oct(stat.st_mode)[-3:])

        file_user = pwd.getpwuid(stat.st_uid)[0]
        self.assertEqual(file_user, settings.pacemaker_uname)

        file_group = grp.getgrgid(stat.st_gid)[0]
        self.assertEqual(file_group, settings.pacemaker_gname)
