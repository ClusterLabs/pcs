from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

def get_root(tree):
    # ElementTree has getroot, Elemet has getroottree
    return tree.getroot() if hasattr(tree, "getroot") else tree.getroottree()

def find_parent(element, tag_names):
    candidate = element
    while True:
        if candidate is None or candidate.tag in tag_names:
            return candidate
        candidate = candidate.getparent()

def get_sub_element(element, sub_element_tag, new_id=None, new_index=None):
    """
    Returns the FIRST sub-element sub_element_tag of element. It will create new
    element if such doesn't exist yet.

    element -- parent element
    sub_element_tag -- tag of the wanted new element
    new_id -- id of the new element, None means no id will be set
    new_index -- where the new element will be added, None means at the end
    """
    sub_element = element.find("./{0}".format(sub_element_tag))
    if sub_element is None:
        sub_element = etree.Element(sub_element_tag)
        if new_id:
            sub_element.set("id", new_id)
        if new_index is None:
            element.append(sub_element)
        else:
            element.insert(new_index, sub_element)
    return sub_element

def export_attributes(element):
    return  dict((key, value) for key, value in element.attrib.items())

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
