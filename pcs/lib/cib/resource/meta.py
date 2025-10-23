from typing import Iterable, Mapping

from pcs.common import reports
from pcs.lib import validate
from pcs.lib.resource_agent import ResourceAgentParameter


def validate_meta_attributes(
    meta_attributes_metadata: Iterable[ResourceAgentParameter],
    meta_attributes: Mapping[str, str],
) -> reports.ReportItemList:
    """
    Validate meta attributes.

    meta_attributes_metadata -- meta attribute definitions of a specific
        resource type
    meta_attributes -- meta attributes to be validated
    """
    return validate.NamesIn(
        [parameter.name for parameter in meta_attributes_metadata],
        option_type="meta attribute",
        severity=reports.item.ReportItemSeverity.warning(),
    ).validate(
        # Allow removing meta attributes unknown to pacemaker while preventing
        # setting them
        {name: value for name, value in meta_attributes.items() if value != ""}
    )
