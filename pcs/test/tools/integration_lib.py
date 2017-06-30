from __future__ import (
    absolute_import,
    division,
    print_function,
)

from os import path

from pcs.test.tools.assertions import assert_xml_equal

from pcs import settings

class Call(object):
    command_completions = {
        "crm_resource": path.join(settings.pacemaker_binaries, "crm_resource"),
        "cibadmin": path.join(settings.pacemaker_binaries, "cibadmin"),
        "crm_mon": path.join(settings.pacemaker_binaries, "crm_mon"),
        "sbd": settings.sbd_binary,
    }

    @staticmethod
    def create_check_stdin_xml(expected_stdin):
        def stdin_xml_check(stdin, command, order_num):
            assert_xml_equal(
                expected_stdin,
                stdin,
                (
                    "Trying to run command no. {0}"
                    "\n\n    '{1}'\n\nwith expected xml stdin.\n"
                ).format(order_num,  command)
            )
        return stdin_xml_check

    def __init__(
        self, command, stdout="", stderr="", returncode=0, check_stdin=None
    ):
        """
        callable check_stdin raises AssertionError when given stdin doesn't match
        """
        self.command = self.__complete_command(command)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.check_stdin = check_stdin if check_stdin else self.__check_no_stdin

    def __complete_command(self, command):
        for shortcut, full_path in self.command_completions.items():
            if command.startswith("{0} ".format(shortcut)):
                return full_path + command[len(shortcut):]
        return command

    def __check_no_stdin(self, stdin, command, order_num):
        if stdin:
            raise AssertionError(
                (
                    "With command\n\n    '{0}'\n\nno stdin expected but was"
                    "\n\n'{1}'"
                )
                .format(command, stdin)
            )

    @property
    def result(self):
        return self.stdout, self.stderr, self.returncode


class Runner(object):
    def __init__(self):
        self.set_runs([])

    def assert_can_take_next_run(self, command, stdin_string):
        if not self.run_list:
            raise AssertionError(
                (
                    "No next run expected, but was:\n    '{command}'{stdin}\n"
                    "already launched:\n{already_launched}"
                ).format(
                    command=command,
                    stdin=(
                        "" if not stdin_string else "\nwith stdin:\n\n{0}\n"
                        .format(stdin_string)
                    ),
                    already_launched="    " + "\n    ".join([
                        "'{0}'".format(run.command)
                        for run in self.already_launched_list
                    ])
                )
            )
        return self.run_list.pop(0)

    def assert_command_match(self, expected_command, entered_command):
        if entered_command != expected_command:
            raise AssertionError(
                "As {0}. command expected\n\n    '{1}'\n\nbut was\n\n    '{2}'"
                .format(
                    self.current_order_num,
                    expected_command,
                    entered_command
                )
            )

    def assert_everything_launched(self):
        if self.run_list:
            raise AssertionError(
                "There are remaining expected commands: \n    '{0}'".format(
                    "'\n    '".join([call.command for call in self.run_list])
                )
            )

    @property
    def current_order_num(self):
        return len(self.already_launched_list) + 1

    def run(
        self, args, stdin_string=None, env_extend=None, binary_output=False
    ):
        command = " ".join(args)
        next_run = self.assert_can_take_next_run(command, stdin_string)
        self.assert_command_match(next_run.command, command)
        next_run.check_stdin(stdin_string, command, self.current_order_num)
        self.already_launched_list.append(next_run)
        return next_run.result

    def set_runs(self, run_list):
        self.run_list = run_list
        self.already_launched_list = []
