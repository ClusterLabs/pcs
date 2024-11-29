from typing import (
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Union,
    cast,
)

from lxml import etree
from lxml.etree import (
    _Element,
    _ElementTree,
)

from pcs.common import (
    const,
    pacemaker,
)
from pcs.common.types import StringCollection


def get_root(tree: Union[_Element, _ElementTree]) -> _Element:
    # ElementTree has getroot, Element has getroottree
    if isinstance(tree, _ElementTree):
        return tree.getroot()
    # getroot() turns _ElementTree to _Element
    return tree.getroottree().getroot()


def find_parent(
    element: _Element, tag_names: StringCollection
) -> Optional[_Element]:
    """
    Return the closest parent with specified tag name of an element or None

    element -- the element whose parent we want to find
    tag_names -- allowed tag names of a parent we are looking for
    """
    candidate: Optional[_Element] = element
    while True:
        if candidate is None or candidate.tag in tag_names:
            return candidate
        candidate = candidate.getparent()


def get_sub_element(
    element: _Element,
    sub_element_tag: str,
    new_id: Optional[str] = None,
    new_index: Optional[int] = None,
    append_if_missing: bool = True,
) -> _Element:
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
    sub_element_list = cast(
        List[_Element],
        element.xpath("./*[local-name()=$tag_name]", tag_name=sub_element_tag),
    )
    if not sub_element_list:
        sub_element = etree.Element(sub_element_tag)
        if new_id:
            sub_element.set("id", new_id)
        if append_if_missing:
            if new_index is None:
                element.append(sub_element)
            else:
                element.insert(new_index, sub_element)
        return sub_element
    return sub_element_list[0]


def export_attributes(
    element: _Element, with_id: bool = True
) -> Dict[str, str]:
    result = {str(key): str(value) for key, value in element.attrib.items()}
    if not with_id:
        result.pop("id", None)
    for role_name in ("role", "rsc-role", "with-rsc-role"):
        if role_name in result:
            result[role_name] = pacemaker.role.get_value_primary(
                const.PcmkRoleType(result[role_name].capitalize())
            )
    return result


def update_attribute_remove_empty(
    element: _Element, name: str, value: str
) -> None:
    """
    Set an attribute's value or remove the attribute if the value is empty

    element -- element to be updated
    name -- attribute name
    value -- attribute value
    """
    if not value:
        if name in element.attrib:
            del element.attrib[name]
        return
    element.set(name, value)


def update_attributes_remove_empty(
    element: _Element, attributes: Mapping[str, str]
) -> None:
    """
    Set an attributes' values or remove an attribute if its new value is empty

    element -- element to be updated
    attributes -- new attributes' values
    """
    for name, value in attributes.items():
        update_attribute_remove_empty(element, name, value)


def etree_to_str(tree: _Element) -> str:
    """
    Export a lxml tree to a string

    tree - the tree to be exported
    """
    # etree returns string in bytes: b'xml'
    # python 3 removed .encode() from byte strings
    # run(...) calls subprocess.Popen.communicate which calls encode...
    # so there is bytes to str conversion
    raw = etree.tostring(tree)
    return raw.decode() if isinstance(raw, bytes) else raw


def is_element_useful(
    element: _Element, attribs_important: bool = True
) -> bool:
    """
    Is an element worth keeping?

    Some elements serve as a container for sub-elements. When all sub-elements
    are removed it is time to consider if such element is still meaningful.

    Some of these elements can be meaningful standalone when they contain
    attributes (e.g. "network" or "storage" in "bundle"). Some of these
    elements are not meaningful without sub-elements even if they have
    attributes (e.g. rsc_ticket - after last sub-element 'resource_set' removal
    there can be attributes but the element is pointless - more details at the
    appropriate place of use). By default, an element is meaningful when it
    contains attributes (except id) even if it has no sub-elements. This can be
    switched by attribs_important parameter.

    element -- element to analyze
    attribs_important -- if True, the element is useful if it contains
        attributes even if it has no sub-elements
    """
    return len(element) > 0 or (
        attribs_important
        and bool(element.attrib)
        and element.attrib.keys() != ["id"]
    )


def append_when_useful(
    parent: _Element,
    element: _Element,
    attribs_important: bool = True,
    index: Optional[int] = None,
) -> _Element:
    """
    Append an element to a parent if the element is useful (see
        is_element_useful for details)

    parent -- where to append the element
    element -- the element to append
    attribs_important -- if True, append even if the element has no children if
        it has attributes
    index -- position to append the element, None means at the end
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

    element -- element to remove
    attribs_important -- if True, do not delete the element if it contains
        attributes
    """
    if not is_element_useful(element, attribs_important):
        remove_one_element(element)


def reset_element(
    element: _Element, keep_attrs: Optional[StringCollection] = None
) -> None:
    """
    Remove all subelements and all attributes (except mentioned in keep_attrs)
    of given element.

    element -- element to reset
    keep_attrs -- names of attributes thas should be kept
    """
    keep_attrs = keep_attrs or []
    for child in list(element):
        element.remove(child)
    for key in element.attrib:
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
