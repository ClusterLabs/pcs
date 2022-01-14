# OCF 1.0 doesn't define unique groups, they are defined since OCF 1.1. Pcs
# transforms OCF 1.0 agents to OCF 1.1 structure and therefore needs to create
# a group name for OCF 1.0 unique attrs. The name is: {this_prefix}{attr_name}
DEFAULT_UNIQUE_GROUP_PREFIX = "_pcs_unique_group_"
