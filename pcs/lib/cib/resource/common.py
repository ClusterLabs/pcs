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

def are_meta_disabled(meta_attributes):
    return meta_attributes.get("target-role", "Started").lower() == "stopped"

def _is_positive_number(value):
    string_value = str(value)
    return string_value.isdigit() and string_value.rstrip("0")

def are_clone_meta_disabled(meta_attributes):
    return are_meta_disabled(meta_attributes) or any([
        not _is_positive_number(meta_attributes.get(key, "1"))
        for key in ["clone-max", "clone-node-max"]
    ])
