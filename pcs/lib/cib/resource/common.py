from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

def disable_meta(meta_attributes):
    """
    Return new dict with meta attributes containing values to disable resource.

    dict meta_attributes are current meta attributes
    """
    disabled_meta_attributes = meta_attributes.copy()
    disabled_meta_attributes["target-role"] = "Stopped"
    return disabled_meta_attributes

