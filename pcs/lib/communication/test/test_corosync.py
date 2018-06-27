from unittest import TestCase

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

class ReloadCorosyncConf(TestCase):
    """
    tested in:
        pcs.lib.commands.test.cluster.test_add_nodes.AddNodesSuccessMinimal
        pcs.lib.commands.test.cluster.test_add_nodes.AddNodeFull
        pcs.lib.commands.test.cluster.test_add_nodes.FailureReloadCorosyncConf
    """
