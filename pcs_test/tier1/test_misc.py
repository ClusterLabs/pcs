from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import (
    get_test_resource as rc,
    get_tmp_file,
    outdent,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


class ParseArgvDashDash(TestCase, AssertPcsMixin):
    # The command will fail, that's ok. We are interested only in the argv
    # parsing.
    cmd = "constraint colocation add R1 with R2".split()

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_misc")
        write_file_to_tmpfile(rc("cib-empty.xml"), self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def test_negative_int(self):
        self.assert_pcs_fail(
            self.cmd + ["-123"],
            outdent(
                """\
                Error: Resource 'R1' does not exist
                Warning: Using '-123' without '--' is deprecated, those parameters will be considered position independent options in future pcs versions
                """
            ),
        )

    def test_negative_float(self):
        self.assert_pcs_fail(
            self.cmd + ["-12.3"],
            outdent(
                """\
                Error: invalid role value 'R2', allowed values are: 'Master', 'Slave', 'Started', 'Stopped'
                Warning: Using '-12.3' without '--' is deprecated, those parameters will be considered position independent options in future pcs versions
                """
            ),
        )

    def test_negative_infinity(self):
        self.assert_pcs_fail(
            self.cmd + ["-inFIniTY"],
            outdent(
                """\
                Error: invalid role value 'R2', allowed values are: 'Master', 'Slave', 'Started', 'Stopped'
                Warning: Using '-inFIniTY' without '--' is deprecated, those parameters will be considered position independent options in future pcs versions
                """
            ),
        )

    def test_negative_int_dash_dash(self):
        self.assert_pcs_fail(
            ["--"] + self.cmd + ["-123"],
            outdent(
                """\
                Error: Resource 'R1' does not exist
                """
            ),
        )

    def test_negative_float_dash_dash(self):
        self.assert_pcs_fail(
            ["--"] + self.cmd + ["-12.3"],
            outdent(
                """\
                Error: invalid role value 'R2', allowed values are: 'Master', 'Slave', 'Started', 'Stopped'
                """
            ),
        )

    def test_negative_infinity_dash_dash(self):
        self.assert_pcs_fail(
            ["--"] + self.cmd + ["-inFIniTY"],
            outdent(
                """\
                Error: invalid role value 'R2', allowed values are: 'Master', 'Slave', 'Started', 'Stopped'
                """
            ),
        )
