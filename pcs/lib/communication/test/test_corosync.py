from unittest import TestCase, skip

class CheckCorosyncOffline(TestCase):
    """
    tested in:
        pcs.lib.test.test_env.PushCorosyncConfLiveNoQdeviceTest
        pcs.lib.commands.test.sbd.test_enable_sbd
    """

class DistributeCorosyncConf(TestCase):
    """
    tested in:
        pcs.lib.test.test_env.PushCorosyncConfLiveNoQdeviceTest
        pcs.lib.commands.test.sbd.test_enable_sbd
    """

@skip("Missing test for pcs.lib.communication.corosync.ReloadCorosyncConf")
class ReloadCorosyncConf(TestCase):
    def test_dummy(self):
        pass
