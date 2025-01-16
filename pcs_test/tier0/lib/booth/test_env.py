import os
from unittest import TestCase

from pcs import settings
from pcs.common import file_type_codes
from pcs.common.reports import codes as report_codes
from pcs.lib.booth import env
from pcs.lib.file.raw_file import GhostFile

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_raise_library_error


class BoothEnv(TestCase):
    def test_ghost_conf_real_key(self):
        # pylint: disable=no-self-use
        assert_raise_library_error(
            lambda: env.BoothEnv(
                "my_booth", {"config_data": "some config data".encode("utf-8")}
            ),
            fixture.error(
                report_codes.LIVE_ENVIRONMENT_NOT_CONSISTENT,
                mocked_files=[file_type_codes.BOOTH_CONFIG],
                required_files=[file_type_codes.BOOTH_KEY],
            ),
        )

    def test_real_conf_ghost_key(self):
        # pylint: disable=no-self-use
        assert_raise_library_error(
            lambda: env.BoothEnv(
                "my_booth", {"key_data": "some key data".encode("utf-8")}
            ),
            fixture.error(
                report_codes.LIVE_ENVIRONMENT_NOT_CONSISTENT,
                mocked_files=[file_type_codes.BOOTH_KEY],
                required_files=[file_type_codes.BOOTH_CONFIG],
            ),
        )

    def test_real(self):
        my_env = env.BoothEnv("my_booth", {})
        self.assertEqual("my_booth", my_env.instance_name)
        self.assertFalse(isinstance(my_env.config.raw_file, GhostFile))
        self.assertFalse(isinstance(my_env.key.raw_file, GhostFile))
        self.assertEqual(
            os.path.join(settings.booth_config_dir, "my_booth.conf"),
            my_env.config_path,
        )
        self.assertEqual(
            os.path.join(settings.booth_config_dir, "my_booth.key"),
            my_env.key_path,
        )
        self.assertEqual([], my_env.ghost_file_codes)
        self.assertEqual({}, my_env.export())

        site_list = ["site1", "site2"]
        arbitrator_list = ["arbitrator1"]
        facade = my_env.create_facade(site_list, arbitrator_list)
        self.assertEqual(site_list, facade.get_sites())
        self.assertEqual(arbitrator_list, facade.get_arbitrators())

    def test_ghost(self):
        config_data = "some config_data".encode("utf-8")
        key_data = "some key_data".encode("utf-8")
        key_path = "some key path"
        my_env = env.BoothEnv(
            "my_booth",
            {
                "config_data": config_data,
                "key_data": key_data,
                "key_path": key_path,
            },
        )
        self.assertEqual("my_booth", my_env.instance_name)
        self.assertTrue(isinstance(my_env.config.raw_file, GhostFile))
        self.assertTrue(isinstance(my_env.key.raw_file, GhostFile))
        with self.assertRaises(AssertionError) as cm:
            _ = my_env.config_path
        self.assertEqual(
            "Reading config path is supported only in live environment",
            str(cm.exception),
        )
        self.assertEqual(key_path, my_env.key_path)
        self.assertEqual(
            [file_type_codes.BOOTH_CONFIG, file_type_codes.BOOTH_KEY],
            my_env.ghost_file_codes,
        )
        self.assertEqual(
            {
                "config_file": {"content": config_data},
                "key_file": {"content": key_data},
            },
            my_env.export(),
        )

        site_list = ["site1", "site2"]
        arbitrator_list = ["arbitrator1"]
        facade = my_env.create_facade(site_list, arbitrator_list)
        self.assertEqual(site_list, facade.get_sites())
        self.assertEqual(arbitrator_list, facade.get_arbitrators())

    def test_invalid_instance(self):
        # pylint: disable=no-self-use
        assert_raise_library_error(
            lambda: env.BoothEnv("/tmp/booth/booth", {}),
            fixture.error(
                report_codes.BOOTH_INVALID_NAME,
                name="/tmp/booth/booth",
                forbidden_characters="/",
            ),
        )

    def test_invalid_instance_ghost(self):
        # pylint: disable=no-self-use
        assert_raise_library_error(
            lambda: env.BoothEnv(
                "../../booth/booth",
                {
                    "config_data": "some config data",
                    "key_data": "some key data",
                    "key_path": "some key path",
                },
            ),
            fixture.error(
                report_codes.BOOTH_INVALID_NAME,
                name="../../booth/booth",
                forbidden_characters="/",
            ),
        )

    def test_default_instance(self):
        self.assertEqual(env.BoothEnv(None, {}).instance_name, "booth")
