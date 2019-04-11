from unittest import TestCase

class Stop(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.commands.test_quorum.RemoveDeviceNetTest
        pcs_test.tier0.lib.test_env.PushCorosyncConfLiveWithQdeviceTest
    """

class Start(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.commands.test_quorum.AddDeviceNetTest
        pcs_test.tier0.lib.test_env.PushCorosyncConfLiveWithQdeviceTest
    """

class Enable(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.commands.test_quorum.AddDeviceNetTest
    """

class Disable(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.commands.test_quorum.RemoveDeviceNetTest
    """
