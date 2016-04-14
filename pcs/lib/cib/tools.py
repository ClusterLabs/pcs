from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib import error_codes
from pcs.lib.errors import LibraryError, ReportItem
from pcs.lib.pacemaker_values import validate_id

def does_id_exist(tree, check_id):
    """
    Checks to see if id exists in the xml dom passed
    tree cib etree node
    check_id id to check
    """
    return tree.find('.//*[@id="{0}"]'.format(check_id)) is not None

def validate_id_does_not_exist(tree, id):
    """
    tree cib etree node
    """
    if does_id_exist(tree, id):
        raise LibraryError(ReportItem.error(
            error_codes.ID_ALREADY_EXISTS,
            '{id} already exists',
            info={'id': id}
        ))

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

def get_constraints(tree):
    """
    Return 'constraint' element from tree
    tree cib etree node
    """
    return tree.find(".//constraints")

def find_parent(element, tag_names):
    candidate = element
    while True:
        if candidate is None or candidate.tag in tag_names:
            return candidate
        candidate = candidate.getparent()

def export_attributes(element):
    return  dict((key, value) for key, value in element.attrib.items())

def check_new_id_applicable(tree, description, id):
    validate_id(id, description)
    validate_id_does_not_exist(tree, id)
