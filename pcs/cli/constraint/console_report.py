from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)


def constraint_plain(constraint_type, constraint_info, with_id=False):
    return constraint_type + " ".join(
        prepare_options(constraint_info["options"], with_id)
    )

def resource_sets(set_list, with_id=True):
    """
    list of dict set_list see resource set
        in pcs/lib/exchange_formats.md
    """
    report = []
    for resource_set in set_list:
        report.extend(
            ["set"] + resource_set["ids"] + options(resource_set["options"])
        )
        if with_id:
            report.append(id_from_options(resource_set["options"]))

    return report

def options(options_dict):
    return [
        key+"="+value
        for key, value in sorted(options_dict.items())
        if key != "id"
    ]

def id_from_options(options_dict):
    return "(id:"+options_dict.get("id", "")+")"

def constraint_with_sets(constraint_info, with_id=True):
    """
    dict constraint_info  see constraint in pcs/lib/exchange_formats.md
    bool with_id have to show id with options_dict
    """
    options_dict = options(constraint_info["options"])
    return " ".join(
        resource_sets(constraint_info["resource_sets"], with_id)
        +
        (["setoptions"] + options_dict if options_dict else [])
        +
        ([id_from_options(constraint_info["options"])] if with_id else [])
    )

def prepare_options(options_dict, with_id=True):
    return (
        options(options_dict)
        +
        ([id_from_options(options_dict)] if with_id else [])
    )
