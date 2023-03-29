from pcs.common.reports.constraints.common import prepare_options


def constraint_plain(constraint_info):
    """
    dict constraint_info  see constraint in pcs/lib/exchange_formats.md
    """
    options = constraint_info["options"]
    role = options.get("rsc-role", "")
    role_prefix = "{0} ".format(role) if role else ""

    return role_prefix + " ".join(
        [options.get("rsc", "")]
        + prepare_options(
            dict(
                (name, value)
                for name, value in options.items()
                if name not in ["rsc-role", "rsc"]
            ),
        )
    )
