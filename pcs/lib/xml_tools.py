from __future__ import (
    absolute_import,
    division,
    print_function,
)

from lxml import etree

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
    element, sub_element_tag, new_id=None, new_index=None, insert=True
):
    """
    Returns the FIRST sub-element sub_element_tag of element. It will create new
    element if such doesn't exist yet.

    element -- parent element
    sub_element_tag -- tag of the wanted new element
    new_id -- id of the new element, None means no id will be set
    new_index -- where the new element will be added, None means at the end
    insert bool -- if True and sub-element doesn't exist, newly created
        sub-element will be placed into element
    """
    sub_element = element.find("./{0}".format(sub_element_tag))
    if sub_element is None:
        sub_element = etree.Element(sub_element_tag)
        if new_id:
            sub_element.set("id", new_id)
        if insert:
            if new_index is None:
                element.append(sub_element)
            else:
                element.insert(new_index, sub_element)
    return sub_element

def export_attributes(element):
    return  dict((key, value) for key, value in element.attrib.items())

def update_attribute_remove_empty(element, name, value):
    """
    Set an attribute's value or remove the attribute if the value is ""

    etree element -- element to be updated
    string name -- attribute name
    mixed value -- attribute value
    """
    if len(value) < 1:
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
    return dict([(key, etree_el.get(key)) for key in required_key_list])

def etree_to_str(tree):
    """
    Export a lxml tree to a string
    etree tree - the tree to be exported
    """
    #etree returns string in bytes: b'xml'
    #python 3 removed .encode() from byte strings
    #run(...) calls subprocess.Popen.communicate which calls encode...
    #so there is bytes to str conversion
    return etree.tostring(tree).decode()

def remove_when_pointless(element, attribs_important=True):
    """
    Remove element when is not worth to keep it.

    Some elements serve as a container for sub-elements. When all sub-elements
    are removed is time to consider if such element is still meaningfull.

    Some of these elements can be meaningfull standalone when it contains some
    attributes (e.g. "network" or "storage" in "bundle"). Some of these elements
    are not meaningfull without sub-elements even if they have attributes (e.g.
    rsc_ticket - after last sub-element 'resource_set' removal there can be
    attributes but the element is pointless - more details at the approrpriate
    place of use). Element is meaningfull when contain attributes (except id) by
    default. It can be switched by parameter attribs_important.

    lxml.etree.element element -- element to remove
    bool attribs_important -- prevents deletion when its value is True and
        the element contains attributes
    """
    is_element_useful = len(element) or (
        attribs_important
        and
        element.attrib
        and
        element.attrib.keys() != ["id"]
    )

    if not is_element_useful:
        element.getparent().remove(element)
