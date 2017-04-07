from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import re

from pcs.common.tools import is_string
from pcs.lib import reports
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import validate_id
from pcs.lib.xml_tools import (
    get_root,
    get_sub_element,
)

class IdProvider(object):
    """
    Book ids for future use in the CIB and generate new ids accordingly
    """
    def __init__(self, cib_element):
        """
        etree cib_element -- any element of the xml to being check against
        """
        self._cib = get_root(cib_element)
        self._booked_ids = set()

    def allocate_id(self, proposed_id):
        """
        Generate a new unique id based on the proposal and keep track of it
        string proposed_id -- requested id
        """
        final_id = find_unique_id(self._cib, proposed_id, self._booked_ids)
        self._booked_ids.add(final_id)
        return final_id

    def book_ids(self, *id_list):
        """
        Check if the ids are not already used and reserve them for future use
        strings *id_list -- ids
        """
        reported_ids = set()
        report_list = []
        for id in id_list:
            if id in reported_ids:
                continue
            if id in self._booked_ids or does_id_exist(self._cib, id):
                report_list.append(reports.id_already_exists(id))
                reported_ids.add(id)
                continue
            self._booked_ids.add(id)
        return report_list


def does_id_exist(tree, check_id):
    """
    Checks to see if id exists in the xml dom passed
    tree cib etree node
    check_id id to check
    """

    # do not search in /cib/status, it may contain references to previously
    # existing and deleted resources and thus preventing creating them again
    existing = get_root(tree).xpath(
        (
            '(/cib/*[name()!="status"]|/*[name()!="cib"])'
            '//*[name()!="acl_target" and name()!="role" and @id="{0}"]'
        ).format(check_id)
    )
    return len(existing) > 0

def validate_id_does_not_exist(tree, id):
    """
    tree cib etree node
    """
    if does_id_exist(tree, id):
        raise LibraryError(reports.id_already_exists(id))

def find_unique_id(tree, check_id, reserved_ids=None):
    """
    Returns check_id if it doesn't exist in the dom, otherwise it adds
    an integer to the end of the id and increments it until a unique id is found
    etree tree -- cib etree node
    string check_id -- id to check
    iterable reserved_ids -- ids to think about as already used
    """
    if not reserved_ids:
        reserved_ids = set()
    counter = 1
    temp_id = check_id
    while temp_id in reserved_ids or does_id_exist(tree, temp_id):
        temp_id = "{0}-{1}".format(check_id, counter)
        counter += 1
    return temp_id

def find_element_by_tag_and_id(
    tag, context_element, element_id, none_if_id_unused=False, id_description=""
):
    """
    Return element with given tag and element_id under context_element. When
    element does not exists raises LibraryError or return None if specified in
    none_if_id_unused.

    etree.Element(Tree) context_element is part of tree for element scan
    string|list tag is expected tag (or list of tags) of search element
    string element_id is id of search element
    bool none_if_id_unused if the element is not found then return None if True
        or raise a LibraryError if False
    string id_description optional description for id
    """
    tag_list = [tag] if is_string(tag) else tag
    element_list = context_element.xpath(
        './/*[({0}) and @id="{1}"]'.format(
            " or ".join(["self::{0}".format(one_tag) for one_tag in tag_list]),
            element_id
        )
    )

    if element_list:
        return element_list[0]

    element = get_root(context_element).find(
        './/*[@id="{0}"]'.format(element_id)
    )

    if element is not None:
        raise LibraryError(
            reports.id_belongs_to_unexpected_type(
                element_id,
                expected_types=tag_list,
                current_type=element.tag
            ) if element.tag not in tag_list
            else reports.object_with_id_in_unexpected_context(
                element.tag,
                element_id,
                context_element.tag,
                context_element.attrib.get("id", "")
            )
        )

    if none_if_id_unused:
        return None

    raise LibraryError(
        reports.id_not_found(
            element_id,
            id_description if id_description else "/".join(tag_list),
            context_element.tag,
            context_element.attrib.get("id", "")
        )
    )

def create_subelement_id(context_element, suffix):
    return find_unique_id(
        context_element,
        "{0}-{1}".format(context_element.get("id"), suffix)
    )

def check_new_id_applicable(tree, description, id):
    validate_id(id, description)
    validate_id_does_not_exist(tree, id)

def _get_mandatory_section(tree, section_name):
    """
    Return required element from tree, raise LibraryError if missing
    tree cib etree node
    """
    section = tree.find(".//{0}".format(section_name))
    if section is not None:
        return section
    raise LibraryError(reports.cib_missing_mandatory_section(section_name))

def get_configuration(tree):
    """
    Return 'configuration' element from tree, raise LibraryError if missing
    tree cib etree node
    """
    return _get_mandatory_section(tree, "configuration")

def get_acls(tree):
    """
    Return 'acls' element from tree, create a new one if missing
    tree cib etree node
    """
    return get_sub_element(get_configuration(tree), "acls")

def get_alerts(tree):
    """
    Return 'alerts' element from tree, create a new one if missing
    tree -- cib etree node
    """
    return get_sub_element(get_configuration(tree), "alerts")

def get_constraints(tree):
    """
    Return 'constraint' element from tree
    tree cib etree node
    """
    return _get_mandatory_section(tree, "configuration/constraints")

def get_fencing_topology(tree):
    """
    Return the 'fencing-topology' element from the tree
    tree -- cib etree node
    """
    return get_sub_element(get_configuration(tree), "fencing-topology")

def get_nodes(tree):
    """
    Return 'nodes' element from the tree
    tree cib etree node
    """
    return _get_mandatory_section(tree, "configuration/nodes")

def get_resources(tree):
    """
    Return the 'resources' element from the tree
    tree -- cib etree node
    """
    return _get_mandatory_section(tree, "configuration/resources")

def get_pacemaker_version_by_which_cib_was_validated(cib):
    """
    Return version of pacemaker which validated specified cib as tree.
    Version is returned as tuple of integers: (<major>, <minor>, <revision>).
    Raises LibraryError on any failure.

    cib -- cib etree
    """
    version = cib.get("validate-with")
    if version is None:
        raise LibraryError(reports.cib_load_error_invalid_format())

    regexp = re.compile(
        r"pacemaker-(?P<major>\d+)\.(?P<minor>\d+)(\.(?P<rev>\d+))?"
    )
    match = regexp.match(version)
    if not match:
        raise LibraryError(reports.cib_load_error_invalid_format())
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("rev") or 0)
    )
