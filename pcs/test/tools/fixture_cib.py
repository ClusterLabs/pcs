from __future__ import (
    absolute_import,
    division,
    print_function,
)

from lxml import etree

from pcs.common.tools import is_string
from pcs.test.tools.xml import etree_to_str


def _replace(element_to_replace, new_element):
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

def _find_all_in(cib_tree, element_xpath):
    element_list = cib_tree.xpath(element_xpath)
    if not element_list:
        raise AssertionError(
            "Cannot find '{0}' in given cib:\n{1}".format(
                element_xpath,
                etree_to_str(cib_tree)
            )
        )
    return element_list

def _find_in(cib_tree, element_xpath):
    element_list = _find_all_in(cib_tree, element_xpath)
    if len(element_list) > 1:
        raise AssertionError(
            "Found more than one '{0}' in given cib:\n{1}".format(
                element_xpath,
                etree_to_str(cib_tree)
            )
        )
    return element_list[0]

def remove(element_xpath):
    def _remove(cib_tree):
        xpath_list = (
            [element_xpath] if is_string(element_xpath) else element_xpath
        )
        for xpath in xpath_list:
            for element_to_remove in _find_all_in(cib_tree, xpath):
                element_to_remove.getparent().remove(element_to_remove)
    return _remove

def put_or_replace(parent_xpath, new_content):
    #This tranformation makes sense in "configuration" section only. In this
    #section there are sub-tags (optional or mandatory) that can occure max 1x.
    #
    #In other sections it is possible to have more occurences of sub-tags. For
    #such cases it is better to use `replace_all` - the difference is that in
    #`replace_all` the element to be replaced is specified by full xpath
    #whilst in `put_or_replace` the xpath to the parent element is specified.
    def replace_optional(cib_tree):
        element = _xml_to_element(new_content)
        parent = _find_in(cib_tree, parent_xpath)
        current_elements = parent.findall(element.tag)

        if len(current_elements) > 1:
            raise _cannot_multireplace(element.tag, parent_xpath, cib_tree)

        if current_elements:
            _replace(current_elements[0], element)
        else:
            parent.append(element)

    return replace_optional

def replace_all(replacements):
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
            _replace(_find_in(cib_tree, xpath), _xml_to_element(new_content))
    return replace

def append_all(append_map):
    """
    Return a function that appends more elements after specified (xpath) element
    dict append_map -- a key is an xpath pointing to a target element (for
        appending), value is appended content
    """
    def append(cib_tree):
        for xpath, new_content in append_map.items():
            _find_in(cib_tree, xpath).append(_xml_to_element(new_content))
    return append


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
    "remove": remove,
    "replace": replace_all,
    "append": append_all,
    "resources": lambda xml: replace_all({"./configuration/resources": xml}),
    "optional_in_conf": lambda xml: put_or_replace("./configuration", xml),
    "constraints": lambda xml: replace_all(
        {"./configuration/constraints": xml}
    ),
    #common modifier `put_or_replace` makes not sense - see explanation inside
    #this function - all occurences should be satisfied by `optional_in_conf`
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

def _cannot_multireplace(tag, parent_xpath, cib_tree):
    return AssertionError(
        (
            "Cannot replace '{element}' in '{parent}' because '{parent}'"
            " contains more than one '{element}' in given cib:\n{cib}"
        ).format(element=tag, parent=parent_xpath, cib=etree_to_str(cib_tree))
    )
