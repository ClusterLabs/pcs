from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib.cib.resource import primitive, operations, clone, group

def find_by_id(tree, element_id):
    """
    Return first resource element with id=element_id

    etree.Element(Tree) tree is part of the cib
    string element_id is id of the search element
    """
    for element in tree.findall('.//*[@id="{0}"]'.format(element_id)):
        if element is not None and element.tag in (
            clone.TAG_CLONE, clone.TAG_MASTER, primitive.TAG, group.TAG
        ):
            return element
    return None
