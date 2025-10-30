from typing import Iterable, Mapping, cast

from pcs.common import reports
from pcs.common.types import StringIterable
from pcs.lib import validate
from pcs.lib.resource_agent import CrmResourceAgent, ResourceAgentParameter


def validate_meta_attributes(
    meta_attributes_types: Iterable[CrmResourceAgent],
    meta_attributes_metadata: Iterable[ResourceAgentParameter],
    meta_attributes: Mapping[str, str],
) -> reports.ReportItemList:
    """
    Validate meta attributes.

    meta_attributes_types -- resource type of the meta attributes
    meta_attributes_metadata -- meta attribute definitions of a specific
        resource type
    meta_attributes -- meta attributes to be validated
    """
    return validate.PcmkMetaAttributeNamesIn(
        [parameter.name for parameter in meta_attributes_metadata],
        cast(StringIterable, meta_attributes_types),
    ).validate(
        # Allow removing meta attributes unknown to pacemaker while preventing
        # setting them
        {name: value for name, value in meta_attributes.items() if value != ""}
    )
