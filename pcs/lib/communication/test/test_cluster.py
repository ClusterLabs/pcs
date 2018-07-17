from unittest import TestCase

class Destroy(TestCase):
    """
    tested in:
        pcs.lib.commands.test.cluster.test_setup.SetupSuccessMinimal
        pcs.lib.commands.test.cluster.test_setup.SetupSuccessAddresses
        pcs.lib.commands.test.cluster.test_setup.Setup2NodeSuccessMinimal
        pcs.lib.commands.test.cluster.test_setup.SetupWithWait
        pcs.lib.commands.test.cluster.test_setup.Failures.test_cluster_destroy_failure
    """

class DestroyWarnOnFailure(TestCase):
    """
    tested in:
        pcs.lib.commands.test.cluster.test_remove_nodes.SuccessMinimal
        pcs.lib.commands.test.cluster.test_remove_nodes.FailureClusterDestroy
    """

class GetQuorumStatus(TestCase):
    """
    tested in:
        pcs.lib.commands.test.cluster.test_remove_nodes.SuccessMinimal
        pcs.lib.commands.test.cluster.test_remove_nodes.QuorumCheck
        pcs.lib.commands.test.cluster.test_remove_nodes.FailureQuorumLoss
    """
