from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from pcs.lib.pacemaker_values import is_true

def constraint_plain(constraint_info, with_id=False):
    attributes = constraint_info["attrib"]
    oc_resource1 = attributes.get("first", "")
    oc_resource2 = attributes.get("then", "")
    first_action = attributes.get("first-action", "")
    then_action = attributes.get("then-action", "")
    oc_id = attributes.get("id", "")
    oc_score = attributes.get("score", "")
    oc_kind = attributes.get("kind", "")
    oc_sym = ""
    oc_id_out = ""
    oc_options = ""
    if (
        "symmetrical" in attributes
        and
        not is_true(attributes.get("symmetrical", "false"))
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
    already_processed_attrs = (
        "first", "then", "first-action", "then-action", "id", "score", "kind",
        "symmetrical"
    )
    oc_options = " ".join([
        "{0}={1}".format(name, value)
        for name, value in attributes.items()
        if name not in already_processed_attrs
    ])
    if oc_options:
        oc_options = "(Options: " + oc_options + ")"
    return " ".join([arg for arg in [
        first_action, oc_resource1, "then", then_action, oc_resource2,
        score_text, oc_sym, oc_options, oc_id_out
    ] if arg])
