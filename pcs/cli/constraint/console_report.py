from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)


def constraint_plain(type, constraint_info, with_id=False):
    return type + " ".join(prepare_attrs(constraint_info["attrib"], with_id))

def resource_sets(set_list, with_id=True):
    report = []
    for resource_set in set_list:
        report.extend(
            ["set"] + resource_set["ids"] + options(resource_set["attrib"])
        )
        if with_id:
            report.append(id_from_options(resource_set["attrib"]))

    return report

def options(attrs):
    return [
        key+"="+value for key, value in sorted(attrs.items()) if key != "id"
    ]

def id_from_options(attrs):
    return "(id:"+attrs.get("id", "")+")"

def constraint_with_sets(constraint_info, with_id=True):
    """
    dict constraint_info for example:
        {"attrib": {"id": "id_constraint"}, "resource_sets": [{
            "ids": ["resource_id_1", "resource_id_2"],
            "attrib": {"id": "resource_set_id"}
        }]}
    bool with_id have to show id with attributes
    """
    attributes = options(constraint_info["attrib"])
    return " ".join(
        resource_sets(constraint_info["resource_sets"], with_id)
        +
        (["setoptions"] + attributes if attributes else [])
        +
        ([id_from_options(constraint_info["attrib"])] if with_id else [])
    )

def prepare_attrs(attributes, with_id=True):
    return (
        options(attributes)
        +
        ([id_from_options(attributes)] if with_id else [])
    )
