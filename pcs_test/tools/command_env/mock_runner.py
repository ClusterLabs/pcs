from os import path

from pcs import settings

from pcs_test.tools.assertions import assert_xml_equal

# pylint: disable=unused-argument

CALL_TYPE_RUNNER = "CALL_TYPE_RUNNER"


class CheckStdinEqual:
    def __init__(self, expected_stdin):
        self.expected_stdin = expected_stdin

    def __call__(self, stdin, command, order_num):
        if stdin != self.expected_stdin:
            raise AssertionError(
                (
                    "With command\n\n    '{0}'"
                    "\n\nexpected stdin:\n\n'{1}'"
                    "\n\nbut was:\n\n'{2}'"
                ).format(command, self.expected_stdin, stdin)
            )


class CheckStdinEqualXml:
    def __init__(self, expected_stdin):
        self.expected_stdin = expected_stdin

    def __call__(self, stdin, command, order_num):
        assert_xml_equal(
            self.expected_stdin,
            stdin,
            (
                "Trying to run command no. {0}"
                "\n\n    '{1}'\n\nwith expected xml stdin.\n"
            ).format(order_num, command),
        )


def check_no_stdin(stdin, command, order_num):
    if stdin:
        raise AssertionError(
            (
                "With command\n\n    '{0}'\n\nno stdin expected but was"
                "\n\n'{1}'"
            ).format(command, stdin)
        )


COMMAND_COMPLETIONS = {
    "cibadmin": path.join(settings.pacemaker_binaries, "cibadmin"),
    "corosync": path.join(settings.corosync_binaries, "corosync"),
    "corosync-cfgtool": path.join(
        settings.corosync_binaries, "corosync-cfgtool"
    ),
    "corosync-qdevice-net-certutil": path.join(
        settings.corosync_qdevice_binaries, "corosync-qdevice-net-certutil"
    ),
    "corosync-quorumtool": path.join(
        settings.corosync_binaries, "corosync-quorumtool"
    ),
    "crm_diff": path.join(settings.pacemaker_binaries, "crm_diff"),
    "crm_mon": path.join(settings.pacemaker_binaries, "crm_mon"),
    "crm_node": path.join(settings.pacemaker_binaries, "crm_node"),
    "crm_resource": path.join(settings.pacemaker_binaries, "crm_resource"),
    "crm_rule": path.join(settings.pacemaker_binaries, "crm_rule"),
    "crm_simulate": path.join(settings.pacemaker_binaries, "crm_simulate"),
    "crm_ticket": path.join(settings.pacemaker_binaries, "crm_ticket"),
    "crm_verify": path.join(settings.pacemaker_binaries, "crm_verify"),
    "iso8601": path.join(settings.pacemaker_binaries, "iso8601"),
    "sbd": settings.sbd_binary,
    "stonith_admin": path.join(settings.pacemaker_binaries, "stonith_admin"),
}


def complete_command(command):
    for shortcut, full_path in COMMAND_COMPLETIONS.items():
        if command[0] == shortcut:
            return [full_path] + command[1:]
    return command


def bad_call(order_num, expected_command, entered_command):
    return "As {0}. command expected\n    '{1}'\nbut was\n    '{2}'".format(
        order_num, expected_command, entered_command
    )


class Call:
    type = CALL_TYPE_RUNNER

    def __init__(
        self, command, stdout="", stderr="", returncode=0, check_stdin=None
    ):
        """
        callable check_stdin raises AssertionError when given stdin doesn't
            match
        """
        self.type = CALL_TYPE_RUNNER
        self.command = complete_command(command)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.check_stdin = check_stdin if check_stdin else check_no_stdin

    def __repr__(self):
        return str("<Runner '{0}' returncode='{1}'>").format(
            self.command, self.returncode
        )


class Runner:
    def __init__(self, call_queue=None, env_vars=None):
        self.__call_queue = call_queue
        self.__env_vars = env_vars if env_vars else {}

    @property
    def env_vars(self):
        return self.__env_vars

    def run(
        self, args, stdin_string=None, env_extend=None, binary_output=False
    ):
        i, call = self.__call_queue.take(CALL_TYPE_RUNNER, args)

        if args != call.command:
            raise self.__call_queue.error_with_context(
                bad_call(i, call.command, args)
            )

        call.check_stdin(stdin_string, args, i)
        return call.stdout, call.stderr, call.returncode
