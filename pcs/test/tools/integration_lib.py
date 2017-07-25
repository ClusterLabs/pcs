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

    def __repr__(self):
        #the "dict" with name and id is "written" inside string because in
        #python3 the order is not
        return str("<{0}.{1} '{2}' returncode='{3}'>").format(
            self.__module__,
            self.__class__.__name__,
            self.command,
            self.returncode
        )

class EffectQueue(object):
    def __init__(self, effect_list=[]):
        self.__effect_list = effect_list
        self.__index = 0

    def take(self, command, stdin_string):
        if self.__index >= len(self.__effect_list):
            raise IndexError("No remaining effect in the queue")
        self.__index += 1
        return self.__index, self.__effect_list[self.__index - 1]

    @property
    def remaining(self):
        return self.__effect_list[self.__index:]

    @property
    def taken(self):
        return self.__effect_list[:self.__index]

class Runner(object):
    def __init__(self, effect_queue=None):
        self.__effect_queue = effect_queue

    def run(
        self, args, stdin_string=None, env_extend=None, binary_output=False
    ):
        command = " ".join(args)
        if not self.__effect_queue.remaining:
            raise self.__extra_effect(
                command,
                stdin_string,
                self.__effect_queue.taken
            )

        ordnum, expected_run = self.__effect_queue.take(command, stdin_string)
        if command != expected_run.command:
            raise self.__bad_effect(ordnum, expected_run.command, command)

        expected_run.check_stdin(stdin_string, command, ordnum)
        return expected_run.result

    def __bad_effect(self, ordnum, expected_command, entered_command):
        return AssertionError(
            "As {0}. command expected\n\n    '{1}'\n\nbut was\n\n    '{2}'"
            .format(ordnum, expected_command, entered_command)
        )

    def __extra_effect(self, command, stdin_string, already_taken):
        return AssertionError(
            (
                "No next effect expected, but was:\n    '{command}'{stdin}\n"
                "already taken:\n{already_taken}"
            ).format(
                command=command,
                stdin=(
                    "" if not stdin_string else "\nwith stdin:\n\n{0}\n"
                    .format(stdin_string)
                ),
                already_taken="    " + "\n    ".join([
                    "'{0}'".format(run.command)
                    for run in already_taken
                ])
            )
        )

#TODO remove HeavyRunner when it is not used
class HeavyRunner(object):
    def __init__(self):
        self.set_runs([])

    def assert_everything_launched(self):
        if self.__effect_queue.remaining:
            raise AssertionError(
                "There are remaining expected commands: \n    '{0}'".format(
                    "'\n    '".join([
                        call.command
                        for call in self.__effect_queue.remaining
                    ])
                )
            )

    def run(
        self, args, stdin_string=None, env_extend=None, binary_output=False
    ):
        return self.__runner.run(args, stdin_string, env_extend, binary_output)

    def set_runs(self, run_list):
        self.__effect_queue = EffectQueue(run_list)
        self.__runner = Runner(self.__effect_queue)
