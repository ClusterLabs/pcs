from unittest import TestCase


class Destroy(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.commands.cluster.test_setup.SetupSuccessMinimal
        pcs_test.tier0.lib.commands.cluster.test_setup.SetupSuccessAddresses
        pcs_test.tier0.lib.commands.cluster.test_setup.Setup2NodeSuccessMinimal
        pcs_test.tier0.lib.commands.cluster.test_setup.SetupWithWait
        pcs_test.tier0.lib.commands.cluster.test_setup.Failures
            .test_cluster_destroy_failure
    """


class DestroyWarnOnFailure(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.commands.cluster.test_remove_nodes.SuccessMinimal
        pcs_test.tier0.lib.commands.cluster.test_remove_nodes
            .FailureClusterDestroy
    """


class GetQuorumStatus(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.commands.cluster.test_remove_nodes.SuccessMinimal
        pcs_test.tier0.lib.commands.cluster.test_remove_nodes.QuorumCheck
        pcs_test.tier0.lib.commands.cluster.test_remove_nodes.FailureQuorumLoss
    """
