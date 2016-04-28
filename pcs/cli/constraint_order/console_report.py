from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from pcs.lib.pacemaker_values import is_true

def constraint_plain(constraint_info, with_id=False):
    """
    dict constraint_info see constraint in pcs/lib/exchange_formats.md
    bool with_id have to show id with options_dict
    """
    options = constraint_info["options"]
    oc_resource1 = options.get("first", "")
    oc_resource2 = options.get("then", "")
    first_action = options.get("first-action", "")
    then_action = options.get("then-action", "")
    oc_id = options.get("id", "")
    oc_score = options.get("score", "")
    oc_kind = options.get("kind", "")
    oc_sym = ""
    oc_id_out = ""
    oc_options = ""
    if (
        "symmetrical" in options
        and
        not is_true(options.get("symmetrical", "false"))
    ):
        oc_sym = "(non-symmetrical)"
    if oc_kind != "":
        score_text = "(kind:" + oc_kind + ")"
    elif oc_kind == "" and oc_score == "":
        score_text = "(kind:Mandatory)"
    else:
        score_text = "(score:" + oc_score + ")"
    if with_id:
        oc_id_out = "(id:"+oc_id+")"
    already_processed_options = (
        "first", "then", "first-action", "then-action", "id", "score", "kind",
        "symmetrical"
    )
    oc_options = " ".join([
        "{0}={1}".format(name, value)
        for name, value in options.items()
        if name not in already_processed_options
    ])
    if oc_options:
        oc_options = "(Options: " + oc_options + ")"
    return " ".join([arg for arg in [
        first_action, oc_resource1, "then", then_action, oc_resource2,
        score_text, oc_sym, oc_options, oc_id_out
    ] if arg])
