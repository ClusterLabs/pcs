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
        resources=None
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
        cib = modify_cib(open(rc(filename)).read(), modifiers, resources)
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
        resources=None,
        instead=None,
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
            resources,
        )
        self.__calls.place(
            name,
            RunnerCall(
                "cibadmin --replace --verbose --xml-pipe --scope configuration",
                check_stdin=create_check_stdin_xml(cib),
            ),
            instead=instead,
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
