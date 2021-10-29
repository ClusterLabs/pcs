from .types import FakeAgentName, OcfVersion, _FAKE_AGENT_STANDARD

OCF_1_0 = OcfVersion("1.0")
OCF_1_1 = OcfVersion("1.1")
SUPPORTED_OCF_VERSIONS = [OCF_1_0, OCF_1_1]

FAKE_AGENT_STANDARD = _FAKE_AGENT_STANDARD
PACEMAKER_FENCED = FakeAgentName("pacemaker-fenced")

STONITH_ACTION_REPLACED_BY = ["pcmk_off_action", "pcmk_reboot_action"]

# OCF 1.0 doesn't define unique groups, they are defined since OCF 1.1. Pcs
# transforms OCF 1.0 agents to OCF 1.1 structure and therefore needs to create
# a group name for OCF 1.0 unique attrs. The name is: {this_prefix}{attr_name}
DEFAULT_UNIQUE_GROUP_PREFIX = "_pcs_unique_group_"
