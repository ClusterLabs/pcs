from unittest import TestCase


class GetOnlineTargets(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.commands.sbd.test_enable_sbd
    """

class SendPcsdSslCertAndKey(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.commands.cluster.test_setup
        pcs_test.tier0.lib.commands.test_pcsd
    """

class RemoveNodesFromCib(TestCase):
    """
    tested in:
        pcs_test.tier0.lib.commands.cluster.test_remove_nodes.{
            RemoveNodesFailureFromCib
            RemoveNodesSuccessMinimal
        }
    """
