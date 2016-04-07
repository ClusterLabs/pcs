from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import shutil
from unittest import TestCase

from pcs.test.tools.resources import get_test_resource as rc
from pcs.test.pcs_test_functions import pcs, ac

coro_conf = rc("corosync.conf")
temp_conf = rc("corosync.conf.tmp")

class QuorumUpdateCmdTest(TestCase):
    # TODO use "quorum config" command to test effect of "quorum update" command
    def setUp(self):
        shutil.copy(coro_conf, temp_conf)

    def cmd(self, cmd):
        return "--corosync_conf={path} {cmd}".format(path=temp_conf, cmd=cmd)

    def test_no_options(self):
        output, retval = pcs(self.cmd("quorum update"))
        self.assertTrue(output.startswith(
            "\nUsage: pcs quorum <command>\n    update "
        ))
        self.assertEqual(1, retval)

    def test_invalid_option(self):
        output, retval = pcs(self.cmd("quorum update nonsense=invalid"))
        ac(
            "Error: invalid quorum option 'nonsense', allowed options are: "
                + "auto_tie_breaker or last_man_standing or "
                + "last_man_standing_window or wait_for_all\n"
            ,
            output
        )
        self.assertEqual(1, retval)

    def test_invalid_value(self):
        output, retval = pcs(self.cmd("quorum update wait_for_all=invalid"))
        ac(
            "Error: 'invalid' is not a valid value for wait_for_all"
                + ", use 0 or 1\n"
            ,
            output
        )
        self.assertEqual(1, retval)

    def test_success(self):
        output, retval = pcs(self.cmd("quorum update wait_for_all=1"))
        ac("", output)
        self.assertEqual(0, retval)
        ac(
            open(temp_conf).read(),
            open(coro_conf).read().replace(
                "provider: corosync_votequorum",
                "provider: corosync_votequorum\n    wait_for_all: 1"
            )
        )
