from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

def constraint_plain(constraint_info, with_id=False):
    attributes = constraint_info["attrib"]
    co_resource1 = attributes.get("rsc", "")
    co_resource2 = attributes.get("with-rsc", "")
    co_id = attributes.get("id", "")
    co_score = attributes.get("score", "")
    score_text = "(score:" + co_score + ")"
    attrs_list = [
        "(%s:%s)" % (attr[0], attr[1])
        for attr in sorted(attributes.items())
        if attr[0] not in ("rsc", "with-rsc", "id", "score")
    ]
    if with_id:
        attrs_list.append("(id:%s)" % co_id)
    return " ".join(
        [co_resource1, "with", co_resource2, score_text] + attrs_list
    )
