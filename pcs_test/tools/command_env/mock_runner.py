from pcs import settings

from pcs_test.tools.assertions import assert_xml_equal

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
    del order_num
    if stdin:
        raise AssertionError(
            (
                "With command\n\n    '{0}'\n\nno stdin expected but was"
                "\n\n'{1}'"
            ).format(command, stdin)
        )


COMMAND_COMPLETIONS = {
    "cibadmin": settings.cibadmin_exec,
    "corosync": settings.corosync_exec,
    "corosync-cfgtool": settings.corosync_cfgtool_exec,
    "corosync-qdevice-net-certutil": settings.corosync_qdevice_net_certutil_exec,
    "corosync-quorumtool": settings.corosync_quorumtool_exec,
    "crm_diff": settings.crm_diff_exec,
    "crm_mon": settings.crm_mon_exec,
    "crm_node": settings.crm_node_exec,
    "crm_resource": settings.crm_resource_exec,
    "crm_rule": settings.crm_rule_exec,
    "crm_simulate": settings.crm_simulate_exec,
    "crm_ticket": settings.crm_ticket_exec,
    "crm_verify": settings.crm_verify_exec,
    "iso8601": settings.iso8601_exec,
    "sbd": settings.sbd_exec,
    "stonith_admin": settings.stonith_admin_exec,
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
        self,
        command,
        stdout="",
        stderr="",
        returncode=0,
        check_stdin=None,
        env=None,
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
        self.env = env or {}

    def __repr__(self):
        return str("<Runner '{0}' returncode='{1}' env='{2}'>").format(
            self.command, self.returncode, self.env
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
        del binary_output
        i, call = self.__call_queue.take(CALL_TYPE_RUNNER, args)

        if args != call.command:
            raise self.__call_queue.error_with_context(
                bad_call(i, call.command, args)
            )

        call.check_stdin(stdin_string, args, i)
        env = dict(self.env_vars)
        if env_extend:
            env.update(env_extend)
        if env != call.env:
            raise self.__call_queue.error_with_context(
                f"Command #{i}: ENV doesn't match. Expected: {call.env}; Real: {env}"
            )
        return call.stdout, call.stderr, call.returncode
