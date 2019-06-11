import re

from pcs.common import report_codes
from pcs.common.tools import Version
from pcs.lib import reports
from pcs.lib.cib import sections
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import (
    sanitize_id,
    validate_id,
)
from pcs.lib.xml_tools import get_root, get_sub_element

VERSION_FORMAT = r"(?P<major>\d+)\.(?P<minor>\d+)(\.(?P<rev>\d+))?$"

class IdProvider:
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
        for _id in id_list:
            if _id in reported_ids:
                continue
            if _id in self._booked_ids or does_id_exist(self._cib, _id):
                report_list.append(reports.id_already_exists(_id))
                reported_ids.add(_id)
                continue
            self._booked_ids.add(_id)
        return report_list


class ElementSearcher():
    """
    Search for an element, allow to book its id if not found, provide reports

    Usage:
    es = ElementSearcher(element_tag, element_id, context_element)
    if es.element_found():
        # the element has been found
        element = es.get_element()
    # if you want to create the element when it does not exist
    elif es.validate_book_id(id_provider)
        element = Element(element_id)
    else:
        raise LibraryError(es.get_errors())
    """
    def __init__(
        self, tags, element_id, context_element, element_type_desc=None
    ):
        """
        string|iterable tags -- a tag (string) or tags (iterable) to look for
        string element_id -- an id to look for
        etree.Element context_element -- an element to look in
        string|iterable element_type_desc -- element types for reports, tags
            if not specified
        """
        self._executed = False
        self._element = None
        self._element_id = element_id
        self._context_element = context_element
        self._tag_list = [tags] if isinstance(tags, str) else tags
        self._expected_types = self._prepare_expected_types(element_type_desc)
        self._book_errors = None

    def _prepare_expected_types(self, element_type_desc):
        if element_type_desc is None:
            return self._tag_list
        if isinstance(element_type_desc, str):
            return [element_type_desc]
        return element_type_desc

    def element_found(self):
        if not self._executed:
            self._execute()
        return self._element is not None

    def get_element(self):
        if not self._executed:
            self._execute()
        return self._element

    def validate_book_id(self, id_provider, id_description="id"):
        """
        Book element_id in the id_provider, return True if success
        """
        self._book_errors = []
        validate_id(
            self._element_id,
            description=id_description,
            reporter=self._book_errors
        )
        if not self._book_errors:
            self._book_errors += id_provider.book_ids(self._element_id)
        return len(self._book_errors) < 1

    def get_errors(self):
        """
        Report why the element has not been found or booking its id failed
        """
        if (
            self.element_found()
            or
            (self._book_errors is not None and not self._book_errors)
        ):
            raise AssertionError(
                "Improper usage: cannot report errors when there are none"
            )

        element = get_root(self._context_element).find(
            f'.//*[@id="{self._element_id}"]'
        )

        if element is not None:
            if element.tag in self._tag_list:
                return [
                    reports.object_with_id_in_unexpected_context(
                        element.tag,
                        self._element_id,
                        self._context_element.tag,
                        self._context_element.attrib.get("id", "")
                    )
                ]
            return [
                reports.id_belongs_to_unexpected_type(
                    self._element_id,
                    expected_types=self._expected_types,
                    current_type=element.tag
                )
            ]
        if self._book_errors is None:
            return [
                reports.id_not_found(
                    self._element_id,
                    self._expected_types,
                    self._context_element.tag,
                    self._context_element.attrib.get("id", "")
                )
            ]
        return self._book_errors

    def _execute(self):
        self._executed = True
        for tag in self._tag_list:
            element_list = self._context_element.xpath(
                f'.//{tag}[@id="{self._element_id}"]'
            )
            if element_list:
                self._element = element_list[0]
                return


# DEPRECATED, use IdProvider instead
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

# DEPRECATED, use IdProvider instead
def validate_id_does_not_exist(tree, _id):
    """
    tree cib etree node
    """
    if does_id_exist(tree, _id):
        raise LibraryError(reports.id_already_exists(_id))

# DEPRECATED, use IdProvider instead
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

# DEPRECATED, use ElementSearcher instead
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
    searcher = ElementSearcher(
        tag, element_id, context_element, element_type_desc=id_types
    )
    if searcher.element_found():
        return searcher.get_element()
    report_list = searcher.get_errors()
    if not none_if_id_unused:
        raise LibraryError(*report_list)
    filtered_reports = [
        report_item for report_item in report_list
        if report_item.code != report_codes.ID_NOT_FOUND
    ]
    if filtered_reports:
        raise LibraryError(*filtered_reports)
    return None

def create_subelement_id(context_element, suffix, id_provider):
    proposed_id = sanitize_id(
        "{0}-{1}".format(context_element.get("id"), suffix)
    )
    return id_provider.allocate_id(proposed_id)

# DEPRECATED
# use ElementSearcher, IdProvider or pcs.lib.validate.ValueId instead
def check_new_id_applicable(tree, description, _id):
    validate_id(_id, description)
    validate_id_does_not_exist(tree, _id)

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

def get_status(tree):
    """
    Return the 'status' element from the tree
    tree -- cib etree node
    """
    return get_sub_element(tree, "status")

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
        re.compile(r"pacemaker-{0}".format(VERSION_FORMAT))
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
        re.compile(VERSION_FORMAT),
        none_if_missing=none_if_missing
    )
