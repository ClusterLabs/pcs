from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib import error_codes
from pcs.lib.errors import LibraryError, ReportItem

def does_id_exist(tree, check_id):
    """
    Checks to see if id exists in the xml dom passed
    tree cib etree node
    check_id id to check
    """
    return tree.find('.//*[@id="{0}"]'.format(check_id)) is not None

def find_unique_id(tree, check_id):
    """
    Returns check_id if it doesn't exist in the dom, otherwise it adds
    an integer to the end of the id and increments it until a unique id is found
    tree cib etree node
    check_id id to check
    """
    counter = 1
    temp_id = check_id
    while does_id_exist(tree, temp_id):
        temp_id = "{0}-{1}".format(check_id, counter)
        counter += 1
    return temp_id

def get_configuration(tree):
    """
    Return 'configuration' element from tree, raise LibraryError if missing
    tree cib etree node
    """
    conf = tree.find(".//configuration")
    if conf is not None:
        return conf
    raise LibraryError(ReportItem.error(
        error_codes.CIB_CANNOT_FIND_CONFIGURATION,
        "Unable to get configuration section of cib"
    ))

def get_acls(tree):
    """
    Return 'acls' element from tree, create a new one if missing
    tree cib etree node
    """
    acls = tree.find(".//acls")
    if acls is None:
        acls = etree.SubElement(get_configuration(tree), "acls")
    return acls
