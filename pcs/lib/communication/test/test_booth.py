from unittest import TestCase


class BoothSendConfig(TestCase):
    """
    tested in:
        pcs.lib.commands.test.test_booth.ConfigSyncTest
    """

class BoothGetConfig(TestCase):
    """
    tested in:
        pcs.lib.commands.test.test_booth.PullConfigSuccess
        pcs.lib.commands.test.test_booth.PullConfigFailure
        pcs.lib.commands.test.test_booth.PullConfigWithAuthfileSuccess
        pcs.lib.commands.test.test_booth.PullConfigWithAuthfileFailure
    """


class BoothSaveFiles(TestCase):
    """
    tested in:
        pcs.lib.commands.test.cluster.test_add_nodes.AddNodeFull
        pcs.lib.commands.test.cluster.test_add_nodes
            .FailureBoothConfigsDistribution
    """
