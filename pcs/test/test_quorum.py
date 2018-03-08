import shutil
from textwrap import dedent
from unittest import TestCase

from pcs.test.tools.assertions import AssertPcsMixin
from pcs.test.tools.misc import (
    get_test_resource as rc,
)
from pcs.test.tools.pcs_runner import PcsRunner


coro_conf = rc("corosync.conf")
coro_qdevice_conf = rc("corosync-3nodes-qdevice.conf")
coro_qdevice_heuristics_conf = rc("corosync-3nodes-qdevice-heuristics.conf")
temp_conf = rc("corosync.conf.tmp")


class TestBase(TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(coro_conf, temp_conf)
        self.pcs_runner = PcsRunner(corosync_conf_file=temp_conf)

    def fixture_conf_qdevice(self):
        shutil.copy(coro_qdevice_conf, temp_conf)

    def fixture_conf_qdevice_heuristics(self):
        shutil.copy(coro_qdevice_heuristics_conf, temp_conf)


class QuorumConfigTest(TestBase):
    def test_no_device(self):
        self.assert_pcs_success(
            "quorum config",
            "Options:\n"
        )

    def test_with_device(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
Device:
  Model: net
    host: 127.0.0.1
"""
        )


class QuorumUpdateTest(TestBase):
    def test_no_options(self):
        self.assert_pcs_fail(
            "quorum update",
            stdout_start="\nUsage: pcs quorum <command>\n    update "
        )

    def test_invalid_option(self):
        self.assert_pcs_fail(
            "quorum update nonsense=invalid",
            "Error: invalid quorum option 'nonsense', allowed options are: "
                + "auto_tie_breaker, last_man_standing, "
                + "last_man_standing_window, wait_for_all\n"
        )

    def test_invalid_value(self):
        self.assert_pcs_fail(
            "quorum update wait_for_all=invalid",
            "Error: 'invalid' is not a valid wait_for_all value, use 0, 1\n"
        )

    def test_success(self):
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
"""
        )
        self.assert_pcs_success(
            "quorum update wait_for_all=1"
        )
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
  wait_for_all: 1
"""
        )


class DeviceAddTest(TestBase):
    def test_no_model_keyword(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device add option=value host=127.0.0.1",
            stdout_start="\nUsage: pcs quorum <command>\n    device add "
        )

    def test_no_model_value(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device add option=value model host=127.0.0.1",
            stdout_start="\nUsage: pcs quorum <command>\n    device add "
        )

    def test_more_models(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device add model net host=127.0.0.1 model disk",
            "Error: 'model' cannot be used more than once\n"
        )

    def test_model_in_options(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device add model=disk model net host=127.0.0.1",
            "Error: Model cannot be specified in generic options\n"
        )

    def test_more_heuristics(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device add model net host=127.0.0.1 heuristics mode=on "
                "heuristics 'exec_ls=test -f /tmp/test'"
            ,
            "Error: 'heuristics' cannot be used more than once\n"
        )

    def test_bad_keyword(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device add model net host=127.0.0.1 heuristic mode=on",
            "Error: missing value of 'heuristic' option\n"
        )

    def test_device_already_set(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_fail_regardless_of_force(
            "quorum device add model net host=127.0.0.1",
            "Error: quorum device is already defined\n"
        )

    def test_success_model_only(self):
        self.assert_pcs_success(
            "quorum device add model net host=127.0.0.1 algorithm=lms"
        )
        self.assert_pcs_success(
            "quorum config",
            dedent("""\
                Options:
                Device:
                  Model: net
                    algorithm: lms
                    host: 127.0.0.1
                """
            )
        )

    def test_succes_generic_and_model_options(self):
        self.assert_pcs_success(
            "quorum device add timeout=12345 model net host=127.0.0.1 "
                "algorithm=ffsplit"
        )
        self.assert_pcs_success(
            "quorum config",
            dedent("""\
                Options:
                Device:
                  timeout: 12345
                  votes: 1
                  Model: net
                    algorithm: ffsplit
                    host: 127.0.0.1
                """
            )
        )

    def test_succes_model_options_and_heuristics(self):
        self.assert_pcs_success(
            "quorum device add model net host=127.0.0.1 algorithm=ffsplit "
                "heuristics mode=on 'exec_ls=test -f /tmp/test'"
        )
        self.assert_pcs_success(
            "quorum config",
            dedent("""\
                Options:
                Device:
                  votes: 1
                  Model: net
                    algorithm: ffsplit
                    host: 127.0.0.1
                  Heuristics:
                    exec_ls: test -f /tmp/test
                    mode: on
                """
            )
        )

    def test_succes_model_options_and_heuristics_no_exec(self):
        self.assert_pcs_success(
            "quorum device add model net host=127.0.0.1 algorithm=ffsplit "
                "heuristics mode=on",
            "Warning: No exec_NAME options are specified, so heuristics are "
                "effectively disabled\n"
        )
        self.assert_pcs_success(
            "quorum config",
            dedent("""\
                Options:
                Device:
                  votes: 1
                  Model: net
                    algorithm: ffsplit
                    host: 127.0.0.1
                  Heuristics:
                    mode: on
                """
            )
        )

    def test_succes_all_options(self):
        self.assert_pcs_success(
            "quorum device add timeout=12345 model net host=127.0.0.1 "
                "algorithm=ffsplit "
                "heuristics mode=on 'exec_ls=test -f /tmp/test'"
        )
        self.assert_pcs_success(
            "quorum config",
            dedent("""\
                Options:
                Device:
                  timeout: 12345
                  votes: 1
                  Model: net
                    algorithm: ffsplit
                    host: 127.0.0.1
                  Heuristics:
                    exec_ls: test -f /tmp/test
                    mode: on
                """
            )
        )

    def test_missing_required_options(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device add model net",
            [
                "Error: required quorum device model option 'algorithm' is missing",
                "Error: required quorum device model option 'host' is missing",
            ]
        )

    def test_bad_options(self):
        self.assert_pcs_fail(
            "quorum device add a=b timeout=-1 model net host=127.0.0.1 "
                "algorithm=x c=d heuristics mode=bad e=f",
            """\
Error: 'x' is not a valid algorithm value, use ffsplit, lms, use --force to override
Error: invalid quorum device model option 'c', allowed options are: algorithm, connect_timeout, force_ip_version, host, port, tie_breaker, use --force to override
Error: '-1' is not a valid timeout value, use a positive integer, use --force to override
Error: invalid quorum device option 'a', allowed options are: sync_timeout, timeout, use --force to override
Error: 'bad' is not a valid mode value, use off, on, sync, use --force to override
Error: invalid heuristics option 'e', allowed options are: interval, mode, sync_timeout, timeout and options matching patterns: exec_NAME, use --force to override
"""
        )

        self.assert_pcs_success(
            "quorum device add a=b timeout=-1 model net host=127.0.0.1 "
                "algorithm=x c=d heuristics mode=bad e=f --force",
            """\
Warning: 'x' is not a valid algorithm value, use ffsplit, lms
Warning: invalid quorum device model option 'c', allowed options are: algorithm, connect_timeout, force_ip_version, host, port, tie_breaker
Warning: '-1' is not a valid timeout value, use a positive integer
Warning: invalid quorum device option 'a', allowed options are: sync_timeout, timeout
Warning: 'bad' is not a valid mode value, use off, on, sync
Warning: invalid heuristics option 'e', allowed options are: interval, mode, sync_timeout, timeout and options matching patterns: exec_NAME
"""
        )
        self.assert_pcs_success(
            "quorum config",
            dedent("""\
                Options:
                Device:
                  a: b
                  timeout: -1
                  Model: net
                    algorithm: x
                    c: d
                    host: 127.0.0.1
                  Heuristics:
                    e: f
                    mode: bad
                """
            )
        )

    def test_bad_model(self):
        self.assert_pcs_fail(
            "quorum device add model invalid x=y",
            "Error: 'invalid' is not a valid model value, use net, use --force to override\n"
        )
        self.assert_pcs_success(
            "quorum device add model invalid x=y --force",
            "Warning: 'invalid' is not a valid model value, use net\n"
        )
        self.assert_pcs_success(
            "quorum config",
            dedent("""\
                Options:
                Device:
                  Model: invalid
                    x: y
                """
            )
        )


class DeviceRemoveTest(TestBase):
    def test_no_device(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device remove",
            "Error: no quorum device is defined in this cluster\n"
        )

    def test_success(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(
            "quorum device remove"
        )
        self.assert_pcs_success(
            "quorum config",
            "Options:\n"
        )

    def test_bad_options(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device remove net",
            stdout_start="\nUsage: pcs quorum <command>\n    device remove\n"
        )


class DeviceHeuristicsRemove(TestBase):
    def test_no_device(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device heuristics remove",
            "Error: no quorum device is defined in this cluster\n"
        )

    def test_bad_options(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device heuristics remove option",
            stdout_start="\nUsage: pcs quorum <command>\n    device heuristics "
                "remove\n"
        )

    def test_success(self):
        self.fixture_conf_qdevice_heuristics()
        self.assert_pcs_success("quorum device heuristics remove")
        self.assert_pcs_success(
            "quorum config",
            dedent("""\
                Options:
                Device:
                  Model: net
                    host: 127.0.0.1
                """
            )
        )


class DeviceUpdateTest(TestBase):
    def test_no_device(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device update option=new_value model host=127.0.0.2",
            "Error: no quorum device is defined in this cluster\n"
        )

    def test_generic_options_change(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success("quorum device update timeout=12345")
        self.assert_pcs_success(
            "quorum config",
            dedent("""\
                Options:
                Device:
                  timeout: 12345
                  Model: net
                    host: 127.0.0.1
                """
            )
        )

    def test_model_options_change(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success("quorum device update model host=127.0.0.2")
        self.assert_pcs_success(
            "quorum config",
            dedent("""\
                Options:
                Device:
                  Model: net
                    host: 127.0.0.2
                """
            )
        )

    def test_heuristic_options_change(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(
            "quorum device update heuristics mode=on 'exec_ls=test -f /tmp/tst'"
        )
        self.assert_pcs_success(
            "quorum config",
            dedent("""\
                Options:
                Device:
                  Model: net
                    host: 127.0.0.1
                  Heuristics:
                    exec_ls: test -f /tmp/tst
                    mode: on
                """
            )
        )

    def test_heuristic_options_change_no_exec(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(
            "quorum device update heuristics mode=on",
            "Warning: No exec_NAME options are specified, so heuristics are "
                "effectively disabled\n"
        )
        self.assert_pcs_success(
            "quorum config",
            dedent("""\
                Options:
                Device:
                  Model: net
                    host: 127.0.0.1
                  Heuristics:
                    mode: on
                """
            )
        )

    def test_all_options_change(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(
            "quorum device update timeout=12345 model host=127.0.0.2 port=1 "
            "heuristics mode=on 'exec_ls=test -f /tmp/test'"
        )
        self.assert_pcs_success(
            "quorum config",
            dedent("""\
                Options:
                Device:
                  timeout: 12345
                  Model: net
                    host: 127.0.0.2
                    port: 1
                  Heuristics:
                    exec_ls: test -f /tmp/test
                    mode: on
                """
            )
        )

    def test_more_heuristics(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device update model host=127.0.0.1 heuristics mode=on "
                "heuristics 'exec_ls=test -f /tmp/test'"
            ,
            "Error: 'heuristics' cannot be used more than once\n"
        )

    def test_bad_keyword(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device update model host=127.0.0.1 heuristic mode=on",
            "Error: missing value of 'heuristic' option\n"
        )

    def test_more_models(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device update model host=127.0.0.2 model port=1",
            "Error: 'model' cannot be used more than once\n"
        )

    def test_model_in_options(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device update model=disk",
            "Error: Model cannot be specified in generic options\n"
        )

    def test_missing_required_options(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_fail_regardless_of_force(
            "quorum device update model host=",
            "Error: '' is not a valid host value, use a qdevice host address\n"
        )

    def test_bad_options(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_fail(
            "quorum device update a=b timeout=-1 model port=x c=d",
            """\
Error: 'x' is not a valid port value, use a port number (1-65535), use --force to override
Error: invalid quorum device model option 'c', allowed options are: algorithm, connect_timeout, force_ip_version, host, port, tie_breaker, use --force to override
Error: '-1' is not a valid timeout value, use a positive integer, use --force to override
Error: invalid quorum device option 'a', allowed options are: sync_timeout, timeout, use --force to override
"""
        )
        self.assert_pcs_success(
            "quorum device update a=b timeout=-1 model port=x c=d --force",
            """\
Warning: 'x' is not a valid port value, use a port number (1-65535)
Warning: invalid quorum device model option 'c', allowed options are: algorithm, connect_timeout, force_ip_version, host, port, tie_breaker
Warning: '-1' is not a valid timeout value, use a positive integer
Warning: invalid quorum device option 'a', allowed options are: sync_timeout, timeout
"""
        )
        self.assert_pcs_success(
            "quorum config",
            dedent("""\
                Options:
                Device:
                  a: b
                  timeout: -1
                  Model: net
                    c: d
                    host: 127.0.0.1
                    port: x
                """
            )
        )
