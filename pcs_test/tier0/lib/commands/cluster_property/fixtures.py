def fixture_property_set(set_id, nvpairs, score=None):
    score_attr = ""
    if score:
        score_attr = f'score="{score}"'
    return (
        f'<cluster_property_set id="{set_id}" {score_attr}>'
        + "".join(
            [
                f'<nvpair id="{set_id}-{name}" name="{name}" value="{value}"/>'
                for name, value in nvpairs.items()
                if value
            ]
        )
        + "</cluster_property_set>"
    )


def fixture_crm_config_properties(set_list, score_list=None):
    return (
        "<crm_config>"
        + "".join(
            [
                fixture_property_set(
                    set_tuple[0],
                    set_tuple[1],
                    score=None if not score_list else score_list[idx],
                )
                for idx, set_tuple in enumerate(set_list)
            ]
        )
        + "</crm_config>"
    )
