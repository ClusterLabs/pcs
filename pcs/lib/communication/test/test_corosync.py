from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.lib.communication import corosync
from pcs.test.tools.pcs_unittest import TestCase

class DistributeCorosyncConf(TestCase):
    """
    tested in:
        pcs.lib.test.test_env.PushCorosyncConfLiveNoQdeviceTest
    """
