from __future__ import (
    absolute_import,
    division,
    print_function,
)

from lxml import etree

from pcs.test.tools import cib_modify
from pcs.test.tools.integration_lib import Call
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.xml import etree_to_str


CIB_FILENAME = "cib-empty.xml"

def modify_cib(cib_xml, modifiers=None, resources=None):
    """
    Apply modifiers to cib_xml and return the result cib_xml

    string cib_xml -- initial cib
    list of callable modifiers -- each takes cib (etree.Element)
    string resources -- xml - resources section, current resources section will
        be replaced by this
    """
    modifiers = modifiers if modifiers else []
    if resources:
        modifiers.append(
            cib_modify.replace_element(".//resources", resources)
        )

    if not modifiers:
        return cib_xml

    cib_tree = etree.fromstring(cib_xml)
    for modify in modifiers:
        modify(cib_tree)

    return etree_to_str(cib_tree)

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
            Call("cibadmin --local --query", stdout=cib),
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
            Call(
                "cibadmin --replace --verbose --xml-pipe --scope configuration",
                check_stdin=Call.create_check_stdin_xml(cib),
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
            Call("cibadmin --upgrade --force"),
            before=before
        )
