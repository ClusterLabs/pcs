from unittest import TestCase

from pcs.common import reports

from pcs_test.tier0.cli.resource.test_enable_disable import WaitMixin
from pcs_test.tools import cli_test_framework as ctf


def _call_is_any_resource_except_stonith(resource_ids, output=False):
    return ctf.LibCallSpec(
        "resource.is_any_resource_except_stonith",
        (resource_ids,),
        output=output,
    )


class StonithEnableWait(WaitMixin, TestCase):
    cli_cmd = "stonith enable S1 S2"
    type_check_call = _call_is_any_resource_except_stonith(["S1", "S2"])
    lib_call = ctf.LibCallSpec("resource.enable", (["S1", "S2"],))
    type_check_before_wait_parsing = False


class StonithDisableWait(WaitMixin, TestCase):
    cli_cmd = "stonith disable S1 S2"
    type_check_call = _call_is_any_resource_except_stonith(["S1", "S2"])
    lib_call = ctf.LibCallSpec("resource.disable", (["S1", "S2"], set()))
    type_check_before_wait_parsing = True


class StonithEnable(TestCase):
    def test_no_args(self):
        ctf.run(
            "stonith enable",
            exit_code=1,
            stderr="Error: You must specify stonith resource(s) to enable\n",
        )

    def test_one_resource(self):
        ctf.run(
            "stonith enable S1",
            [
                _call_is_any_resource_except_stonith(["S1"]),
                ctf.LibCallSpec("resource.enable", (["S1"],)),
            ],
            supported_flags=["--wait", "-f"],
        )

    def test_more_resources(self):
        ctf.run(
            "stonith enable S1 S2",
            [
                _call_is_any_resource_except_stonith(["S1", "S2"]),
                ctf.LibCallSpec("resource.enable", (["S1", "S2"],)),
            ],
        )

    def test_not_stonith_resource(self):
        ctf.run(
            "stonith enable S1 R1",
            _call_is_any_resource_except_stonith(["S1", "R1"], output=True),
            exit_code=1,
            stderr=(
                "Error: This command does not accept resources. "
                "Please use 'pcs resource enable' instead.\n"
            ),
        )

    def test_f_and_wait_mutually_exclusive(self):
        ctf.run(
            "stonith enable S1 --wait -f foo",
            exit_code=1,
            stderr="Error: Only one of '--wait', '-f' can be used\n",
        )


class StonithDisable(TestCase):
    def test_no_args(self):
        ctf.run(
            "stonith disable",
            exit_code=1,
            stderr="Error: You must specify stonith resource(s) to disable\n",
        )

    def test_one_resource(self):
        ctf.run(
            "stonith disable S1",
            [
                _call_is_any_resource_except_stonith(["S1"]),
                ctf.LibCallSpec("resource.disable", (["S1"], set())),
            ],
        )

    def test_more_resources(self):
        ctf.run(
            "stonith disable S1 S2",
            [
                _call_is_any_resource_except_stonith(["S1", "S2"]),
                ctf.LibCallSpec("resource.disable", (["S1", "S2"], set())),
            ],
        )

    def test_force(self):
        ctf.run(
            "stonith disable S1 --force",
            [
                _call_is_any_resource_except_stonith(["S1"]),
                ctf.LibCallSpec(
                    "resource.disable", (["S1"], {reports.codes.FORCE})
                ),
            ],
        )

    def test_not_stonith_resource(self):
        ctf.run(
            "stonith disable S1 R1",
            _call_is_any_resource_except_stonith(["S1", "R1"], output=True),
            exit_code=1,
            stderr=(
                "Error: This command does not accept resources. "
                "Please use 'pcs resource disable' instead.\n"
            ),
        )

    def test_f_and_wait_mutually_exclusive(self):
        ctf.run(
            "stonith disable S1 --wait -f foo",
            _call_is_any_resource_except_stonith(["S1"]),
            exit_code=1,
            stderr="Error: Only one of '--wait', '-f' can be used\n",
        )
