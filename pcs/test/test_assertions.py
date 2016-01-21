import difflib

from pcs_test_functions import pcs

def prepare_diff(first, second):
    return ''.join(
        difflib.Differ().compare(first.splitlines(1), second.splitlines(1))
    )


class AssertPcsMixin(object):
    def assert_pcs_success(self, command, stdout_start=None, stdout_full=None):
        full = stdout_full
        if stdout_start is None and stdout_full is None:
            full = ''

        self.assert_pcs_result(
            command,
            stdout_start=stdout_start,
            stdout_full=full
        )

    def assert_pcs_fail(self, command, stdout_start=None, stdout_full=None):
        self.assert_pcs_result(
            command,
            stdout_start=stdout_start,
            stdout_full=stdout_full,
            returncode=1
        )

    def assert_pcs_result(
        self, command, stdout_start=None, stdout_full=None, returncode=0
    ):
        msg = 'Please specify exactly one: stdout_start or stdout_full'
        if stdout_start is None and stdout_full is None:
            raise Exception(msg +', none specified')

        if stdout_start is not None and stdout_full is not None:
            raise Exception(msg +', both specified')

        stdout, pcs_returncode = self.pcs_runner.run(command)
        self.assertEqual(returncode, pcs_returncode)
        if stdout_start:
            if not stdout.startswith(stdout_start):
                self.assertTrue(
                    False,
                    'Stdout not start as expected, diff is (expected 2nd):\n'
                    +prepare_diff(stdout[:len(stdout_start)], stdout_start)
                )
        else:
            #unicode vs non-unicode not solved here
            if stdout != stdout_full:
                self.assertEqual(
                    stdout, stdout_full,
                    'Stdout is not as expected, diff is(expected 2nd):\n'
                    +prepare_diff(stdout, stdout_full)
                )
