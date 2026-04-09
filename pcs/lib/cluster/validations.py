from pcs.common import reports
from pcs.lib import validate


def validate_add_cluster(
    cluster_name: str, nodes: list[str]
) -> reports.ReportItemList:
    report_list = validate.ValueNotEmpty(
        "name", None, option_name_for_report="cluster name"
    ).validate({"name": cluster_name})

    if not nodes:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.InvalidOptionValue(
                    "nodes",
                    "[]",
                    "non-empty list of nodes",
                    cannot_be_empty=True,
                )
            )
        )

    seen_node_names = set()
    node_name_duplicates = set()
    for node_name in nodes:
        report_list.extend(
            validate.ValueNotEmpty(
                "node_name", None, option_name_for_report="node name"
            ).validate({"node_name": node_name})
        )
        if node_name in seen_node_names:
            node_name_duplicates.add(node_name)
        seen_node_names.add(node_name)
    if node_name_duplicates:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.NodeNamesDuplication(
                    sorted(node_name_duplicates)
                )
            )
        )

    return report_list


def validate_remove_clusters(
    clusters_to_remove: list[str],
) -> reports.ReportItemList:
    add_remove_validator = validate.ValidateAddRemove(
        [],
        clusters_to_remove,
        reports.const.ADD_REMOVE_ITEM_TYPE_CLUSTER,
    )
    # To match the original Ruby implementation, there is is intentionally no
    # validation - not validating duplicates, or if the removed clusters exist
    return add_remove_validator.validate_add_or_remove_specified()
