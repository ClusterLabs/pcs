def get_resources_failcounts(cib_status):
    # pylint: disable=too-many-locals
    """
    List all resources failcounts
    Return a dict {
        "node": string -- node name,
        "resource": string -- resource id,
        "clone_id": string -- resource clone id or None,
        "operation": string -- operation name,
        "interval": string -- operation interval,
        "fail_count": "INFINITY" or int -- fail count,
        "last_failure": int -- last failure timestamp,
    }

    etree cib_status -- status element of the CIB
    """
    failcounts = []
    for node_state in cib_status.findall("node_state"):
        node_name = node_state.get("uname")

        # Pair fail-counts with last-failures.
        # failures_info = {
        #         failure_name: {"fail_count": count, "last-failure": timestamp}
        #     }
        failures_info = {}
        for nvpair in node_state.findall(
            "transient_attributes/instance_attributes/nvpair"
        ):
            name = nvpair.get("name")
            for part in ("fail-count-", "last-failure-"):
                if name.startswith(part):
                    failure_name = name[len(part):]
                    if failure_name not in failures_info:
                        failures_info[failure_name] = {}
                    failures_info[failure_name][part[:-1]] = nvpair.get("value")
                    break

        if not failures_info:
            continue
        for failure_name, failure_data in failures_info.items():
            resource, clone_id, operation, interval = _parse_failure_name(
                failure_name
            )
            fail_count = failure_data.get("fail-count", "0").upper()
            if fail_count != "INFINITY":
                try:
                    fail_count = int(fail_count)
                except ValueError:
                    # There are failures we just do not know how many. If we set
                    # fail_count = 0, no failures would be recorded.
                    fail_count = 1
            try:
                last_failure = int(failure_data.get("last-failure", "0"))
            except ValueError:
                last_failure = 0
            failcounts.append({
                "node": node_name,
                "resource": resource,
                "clone_id": clone_id,
                "operation": operation,
                "interval": interval,
                "fail_count": fail_count,
                "last_failure": last_failure,
            })
    return failcounts

def _parse_failure_name(name):
    # failure_name looks like this:
    # <resource_name>[:<clone_id>]#<operation>_<interval>
    # resource name is an id so it cannot contain # nor :
    resource_clone, operation_interval = name.split("#", 1)
    if ":" in resource_clone:
        resource, clone = resource_clone.split(":", 1)
    else:
        resource, clone = resource_clone, None
    operation, interval = operation_interval.rsplit("_", 1)
    return resource, clone, operation, interval

def filter_resources_failcounts(
    failcounts, resource=None, node=None, operation=None, interval=None
):
    return [
        failure for failure in failcounts
        if (
            (node is None or failure["node"] == node)
            and
            (resource is None or failure["resource"] == resource)
            and
            (operation is None or failure["operation"] == operation)
            and
            # 5 != "5", failure["interval"] is a string already
            (interval is None or failure["interval"] == str(interval))
        )
    ]
