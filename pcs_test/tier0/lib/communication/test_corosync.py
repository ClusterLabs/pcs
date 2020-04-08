from unittest import TestCase


class CheckCorosyncOffline(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.test_env.PushCorosyncConfLiveNoQdeviceTest
    """


class DistributeCorosyncConf(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.test_env.PushCorosyncConfLiveNoQdeviceTest
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
        pcs_test.tier0.lib.test_env
    """
