from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import difflib

def prepare_diff(first, second):
    return ''.join(
        difflib.Differ().compare(first.splitlines(1), second.splitlines(1))
    )


class AssertPcsMixin(object):
    def assert_pcs_success(self, command, stdout_full=None, stdout_start=None):
        full = stdout_full
        if stdout_start is None and stdout_full is None:
            full = ''

        self.assert_pcs_result(
            command,
            stdout_full=full,
            stdout_start=stdout_start
        )

    def assert_pcs_fail(self, command, stdout_full=None, stdout_start=None):
        self.assert_pcs_result(
            command,
            stdout_full=stdout_full,
            stdout_start=stdout_start,
            returncode=1
        )

    def assert_pcs_result(
        self, command, stdout_full=None, stdout_start=None, returncode=0
    ):
        msg = 'Please specify exactly one: stdout_start or stdout_full'
        if stdout_start is None and stdout_full is None:
            raise Exception(msg +', none specified')

        if stdout_start is not None and stdout_full is not None:
            raise Exception(msg +', both specified')

        stdout, pcs_returncode = self.pcs_runner.run(command)
        self.assertEqual(
            returncode, pcs_returncode, (
                'Expected return code "{0}", but was "{1}"'
                +'\ncommand:\n{2}\nstdout:\n{3}'
            ).format(returncode, pcs_returncode, command, stdout)
        )
        if stdout_start:
            expected_start = '\n'.join(stdout_start)+'\n' \
                if isinstance(stdout_start, list) else stdout_start

            if not stdout.startswith(expected_start):
                self.assertTrue(
                    False,
                    'Stdout not start as expected\ncommand:\n'+command
                    +'\ndiff is (expected 2nd):\n'
                    +prepare_diff(stdout[:len(expected_start)], expected_start)
                    +'\nFull stdout:'+stdout
                )
        else:
            expected_full = '\n'.join(stdout_full)+'\n' \
                if isinstance(stdout_full, list) else stdout_full

            #unicode vs non-unicode not solved here
            if stdout != expected_full:
                self.assertEqual(
                    stdout, expected_full,
                    'Stdout is not as expected\ncommand:\n'+command
                    +'\n diff is(expected 2nd):\n'
                    +prepare_diff(stdout, expected_full)
                    +'\nFull stdout:'+stdout
                )
