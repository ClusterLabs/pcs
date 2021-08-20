from typing import Dict, Iterable

from lxml import etree
from lxml.etree import _Element

from pcs.common import (
    const,
    pacemaker,
)


def get_root(tree):
    # ElementTree has getroot, Elemet has getroottree
    return tree.getroot() if hasattr(tree, "getroot") else tree.getroottree()


def find_parent(element, tag_names):
    """
    Find parent of an element based on parent's tag name. Return the parent
    element or None if such element does not exist.

    etree element -- the element whose parent we want to find
    strings tag_names -- allowed tag names of parent we are looking for
    """
    candidate = element
    while True:
        if candidate is None or candidate.tag in tag_names:
            return candidate
        candidate = candidate.getparent()


def get_sub_element(
    element,
    sub_element_tag,
    new_id=None,
    new_index=None,
    append_if_missing=True,
):
    """
    Returns the FIRST sub-element sub_element_tag of element. It will create new
    element if such doesn't exist yet.

    element -- parent element
    sub_element_tag -- tag of the wanted new element
    new_id -- id of the new element, None means no id will be set
    new_index -- where the new element will be added, None means at the end
    append_if_missing -- if the searched element does not exist, append it to
        the parent element
    """
    sub_element = element.find("./{0}".format(sub_element_tag))
    if sub_element is None:
        sub_element = etree.Element(sub_element_tag)
        if new_id:
            sub_element.set("id", new_id)
        if append_if_missing:
            if new_index is None:
                element.append(sub_element)
            else:
                element.insert(new_index, sub_element)
    return sub_element


def export_attributes(
    element: _Element, with_id: bool = True
) -> Dict[str, str]:
    result = {str(key): str(value) for key, value in element.attrib.items()}
    if not with_id:
        result.pop("id", None)
    for role_name in ("role", "rsc-role"):
        if role_name in result:
            result[role_name] = pacemaker.role.get_value_primary(
                const.PcmkRoleType(result[role_name].capitalize())
            )
    return result


def update_attribute_remove_empty(element, name, value):
    """
    Set an attribute's value or remove the attribute if the value is ""

    etree element -- element to be updated
    string name -- attribute name
    mixed value -- attribute value
    """
    if not value:
        if name in element.attrib:
            del element.attrib[name]
        return
    element.set(name, value)


def update_attributes_remove_empty(element, attributtes):
    """
    Set an attributes' values or remove an attribute if its new value is ""

    etree element -- element to be updated
    dict attributes -- new attributes' values
    """
    for name, value in attributtes.items():
        update_attribute_remove_empty(element, name, value)


def etree_element_attibutes_to_dict(etree_el, required_key_list):
    """
    Returns all attributes of etree_el from required_key_list in dictionary,
    where keys are attributes and values are values of attributes or None if
    it's not present.

    etree_el -- etree element from which attributes should be extracted
    required_key_list -- list of strings, attributes names which should be
        extracted
    """
    return {key: etree_el.get(key) for key in required_key_list}


def etree_to_str(tree: _Element) -> str:
    """
    Export a lxml tree to a string
    etree tree - the tree to be exported
    """
    # etree returns string in bytes: b'xml'
    # python 3 removed .encode() from byte strings
    # run(...) calls subprocess.Popen.communicate which calls encode...
    # so there is bytes to str conversion
    raw = etree.tostring(tree)
    return raw.decode() if isinstance(raw, bytes) else raw


def is_element_useful(element, attribs_important=True):
    """
    Is an element worth keeping?

    Some elements serve as a container for sub-elements. When all sub-elements
    are removed it is time to consider if such element is still meaningful.

    Some of these elements can be meaningful standalone when they contain
    attributes (e.g. "network" or "storage" in "bundle"). Some of these
    elements are not meaningful without sub-elements even if they have
    attributes (e.g. rsc_ticket - after last sub-element 'resource_set' removal
    there can be attributes but the element is pointless - more details at the
    approrpriate place of use). By default, an element is meaningful when it
    contains attributes (except id) even if it has no sub-elements. This can be
    switched by attribs_important parameter.

    lxml.etree.element element -- element to analyze
    bool attribs_important -- if True, the element is useful if it contains
        attributes even if it has no sub-elements
    """
    return len(element) or (
        attribs_important and element.attrib and element.attrib.keys() != ["id"]
    )


def append_when_useful(parent, element, attribs_important=True, index=None):
    """
    Append an element to a parent if the element is useful (see
        is_element_useful for details)

    lxml.etree.element parent -- where to append the element
    lxml.etree.element element -- the element to append
    bool attribs_important -- if True, append even if the element has no
        children if it has attributes
    int or None index -- postion to append the element, None means at the end
    """
    if element.getparent() == parent:
        return element
    if is_element_useful(element, attribs_important):
        if index is None:
            parent.append(element)
        else:
            parent.insert(index, element)
    return element


def remove_when_pointless(
    element: _Element,
    attribs_important: bool = True,
) -> None:
    """
    Remove an element when it is not worth keeping (see is_element_useful for
        details).

    lxml.etree.element element -- element to remove
    bool attribs_important -- if True, do not delete the element if it contains
        attributes
    """
    if not is_element_useful(element, attribs_important):
        remove_one_element(element)


def reset_element(element, keep_attrs=None):
    """
    Remove all subelements and all attributes (except mentioned in keep_attrs)
    of given element.

    lxml.etree.element element -- element to reset
    list keep_attrs -- names of attributes thas should be kept
    """
    keep_attrs = keep_attrs or []
    for child in list(element):
        element.remove(child)
    for key in element.attrib.keys():
        if key not in keep_attrs:
            del element.attrib[key]


def move_elements(
    to_move_list: Iterable[_Element],
    adjacent_el: _Element,
    put_after_adjacent: bool = False,
) -> None:
    """
    Move elements inside or into an element after or before specified element
    in the element.

    to_move_list -- elements to be moved
    adjacent_el -- the element next to which the moved elements will be put
    put_after_adjacent -- put elements after (True) or before (False) the
        adjacent element
    """
    for el in to_move_list:
        if put_after_adjacent:
            adjacent_el.addnext(el)
            adjacent_el = el
        else:
            adjacent_el.addprevious(el)


def remove_one_element(element: _Element) -> None:
    """
    Remove single specified element.

    element -- element to be removed
    """
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)
