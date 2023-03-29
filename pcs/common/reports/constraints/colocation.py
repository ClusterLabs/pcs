def constraint_plain(constraint_info):
    """
    dict constraint_info see constraint in pcs/lib/exchange_formats.md
    """
    options_dict = constraint_info["options"]
    co_resource1 = options_dict.get("rsc", "")
    co_resource2 = options_dict.get("with-rsc", "")
    co_id = options_dict.get("id", "")
    co_score = options_dict.get("score", "")
    score_text = "(score:" + co_score + ")"
    console_option_list = [
        "(%s:%s)" % (option[0], option[1])
        for option in sorted(options_dict.items())
        if option[0] not in ("rsc", "with-rsc", "id", "score")
    ]
    console_option_list.append("(id:%s)" % co_id)
    return " ".join(
        [co_resource1, "with", co_resource2, score_text] + console_option_list
    )
