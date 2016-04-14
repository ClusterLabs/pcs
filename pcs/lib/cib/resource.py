from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

TAGS_CLONE = "clone", "master"
TAGS_ALL = TAGS_CLONE + ("primitive", "group")

def find_by_id(tree, id):
    element = tree.find('.//*[@id="{0}"]'.format(id))
    if element is None or element.tag not in TAGS_ALL:
        return None
    return element
