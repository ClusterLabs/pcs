from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

TAGS_CLONE = "clone", "master"
TAGS_ALL = TAGS_CLONE + ("primitive", "group")

def find_by_id(tree, id):
    for element in tree.findall('.//*[@id="{0}"]'.format(id)):
        if element is not None and element.tag in TAGS_ALL:
            return element
    return None
