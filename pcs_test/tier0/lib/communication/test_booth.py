from unittest import TestCase


class BoothSendConfig(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.commands.test_booth.ConfigSyncTest
    """

class BoothGetConfig(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.commands.test_booth.PullConfigSuccess
        pcs_test.tier0.lib.commands.test_booth.PullConfigFailure
        pcs_test.tier0.lib.commands.test_booth.PullConfigWithAuthfileSuccess
        pcs_test.tier0.lib.commands.test_booth.PullConfigWithAuthfileFailure
    """


class BoothSaveFiles(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.commands.cluster.test_add_nodes.AddNodeFull
        pcs_test.tier0.lib.commands.cluster.test_add_nodes
            .FailureBoothConfigsDistribution
    """
