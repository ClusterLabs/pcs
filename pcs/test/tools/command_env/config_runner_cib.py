from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.command_env.mock_runner import(
    Call as RunnerCall,
    create_check_stdin_xml,
)
from pcs.test.tools.fixture import modify_cib
from pcs.test.tools.misc import get_test_resource as rc


CIB_FILENAME = "cib-empty.xml"


class CibShortcuts(object):
    def __init__(self, calls):
        """
        CallCollection calls -- provides access to call list
        """
        self.__calls = calls
        self.cib_filename = CIB_FILENAME

    def load(
        self,
        modifiers=None,
        name="load_cib",
        filename=None,
        before=None,
        **modifier_shortcuts
    ):
        """
        Create call for loading cib.

        string name -- key of the call
        list of callable modifiers -- every callable takes etree.Element and
            returns new etree.Element with desired modification.
        string filename -- points to file with cib in the content
        string resources -- xml - resources section, current resources section
            will be replaced by this
        string before -- key of call before which this new call is to be placed
        """
        filename = filename if filename else self.cib_filename
        cib = modify_cib(
            open(rc(filename)).read(),
            modifiers,
            **modifier_shortcuts
        )
        self.__calls.place(
            name,
            RunnerCall("cibadmin --local --query", stdout=cib),
            before=before,
        )

    def push(
        self,
        modifiers=None,
        name="push_cib",
        load_key="load_cib",
        instead=None,
        stderr="",
        returncode=0,
        **modifier_shortcuts
    ):
        """
        Create call for pushing cib.
        Cib is taken from the load call by default.

        string name -- key of the call
        list of callable modifiers -- every callable takes etree.Element and
            returns new etree.Element with desired modification.
        string load_key -- key of a call from which stdout can be cib taken
        string resources -- xml - resources section, current resources section
            will be replaced by this
        string instead -- key of call instead of which this new call is to be
            placed
        """
        cib = modify_cib(
            self.__calls.get(load_key).stdout,
            modifiers,
            **modifier_shortcuts
        )
        self.__calls.place(
            name,
            RunnerCall(
                "cibadmin --replace --verbose --xml-pipe --scope configuration",
                stderr=stderr,
                returncode=returncode,
                check_stdin=create_check_stdin_xml(cib),
            ),
            instead=instead,
        )

    def push_independent(
        self,
        cib,
        name="push_cib",
        instead=None,
    ):
        """
        Create call for pushing cib.
        Cib is specified as an argument.

        string name -- key of the call
        string cib -- whole cib to push
        string instead -- key of call instead of which this new call is to be
            placed
        """
        self.__calls.place(
            name,
            RunnerCall(
                "cibadmin --replace --verbose --xml-pipe --scope configuration",
                check_stdin=create_check_stdin_xml(cib),
            ),
            instead=instead,
        )

    def diff(
        self,
        cib_old_file,
        cib_new_file,
        name="diff_cib",
        stdout="resulting diff",
        stderr="",
        returncode=0
    ):
        """
        Create a call for diffing two CIBs stored in two files
        string cib_old_file -- path to a file with an old CIB
        string cib_new_file -- path to a file with a new CIB
        string name -- key of the call
        string stdout -- resulting diff
        string stderr -- error returned from the diff process
        int returncode -- exit code of the diff process
        """
        self.__calls.place(
            name,
            RunnerCall(
                "crm_diff --original {old} --new {new} --no-version".format(
                    old=cib_old_file, new=cib_new_file
                ),
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def push_diff(
        self,
        name="push_cib_diff",
        cib_diff="resulting diff",
        stdout="",
        stderr="",
        returncode=0
    ):
        """
        Create a call for pushing a diff of CIBs
        string name -- key of the call
        string cib_diff -- the diff of CIBs
        """
        self.__calls.place(
            name,
            RunnerCall(
                "cibadmin --patch --verbose --xml-pipe",
                check_stdin=create_check_stdin_xml(cib_diff),
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            ),
        )

    def upgrade(self, name="upgrade_cib", before=None):
        """
        Create call for upgrading cib.

        string name -- key of the call
        string before -- key of call before which this new call is to be placed
        """
        self.__calls.place(
            name,
            RunnerCall("cibadmin --upgrade --force"),
            before=before
        )
