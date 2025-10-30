from pcs.common.resource_agent import const

from .types import (
    _FAKE_AGENT_STANDARD,
    CrmAttrAgent,
    CrmResourceAgent,
    FakeAgentName,
    OcfVersion,
)

OCF_1_0 = OcfVersion("1.0")
OCF_1_1 = OcfVersion("1.1")
SUPPORTED_OCF_VERSIONS = [OCF_1_0, OCF_1_1]

FAKE_AGENT_STANDARD = _FAKE_AGENT_STANDARD
CLUSTER_OPTIONS = CrmAttrAgent("cluster-options")
PACEMAKER_FENCED = FakeAgentName("pacemaker-fenced")
PRIMITIVE_META = CrmResourceAgent("primitive-meta")
STONITH_META = CrmResourceAgent("stonith-meta")


STONITH_ACTION_REPLACED_BY = ["pcmk_off_action", "pcmk_reboot_action"]
DEFAULT_UNIQUE_GROUP_PREFIX = const.DEFAULT_UNIQUE_GROUP_PREFIX
