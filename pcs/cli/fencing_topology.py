from pcs.common.fencing_topology import (
    TARGET_TYPE_NODE,
    TARGET_TYPE_REGEXP,
    TARGET_TYPE_ATTRIBUTE,
)

__target_type_map = {
    "attrib": TARGET_TYPE_ATTRIBUTE,
    "node": TARGET_TYPE_NODE,
    "regexp": TARGET_TYPE_REGEXP,
}

target_type_map_cli_to_lib = __target_type_map

target_type_map_lib_to_cli = dict([
    (value, key) for key, value in __target_type_map.items()
])
