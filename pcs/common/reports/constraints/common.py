def constraint_plain(constraint_type, constraint_info):
    return "{0} {1}".format(
        constraint_type,
        " ".join(prepare_options(constraint_info["options"])),
    )


def _resource_sets(set_list):
    """
    list of dict set_list see resource set
        in pcs/lib/exchange_formats.md
    """
    report = []
    for resource_set in set_list:
        report.extend(
            ["set"]
            + resource_set["ids"]
            + prepare_options(resource_set["options"])
        )

    return report


def prepare_options(options_dict):
    return [
        key + "=" + value
        for key, value in sorted(options_dict.items())
        if key != "id"
    ] + ["(id:{id})".format(id=options_dict.get("id", ""))]


def constraint_with_sets(constraint_info):
    """
    dict constraint_info  see constraint in pcs/lib/exchange_formats.md
    """
    options_dict = prepare_options(constraint_info["options"])
    return " ".join(
        _resource_sets(constraint_info["resource_sets"])
        + ((["setoptions"] + options_dict) if options_dict else [])
    )
