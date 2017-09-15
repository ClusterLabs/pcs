from __future__ import (
    absolute_import,
    division,
    print_function,
)

from lxml import etree

from pcs.common.tools import is_string
from pcs.test.tools.xml import etree_to_str


def _replace_element_in_parent(element_to_replace, new_element):
    parent = element_to_replace.getparent()
    for child in parent:
        if element_to_replace == child:
            index = list(parent).index(child)
            parent.remove(child)
            parent.insert(index, new_element)
            return

def _xml_to_element(xml):
    try:
        new_element = etree.fromstring(xml)
    except etree.XMLSyntaxError:
        raise AssertionError(
            "Cannot put to the cib a non-xml fragment:\n'{0}'"
            .format(xml)
        )
    return new_element

def _find_element(cib_tree, element_xpath):
    element = cib_tree.find(element_xpath)
    if element is None:
        raise AssertionError(
            "Cannot find '{0}' in given cib:\n{1}".format(
                element_xpath,
                etree_to_str(cib_tree)
            )
        )
    return element

def remove_element(element_xpath):
    def remove(cib_tree):
        xpath_list = (
            [element_xpath] if is_string(element_xpath) else element_xpath
        )
        for xpath in xpath_list:
            element_to_remove = _find_element(cib_tree, xpath)
            element_to_remove.getparent().remove(element_to_remove)
    return remove

def replace_optional_element(element_place_xpath, element_name, new_content):
    def replace_optional(cib_tree):
        element_parent = _find_element(cib_tree, element_place_xpath)
        elements_to_replace = element_parent.findall(element_name)
        if not elements_to_replace:
            new_element = etree.SubElement(element_parent, element_name)
            elements_to_replace.append(new_element)
        elif len(elements_to_replace) > 1:
            raise AssertionError(
                (
                    "Cannot replace '{element}' in '{parent}' because '{parent}'"
                    " contains more than one '{element}' in given cib:\n{cib}"
                ).format(
                    element=element_name,
                    parent=element_place_xpath,
                    cib=etree_to_str(cib_tree)
                )
            )
        _replace_element_in_parent(
            elements_to_replace[0],
            _xml_to_element(new_content)
        )
    return replace_optional

def replace_more_elements(replacements):
    """
    Return a function that replace more elements (defined by replacement_dict)
    in the cib_tree with new_content.

    dict replacemens -- contains more replacements:
        key is xpath - its destination must be one element: replacement is
        applied only on the first occurence
        value is new content -contains a content that have to be placed instead
        of an element found by element_xpath
    """
    def replace(cib_tree):
        for xpath, new_content in replacements.items():
            _replace_element_in_parent(
                _find_element(cib_tree, xpath),
                _xml_to_element(new_content)
            )
    return replace

#Possible modifier shortcuts are defined here.
#Keep in mind that every key will be named parameter in config function
#(see modifier_shortcuts param in some of pcs.test.tools.command_env.config_*
#modules)
#
#DO NOT USE CONFLICTING KEYS HERE!
#1) args of pcs.test.tools.command_env.calls#CallListBuilder.place:
#  name, before, instead
#2) args of pcs.test.tools.command_env.mock_runner#Call.__init__
#  command, stdout, stderr, returncode, check_stdin
#3) special args of pcs.test.tools.command_env.config_*
#  modifiers, filename, load_key, wait, exception
#It would be not aplied. Not even mention that the majority of these names do
#not make sense for a cib modifying ;)
MODIFIER_GENERATORS = {
    "remove": remove_element,
    "replace": replace_more_elements,
    "resources": lambda xml: replace_more_elements({".//resources": xml}),
    "optional_in_conf": lambda optional_in_conf: replace_optional_element(
        "./configuration",
        etree.fromstring(optional_in_conf).tag,
        optional_in_conf,
    ),
}

def create_modifiers(**modifier_shortcuts):
    """
    Return list of modifiers: list of functions that transform cib

    dict modifier_shortcuts -- a new modifier is generated from each modifier
        shortcut.
        As key there can be keys of MODIFIER_GENERATORS.
        Value is passed into appropriate generator from MODIFIER_GENERATORS.

    """
    unknown_shortcuts = (
        set(modifier_shortcuts.keys()) - set(MODIFIER_GENERATORS.keys())
    )
    if unknown_shortcuts:
        raise AssertionError(
            "Unknown modifier shortcuts '{0}', available are: '{1}'".format(
                "', '".join(list(unknown_shortcuts)),
                "', '".join(MODIFIER_GENERATORS.keys()),
            )
        )

    return [
        MODIFIER_GENERATORS[name](param)
        for name, param in modifier_shortcuts.items()
    ]

def modify_cib(cib_xml, modifiers=None, **modifier_shortcuts):
    """
    Apply modifiers to cib_xml and return the result cib_xml

    string cib_xml -- initial cib
    list of callable modifiers -- each takes cib (etree.Element)
    dict modifier_shortcuts -- a new modifier is generated from each modifier
        shortcut.
        As key there can be keys of MODIFIER_GENERATORS.
        Value is passed into appropriate generator from MODIFIER_GENERATORS.
    """
    modifiers = modifiers if modifiers else []
    all_modifiers = modifiers + create_modifiers(**modifier_shortcuts)

    if not all_modifiers:
        return cib_xml

    cib_tree = etree.fromstring(cib_xml)
    for modify in all_modifiers:
        modify(cib_tree)

    return etree_to_str(cib_tree)
