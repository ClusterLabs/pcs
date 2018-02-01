from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.pcs_unittest import TestCase, skip


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


@skip("TODO: missing tests for pcs.lib.communication.booth.BoothSaveFiles")
class BoothSaveFiles(TestCase):
    def test_skip(self):
        pass
