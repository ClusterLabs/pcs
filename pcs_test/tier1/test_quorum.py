from textwrap import dedent
from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import ParametrizedTestMetaClass
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner

# pylint: disable=line-too-long

coro_conf = rc("corosync.conf")
coro_qdevice_conf = rc("corosync-3nodes-qdevice.conf")
coro_qdevice_heuristics_conf = rc("corosync-3nodes-qdevice-heuristics.conf")


class TestBase(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_conf = get_tmp_file("tier1_quorum")
        write_file_to_tmpfile(coro_conf, self.temp_conf)
        # The tested commands work differently when non-live corosync.conf
        # (--corosync_conf) is used. In these tests it is not possible to cover
        # all the live config behavior, so we stick to using a non-live config.
        # Live behavior is tested in pcs_test.tier0.lib.commands.test_quorum.
        self.pcs_runner = PcsRunner(
            cib_file=None, corosync_conf_opt=self.temp_conf.name
        )

    def tearDown(self):
        self.temp_conf.close()

    def fixture_conf_qdevice(self):
        write_file_to_tmpfile(coro_qdevice_conf, self.temp_conf)

    def fixture_conf_qdevice_heuristics(self):
        write_file_to_tmpfile(coro_qdevice_heuristics_conf, self.temp_conf)


class QuorumConfigTest(TestBase):
    def test_no_device(self):
        self.assert_pcs_success("quorum config".split(), "")

    def test_with_device(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
                Device:
                  Model: net
                    host: 127.0.0.1
                """
            ),
        )


class QuorumUpdateTest(TestBase):
    def test_no_options(self):
        self.assert_pcs_fail(
            "quorum update".split(),
            stderr_start="\nUsage: pcs quorum <command>\n    update ",
        )

    def test_invalid_option(self):
        self.assert_pcs_fail(
            "quorum update nonsense=invalid".split(),
            (
                "Error: invalid quorum option 'nonsense', allowed options are: "
                "'auto_tie_breaker', 'last_man_standing', "
                "'last_man_standing_window', 'wait_for_all'\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_invalid_value(self):
        self.assert_pcs_fail(
            "quorum update wait_for_all=invalid".split(),
            (
                "Error: 'invalid' is not a valid wait_for_all value, use '0', "
                "'1'\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_success(self):
        self.assert_pcs_success("quorum config".split(), "")
        self.assert_pcs_success("quorum update wait_for_all=1".split())
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
                Options:
                  wait_for_all: 1
                """
            ),
        )


class DeviceAddTest(TestBase):
    def test_no_model_keyword(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device add option=value host=127.0.0.1".split(),
            stderr_start="\nUsage: pcs quorum <command>\n    device add ",
        )

    def test_no_model_value(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device add option=value model host=127.0.0.1".split(),
            stderr_start="\nUsage: pcs quorum <command>\n    device add ",
        )

    def test_more_models(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device add model net host=127.0.0.1 model disk".split(),
            "Error: 'model' cannot be used more than once\n",
        )

    def test_model_in_options(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device add model=disk model net host=127.0.0.1".split(),
            "Error: Model cannot be specified in generic options\n",
        )

    def test_more_heuristics(self):
        self.assert_pcs_fail_regardless_of_force(
            [
                "quorum",
                "device",
                "add",
                "model",
                "net",
                "host=127.0.0.1",
                "heuristics",
                "mode=on",
                "heuristics",
                "exec_ls=test -f /tmp/test",
            ],
            "Error: 'heuristics' cannot be used more than once\n",
        )

    def test_bad_keyword(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device add model net host=127.0.0.1 heuristic mode=on".split(),
            "Error: missing value of 'heuristic' option\n",
        )

    def test_device_already_set(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_fail_regardless_of_force(
            "quorum device add model net host=127.0.0.1".split(),
            "Error: quorum device is already defined\n",
        )

    def test_success_model_only(self):
        self.assert_pcs_success(
            "quorum device add model net host=127.0.0.1 algorithm=lms".split()
        )
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
                Device:
                  Model: net
                    algorithm: lms
                    host: 127.0.0.1
                """
            ),
        )

    def test_success_generic_and_model_options(self):
        self.assert_pcs_success(
            (
                "quorum device add timeout=12345 model net host=127.0.0.1 "
                "algorithm=ffsplit"
            ).split()
        )
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
                Device:
                  timeout: 12345
                  votes: 1
                  Model: net
                    algorithm: ffsplit
                    host: 127.0.0.1
                """
            ),
        )

    def test_success_model_options_and_heuristics(self):
        self.assert_pcs_success(
            [
                "quorum",
                "device",
                "add",
                "model",
                "net",
                "host=127.0.0.1",
                "algorithm=ffsplit",
                "heuristics",
                "mode=on",
                "exec_ls=test -f /tmp/test",
            ]
        )
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
                Device:
                  votes: 1
                  Model: net
                    algorithm: ffsplit
                    host: 127.0.0.1
                  Heuristics:
                    exec_ls: test -f /tmp/test
                    mode: on
                """
            ),
        )

    def test_success_model_options_and_heuristics_no_exec(self):
        self.assert_pcs_success(
            (
                "quorum device add model net host=127.0.0.1 algorithm=ffsplit "
                "heuristics mode=on"
            ).split(),
            stderr_full=(
                "Warning: No exec_NAME options are specified, so heuristics are "
                "effectively disabled\n"
            ),
        )
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
                Device:
                  votes: 1
                  Model: net
                    algorithm: ffsplit
                    host: 127.0.0.1
                  Heuristics:
                    mode: on
                """
            ),
        )

    def test_success_all_options(self):
        self.assert_pcs_success(
            [
                "quorum",
                "device",
                "add",
                "timeout=12345",
                "model",
                "net",
                "host=127.0.0.1",
                "tls=required",
                "keep_active_partition_tie_breaker=on",
                "algorithm=ffsplit",
                "heuristics",
                "mode=on",
                "exec_ls=test -f /tmp/test",
            ]
        )
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
                Device:
                  timeout: 12345
                  votes: 1
                  Model: net
                    algorithm: ffsplit
                    host: 127.0.0.1
                    keep_active_partition_tie_breaker: on
                    tls: required
                  Heuristics:
                    exec_ls: test -f /tmp/test
                    mode: on
                """
            ),
        )

    def test_missing_required_options(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device add model net".split(),
            [
                "Error: required quorum device model options 'algorithm', 'host' are missing",
                "Error: Errors have occurred, therefore pcs is unable to continue",
            ],
        )

    def test_bad_options(self):
        self.assert_pcs_fail(
            (
                "quorum device add a=b timeout=-1 model net host=127.0.0.1 "
                "algorithm=x c=d heuristics mode=bad e=f"
            ).split(),
            stderr_full=(
                dedent(
                    """\
                    Error: invalid quorum device model option 'c', allowed options are: 'algorithm', 'connect_timeout', 'force_ip_version', 'host', 'keep_active_partition_tie_breaker', 'port', 'tie_breaker', 'tls', use --force to override
                    Error: 'x' is not a valid algorithm value, use 'ffsplit', 'lms', use --force to override
                    Error: invalid quorum device option 'a', allowed options are: 'sync_timeout', 'timeout', use --force to override
                    Error: '-1' is not a valid timeout value, use a positive integer, use --force to override
                    Error: invalid heuristics option 'e', allowed options are: 'interval', 'mode', 'sync_timeout', 'timeout' and options matching patterns: 'exec_NAME', use --force to override
                    Error: 'bad' is not a valid mode value, use 'off', 'on', 'sync', use --force to override
                    Error: Errors have occurred, therefore pcs is unable to continue
                    """
                )
            ),
        )

        self.assert_pcs_success(
            (
                "quorum device add a=b timeout=-1 model net host=127.0.0.1 "
                "algorithm=x c=d heuristics mode=bad e=f --force"
            ).split(),
            stderr_full=(
                dedent(
                    """\
                    Warning: invalid quorum device model option 'c', allowed options are: 'algorithm', 'connect_timeout', 'force_ip_version', 'host', 'keep_active_partition_tie_breaker', 'port', 'tie_breaker', 'tls'
                    Warning: 'x' is not a valid algorithm value, use 'ffsplit', 'lms'
                    Warning: invalid quorum device option 'a', allowed options are: 'sync_timeout', 'timeout'
                    Warning: '-1' is not a valid timeout value, use a positive integer
                    Warning: invalid heuristics option 'e', allowed options are: 'interval', 'mode', 'sync_timeout', 'timeout' and options matching patterns: 'exec_NAME'
                    Warning: 'bad' is not a valid mode value, use 'off', 'on', 'sync'
                    """
                )
            ),
        )
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
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
            ),
        )

    def test_bad_model(self):
        self.assert_pcs_fail(
            "quorum device add model invalid x=y".split(),
            [
                "Error: 'invalid' is not a valid model value, use 'net', use --force to override",
                "Error: Errors have occurred, therefore pcs is unable to continue",
            ],
        )
        self.assert_pcs_success(
            "quorum device add model invalid x=y --force".split(),
            stderr_full=(
                "Warning: 'invalid' is not a valid model value, use 'net'\n"
            ),
        )
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
                Device:
                  Model: invalid
                    x: y
                """
            ),
        )


class DeviceDeleteRemoveTest(TestBase):
    command = None

    def _test_no_device(self):
        self.assert_pcs_fail(
            ["quorum", "device", self.command],
            "Error: no quorum device is defined in this cluster\n",
        )

    def _test_success(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(["quorum", "device", self.command])
        self.assert_pcs_success("quorum config".split(), "")

    def _test_bad_options(self):
        self.assert_pcs_fail(
            ["quorum", "device", self.command, "net"],
            stderr_start=dedent(
                f"""
                Usage: pcs quorum <command>
                    device {self.command}
                """
            ),
        )


class DeviceDeleteTest(
    DeviceDeleteRemoveTest, metaclass=ParametrizedTestMetaClass
):
    command = "delete"


class DeviceRemoveTest(
    DeviceDeleteRemoveTest, metaclass=ParametrizedTestMetaClass
):
    command = "remove"


class DeviceHeuristicsDeleteRemove(TestBase):
    command = None

    def _test_no_device(self):
        self.assert_pcs_fail(
            ["quorum", "device", "heuristics", self.command],
            "Error: no quorum device is defined in this cluster\n",
        )

    def _test_bad_options(self):
        self.assert_pcs_fail(
            ["quorum", "device", "heuristics", self.command, "option"],
            stderr_start=dedent(
                f"""
                Usage: pcs quorum <command>
                    device heuristics {self.command}
                """
            ),
        )

    def _test_success(self):
        self.fixture_conf_qdevice_heuristics()
        self.assert_pcs_success(
            ["quorum", "device", "heuristics", self.command]
        )
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
                Device:
                  Model: net
                    host: 127.0.0.1
                """
            ),
        )


class DeviceHeuristicsDelete(
    DeviceHeuristicsDeleteRemove, metaclass=ParametrizedTestMetaClass
):
    command = "delete"


class DeviceHeuristicsRemove(
    DeviceHeuristicsDeleteRemove, metaclass=ParametrizedTestMetaClass
):
    command = "remove"


class DeviceUpdateTest(TestBase):
    def test_no_device(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device update option=new_value model host=127.0.0.2".split(),
            "Error: no quorum device is defined in this cluster\n",
        )

    def test_generic_options_change(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success("quorum device update timeout=12345".split())
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
                Device:
                  timeout: 12345
                  Model: net
                    host: 127.0.0.1
                """
            ),
        )

    def test_model_options_change(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(
            "quorum device update model host=127.0.0.2".split()
        )
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
                Device:
                  Model: net
                    host: 127.0.0.2
                """
            ),
        )

    def test_heuristic_options_change(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(
            [
                "quorum",
                "device",
                "update",
                "heuristics",
                "mode=on",
                "exec_ls=test -f /tmp/tst",
            ]
        )
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
                Device:
                  Model: net
                    host: 127.0.0.1
                  Heuristics:
                    exec_ls: test -f /tmp/tst
                    mode: on
                """
            ),
        )

    def test_heuristic_options_change_no_exec(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(
            "quorum device update heuristics mode=on".split(),
            stderr_full=(
                "Warning: No exec_NAME options are specified, so heuristics are "
                "effectively disabled\n"
            ),
        )
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
                Device:
                  Model: net
                    host: 127.0.0.1
                  Heuristics:
                    mode: on
                """
            ),
        )

    def test_all_options_change(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_success(
            [
                "quorum",
                "device",
                "update",
                "timeout=12345",
                "model",
                "host=127.0.0.2",
                "port=1",
                "heuristics",
                "mode=on",
                "exec_ls=test -f /tmp/test",
            ]
        )
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
                Device:
                  timeout: 12345
                  Model: net
                    host: 127.0.0.2
                    port: 1
                  Heuristics:
                    exec_ls: test -f /tmp/test
                    mode: on
                """
            ),
        )

    def test_more_heuristics(self):
        self.assert_pcs_fail_regardless_of_force(
            [
                "quorum",
                "device",
                "update",
                "model",
                "host=127.0.0.1",
                "heuristics",
                "mode=on",
                "heuristics",
                "exec_ls=test -f /tmp/test",
            ],
            "Error: 'heuristics' cannot be used more than once\n",
        )

    def test_bad_keyword(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device update model host=127.0.0.1 heuristic mode=on".split(),
            "Error: missing value of 'heuristic' option\n",
        )

    def test_more_models(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device update model host=127.0.0.2 model port=1".split(),
            "Error: 'model' cannot be used more than once\n",
        )

    def test_model_in_options(self):
        self.assert_pcs_fail_regardless_of_force(
            "quorum device update model=disk".split(),
            "Error: Model cannot be specified in generic options\n",
        )

    def test_missing_required_options(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_fail_regardless_of_force(
            "quorum device update model host=".split(),
            (
                "Error: host cannot be empty, use a qdevice host address\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_bad_options(self):
        self.fixture_conf_qdevice()
        self.assert_pcs_fail(
            "quorum device update a=b timeout=-1 model port=x c=d".split(),
            (
                "Error: invalid quorum device model option 'c', allowed "
                "options are: 'algorithm', 'connect_timeout', "
                "'force_ip_version', 'host', 'keep_active_partition_tie_breaker',"
                " 'port', 'tie_breaker', 'tls', use --force to override\n"
                "Error: 'x' is not a valid port value, use a port number "
                "(1..65535), use --force to override\n"
                "Error: invalid quorum device option 'a', allowed options are: "
                "'sync_timeout', 'timeout', use --force to override\n"
                "Error: '-1' is not a valid timeout value, use a positive "
                "integer, use --force to override\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_pcs_success(
            "quorum device update a=b timeout=-1 model port=x c=d --force".split(),
            stderr_full=(
                dedent(
                    """\
                    Warning: invalid quorum device model option 'c', allowed options are: 'algorithm', 'connect_timeout', 'force_ip_version', 'host', 'keep_active_partition_tie_breaker', 'port', 'tie_breaker', 'tls'
                    Warning: 'x' is not a valid port value, use a port number (1..65535)
                    Warning: invalid quorum device option 'a', allowed options are: 'sync_timeout', 'timeout'
                    Warning: '-1' is not a valid timeout value, use a positive integer
                    """
                )
            ),
        )
        self.assert_pcs_success(
            "quorum config".split(),
            dedent(
                """\
                Device:
                  a: b
                  timeout: -1
                  Model: net
                    c: d
                    host: 127.0.0.1
                    port: x
                """
            ),
        )
