import re

from pcs.common.tools import is_string, Version
from pcs.lib import reports
from pcs.lib.cib import sections
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import (
    sanitize_id,
    validate_id,
)
from pcs.lib.xml_tools import get_root

_VERSION_FORMAT = r"(?P<major>\d+)\.(?P<minor>\d+)(\.(?P<rev>\d+))?"

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

    #pacemaker creates an implicit resource for the pacemaker_remote connection,
    #which will be named the same as the value of the remote-node attribute of
    #the explicit resource. So the value of nvpair named "remote-node" is
    #considered to be id
    existing = get_root(tree).xpath("""
        (
            /cib/*[name()!="status"]
            |
            /*[name()!="cib"]
        )
        //*[
            (
                name()!="acl_target"
                and
                name()!="role"
                and
                @id="{0}"
            ) or (
                name()="primitive"
                and
                meta_attributes[
                    nvpair[
                        @name="remote-node"
                        and
                        @value="{0}"
                    ]
                ]
            )
        ]
    """.format(check_id))
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
    tag, context_element, element_id, none_if_id_unused=False, id_types=None
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
    list id_types optional list of descriptions for id / expected types of id
    """
    tag_list = [tag] if is_string(tag) else tag
    if id_types is None:
        id_type_list = tag_list
    elif is_string(id_types):
        id_type_list = [id_types]
    else:
        id_type_list = id_types

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
            id_type_list,
            context_element.tag,
            context_element.attrib.get("id", "")
        )
    )

def create_subelement_id(context_element, suffix, id_provider=None):
    proposed_id = sanitize_id(
        "{0}-{1}".format(context_element.get("id"), suffix)
    )
    if id_provider:
        return id_provider.allocate_id(proposed_id)
    return find_unique_id(context_element, proposed_id)

def check_new_id_applicable(tree, description, id):
    validate_id(id, description)
    validate_id_does_not_exist(tree, id)

def get_configuration(tree):
    """
    Return 'configuration' element from tree, raise LibraryError if missing
    tree cib etree node
    """
    return sections.get(tree, sections.CONFIGURATION)

def get_acls(tree):
    """
    Return 'acls' element from tree, create a new one if missing
    tree cib etree node
    """
    return sections.get(tree, sections.ACLS)

def get_alerts(tree):
    """
    Return 'alerts' element from tree, create a new one if missing
    tree -- cib etree node
    """
    return sections.get(tree, sections.ALERTS)

def get_constraints(tree):
    """
    Return 'constraint' element from tree
    tree cib etree node
    """
    return sections.get(tree, sections.CONSTRAINTS)

def get_fencing_topology(tree):
    """
    Return the 'fencing-topology' element from the tree
    tree -- cib etree node
    """
    return sections.get(tree, sections.FENCING_TOPOLOGY)

def get_nodes(tree):
    """
    Return 'nodes' element from the tree
    tree cib etree node
    """
    return sections.get(tree, sections.NODES)

def get_resources(tree):
    """
    Return the 'resources' element from the tree
    tree -- cib etree node
    """
    return sections.get(tree, sections.RESOURCES)

def _get_cib_version(cib, attribute, regexp, none_if_missing=False):
    version = cib.get(attribute)
    if version is None:
        if none_if_missing:
            return None
        raise LibraryError(reports.cib_load_error_invalid_format(
            "the attribute '{0}' of the element 'cib' is missing".format(
                attribute
            )
        ))
    match = regexp.match(version)
    if not match:
        raise LibraryError(reports.cib_load_error_invalid_format(
            (
                "the attribute '{0}' of the element 'cib' has an invalid"
                " value: '{1}'"
            ).format(attribute, version)
        ))
    return Version(
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("rev")) if match.group("rev") else None
    )

def get_pacemaker_version_by_which_cib_was_validated(cib):
    """
    Return version of pacemaker which validated specified cib as tree.
    Version is returned as an instance of pcs.common.tools.Version.
    Raises LibraryError on any failure.

    cib -- cib etree
    """
    return _get_cib_version(
        cib,
        "validate-with",
        re.compile(r"pacemaker-{0}".format(_VERSION_FORMAT))
    )

def get_cib_crm_feature_set(cib, none_if_missing=False):
    """
    Return crm_feature_set as pcs.common.tools.Version or raise LibraryError

    etree cib -- cib etree
    bool none_if_missing -- return None instead of raising when crm_feature_set
        is missing
    """
    return _get_cib_version(
        cib,
        "crm_feature_set",
        re.compile(_VERSION_FORMAT),
        none_if_missing=none_if_missing
    )
