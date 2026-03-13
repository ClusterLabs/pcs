from unittest import TestCase, mock

from pcs import settings
from pcs.lib.pcs_cfgsync.config.facade import Facade as CfgsyncFacade


class Facade(TestCase):
    def assert_all_default_values(self, facade: CfgsyncFacade):
        self.assertTrue(facade.is_sync_allowed)
        self.assertFalse(facade.is_sync_paused)
        self.assertEqual(
            settings.pcs_cfgsync_thread_interval_default, facade.sync_interval
        )
        self.assertEqual(
            settings.pcs_cfgsync_thread_interval_previous_not_connected_default,
            facade.sync_interval_previous_not_connected,
        )
        self.assertEqual(
            settings.pcs_cfgsync_file_backup_count_default,
            facade.file_backup_count,
        )

    def test_create(self):
        facade = CfgsyncFacade.create()
        self.assert_all_default_values(facade)

    def test_empty_file(self):
        facade = CfgsyncFacade({})
        self.assert_all_default_values(facade)

    def test_file_with_values(self):
        facade = CfgsyncFacade(
            {
                "thread_disabled": True,
                "thread_interval": 100,
                "thread_interval_previous_not_connected": 30,
                "file_backup_count": 20,
            }
        )
        self.assertFalse(facade.is_sync_allowed)
        self.assertFalse(facade.is_sync_paused)
        self.assertEqual(100, facade.sync_interval)
        self.assertEqual(30, facade.sync_interval_previous_not_connected)
        self.assertEqual(20, facade.file_backup_count)

    def test_too_low_values(self):
        facade = CfgsyncFacade(
            {
                "thread_interval": 1,
                "thread_interval_previous_not_connected": 1,
                "file_backup_count": -1,
            }
        )
        self.assertEqual(
            settings.pcs_cfgsync_thread_interval_minimum, facade.sync_interval
        )
        self.assertEqual(
            settings.pcs_cfgsync_thread_interval_previous_not_connected_minimum,
            facade.sync_interval_previous_not_connected,
        )
        self.assertEqual(
            settings.pcs_cfgsync_file_backup_count_minimum,
            facade.file_backup_count,
        )

    @mock.patch("pcs.lib.pcs_cfgsync.config.facade.time.time", lambda: 1000)
    def test_paused_still_paused(self):
        facade = CfgsyncFacade({"thread_paused_until": 2000})
        self.assertFalse(facade.is_sync_allowed)
        self.assertTrue(facade.is_sync_paused)

    @mock.patch("pcs.lib.pcs_cfgsync.config.facade.time.time", lambda: 1000)
    def test_paused_no_longer_paused(self):
        facade = CfgsyncFacade({"thread_paused_until": 500})
        self.assertTrue(facade.is_sync_allowed)
        self.assertFalse(facade.is_sync_paused)

    @mock.patch("pcs.lib.pcs_cfgsync.config.facade.time.time", lambda: 1000)
    def test_file_with_incorrect_values(self):
        facade = CfgsyncFacade(
            {
                "thread_disabled": "a",
                "thread_interval": "b",
                "thread_interval_previous_not_connected": "c",
                "file_backup_count": "d",
                "thread_paused_until": "e",
            }
        )
        self.assert_all_default_values(facade)

    def test_enable_disable_sync(self):
        facade = CfgsyncFacade.create()

        self.assertTrue(facade.is_sync_allowed)
        facade.disable_sync()
        self.assertFalse(facade.is_sync_allowed)
        facade.enable_sync()
        self.assertTrue(facade.is_sync_allowed)

    @mock.patch("pcs.lib.pcs_cfgsync.config.facade.time.time", lambda: 1000)
    def test_resume_pause_sync(self):
        facade = CfgsyncFacade.create()

        self.assertFalse(facade.is_sync_paused)
        facade.pause_sync(300)
        self.assertTrue(facade.is_sync_paused)
        facade.resume_sync()
        self.assertFalse(facade.is_sync_paused)
