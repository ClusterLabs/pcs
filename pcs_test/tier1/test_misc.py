import os
from unittest import TestCase

from pcs.common import const
from pcs.common.str_tools import format_list

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_dir,
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
        self.temp_cib = get_tmp_file("tier1_misc_dashdash")
        write_file_to_tmpfile(rc("cib-empty.xml"), self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.allowed_roles = format_list(const.PCMK_ROLES)

    def tearDown(self):
        self.temp_cib.close()

    def test_negative_int(self):
        self.assert_pcs_fail(
            self.cmd + ["-123"],
            outdent(
                """\
                Deprecation Warning: Using '-123' without '--' is deprecated, those parameters will be considered position independent options in future pcs versions
                Deprecation Warning: Specifying score as a standalone value is deprecated and might be removed in a future release, use score=value instead
                Error: Resource 'R1' does not exist
                """
            ),
        )

    def test_negative_float(self):
        self.assert_pcs_fail(
            self.cmd + ["-12.3"],
            outdent(
                f"""\
                Deprecation Warning: Using '-12.3' without '--' is deprecated, those parameters will be considered position independent options in future pcs versions
                Error: invalid role value 'R2', allowed values are: {self.allowed_roles}
                """
            ),
        )

    def test_negative_infinity(self):
        self.assert_pcs_fail(
            self.cmd + ["-inFIniTY"],
            outdent(
                f"""\
                Deprecation Warning: Using '-inFIniTY' without '--' is deprecated, those parameters will be considered position independent options in future pcs versions
                Error: invalid role value 'R2', allowed values are: {self.allowed_roles}
                """
            ),
        )

    def test_negative_int_dash_dash(self):
        self.assert_pcs_fail(
            ["--"] + self.cmd + ["-123"],
            outdent(
                """\
                Deprecation Warning: Specifying score as a standalone value is deprecated and might be removed in a future release, use score=value instead
                Error: Resource 'R1' does not exist
                """
            ),
        )

    def test_negative_float_dash_dash(self):
        self.assert_pcs_fail(
            ["--"] + self.cmd + ["-12.3"],
            outdent(
                f"""\
                Error: invalid role value 'R2', allowed values are: {self.allowed_roles}
                """
            ),
        )

    def test_negative_infinity_dash_dash(self):
        self.assert_pcs_fail(
            ["--"] + self.cmd + ["-inFIniTY"],
            outdent(
                f"""\
                Error: invalid role value 'R2', allowed values are: {self.allowed_roles}
                """
            ),
        )


class EmptyCibIsPcmk2Compatible(TestCase, AssertPcsMixin):
    # This test verifies that a default empty CIB created by pcs when -f points
    # to an empty file conforms to minimal schema version supported by
    # pacemaker 2.0. If pcs prints a message that CIB schema has been upgraded,
    # then the test fails and shows there is a bug. Bundle with promoted-max
    # requires CIB compliant with schema 3.1, which was introduced in pacemaker
    # 2.0.0.
    def setUp(self):
        self.cib_dir = get_tmp_dir("tier1_misc_empty_cib")
        self.pcs_runner = PcsRunner(os.path.join(self.cib_dir.name, "cib.xml"))

    def tearDown(self):
        self.cib_dir.cleanup()

    def test_success(self):
        self.assert_pcs_success(
            "resource bundle create b container docker image=my.img promoted-max=1".split(),
            "",
        )
