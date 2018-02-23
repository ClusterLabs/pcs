from unittest import TestCase


class EnableSbdService(TestCase):
    """
    tested in:
        pcs.lib.commands.test.sbd.test_enable_sbd
    """

class DisableSbdService(TestCase):
    """
    tested in:
        pcs.lib.commands.test.sbd.test_disable_sbd.DisableSbd
    """

class RemoveStonithWatchdogTimeout(TestCase):
    """
    tested in:
        pcs.lib.commands.test.sbd.test_enable_sbd
    """

class SetStonithWatchdogTimeoutToZero(TestCase):
    """
    tested in:
        pcs.lib.commands.test.sbd.test_disable_sbd.DisableSbd
    """

class SetSbdConfig(TestCase):
    """
    tested in:
        pcs.lib.commands.test.sbd.test_enable_sbd
    """

class GetSbdConfig(TestCase):
    """
    tested in:
        pcs.lib.commands.test.sbd.test_get_cluster_sbd_config.GetClusterSbdConfig
    """

class GetSbdStatus(TestCase):
    """
    tested in:
        pcs.lib.commands.test.sbd.test_get_cluster_sbd_status.GetClusterSbdStatus
    """

class CheckSbd(TestCase):
    """
    tested in:
        pcs.lib.commands.test.sbd.test_enable_sbd
    """
