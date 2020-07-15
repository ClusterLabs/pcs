from typing import (
    List,
    Tuple,
)

from lxml.etree import _Element

from pcs.lib.pacemaker.values import is_false

# TODO replace by the new finding function
def is_stonith_resource(resources_el, name):
    return (
        len(
            resources_el.xpath(
                "primitive[@id='{0}' and @class='stonith']".format(name)
            )
        )
        > 0
    )


def is_stonith_enabled(crm_config_el: _Element) -> bool:
    # We should read the default value from pacemaker. However, that may slow
    # pcs down as we need to run 'pacemaker-schedulerd metadata' to get it.
    stonith_enabled = True
    # TODO properly support multiple cluster_property_set with rules
    for nvpair in crm_config_el.iterfind(
        "cluster_property_set/nvpair[@name='stonith-enabled']"
    ):
        if is_false(nvpair.get("value")):
            stonith_enabled = False
            break
    return stonith_enabled


def get_misconfigured_resources(
    resources_el: _Element,
) -> Tuple[List[_Element], List[_Element], List[_Element]]:
    """
    Return stonith: all, 'action' option set, 'method' option set to 'cycle'
    """
    stonith_all = []
    stonith_with_action = []
    stonith_with_method_cycle = []
    for stonith in resources_el.iterfind("primitive[@class='stonith']"):
        stonith_all.append(stonith)
        for nvpair in stonith.iterfind("instance_attributes/nvpair"):
            if nvpair.get("name") == "action" and nvpair.get("value"):
                stonith_with_action.append(stonith)
            if (
                nvpair.get("name") == "method"
                and nvpair.get("value") == "cycle"
            ):
                stonith_with_method_cycle.append(stonith)
    return stonith_all, stonith_with_action, stonith_with_method_cycle
