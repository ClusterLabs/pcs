from unittest import TestCase

class CheckCorosyncOffline(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.test_env.PushCorosyncConfLiveNoQdeviceTest
        pcs_test.tier0.lib.commands.sbd.test_enable_sbd
    """

class DistributeCorosyncConf(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.test_env.PushCorosyncConfLiveNoQdeviceTest
        pcs_test.tier0.lib.commands.sbd.test_enable_sbd
    """

class ReloadCorosyncConf(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.commands.cluster.test_add_nodes.{
            AddNodesSuccessMinimal
            AddNodeFull
        }   FailureReloadCorosyncConf
        pcs_test.tier0.lib.commands.cluster.test_remove_nodes
            .FailureCorosyncReload
    """
