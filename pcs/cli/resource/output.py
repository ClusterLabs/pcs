import shlex
from collections import defaultdict
from typing import (
    Container,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.output import (
    INDENT_STEP,
    bool_to_cli_value,
    format_wrap_for_terminal,
    options_to_cmd,
    pairs_to_cmd,
)
from pcs.cli.nvset import nvset_dto_to_lines
from pcs.cli.reports.output import warn
from pcs.cli.resource_agent import is_stonith
from pcs.common import resource_agent
from pcs.common.pacemaker.defaults import CibDefaultsDto
from pcs.common.pacemaker.nvset import CibNvsetDto
from pcs.common.pacemaker.resource.bundle import (
    CibResourceBundleContainerRuntimeOptionsDto,
    CibResourceBundleDto,
    CibResourceBundleNetworkOptionsDto,
    CibResourceBundlePortMappingDto,
    CibResourceBundleStorageMappingDto,
)
from pcs.common.pacemaker.resource.clone import CibResourceCloneDto
from pcs.common.pacemaker.resource.group import CibResourceGroupDto
from pcs.common.pacemaker.resource.list import CibResourcesDto
from pcs.common.pacemaker.resource.operations import (
    OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME,
    CibResourceOperationDto,
)
from pcs.common.pacemaker.resource.primitive import CibResourcePrimitiveDto
from pcs.common.resource_agent.dto import (
    ResourceAgentNameDto,
    get_resource_agent_full_name,
)
from pcs.common.str_tools import (
    format_list,
    format_name_value_list,
    format_optional,
    format_plural,
    indent,
)
from pcs.common.types import StringIterable


def _get_ocf_check_level_from_operation(
    operation_dto: CibResourceOperationDto,
) -> Optional[str]:
    for nvset in operation_dto.instance_attributes:
        for nvpair in nvset.nvpairs:
            if nvpair.name == OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME:
                return nvpair.value
    return None


def _resource_operation_to_pairs(
    operation_dto: CibResourceOperationDto,
) -> List[Tuple[str, str]]:
    pairs = [("interval", operation_dto.interval)]
    if operation_dto.id:
        pairs.append(("id", operation_dto.id))
    if operation_dto.start_delay:
        pairs.append(("start-delay", operation_dto.start_delay))
    elif operation_dto.interval_origin:
        pairs.append(("interval-origin", operation_dto.interval_origin))
    if operation_dto.timeout:
        pairs.append(("timeout", operation_dto.timeout))
    if operation_dto.enabled is not None:
        pairs.append(("enabled", bool_to_cli_value(operation_dto.enabled)))
    if operation_dto.record_pending is not None:
        pairs.append(
            ("record-pending", bool_to_cli_value(operation_dto.record_pending))
        )
    if operation_dto.role:
        pairs.append(("role", operation_dto.role))
    if operation_dto.on_fail:
        pairs.append(("on-fail", operation_dto.on_fail))
    ocf_check_level = _get_ocf_check_level_from_operation(operation_dto)
    if ocf_check_level:
        pairs.append((OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME, ocf_check_level))
    return pairs


def _resource_operation_to_str(
    operation_dto: CibResourceOperationDto,
) -> List[str]:
    lines = []
    op_pairs = [
        pair
        for pair in _resource_operation_to_pairs(operation_dto)
        if pair[0] != "id"
    ]
    if op_pairs:
        lines.append(" ".join(format_name_value_list(op_pairs)))
    # TODO: add support for meta and instance attributes once it is supported
    # by pcs
    return [
        "{name}:{id}".format(
            name=operation_dto.name,
            id=format_optional(operation_dto.id, " {}"),
        )
    ] + indent(lines, indent_step=INDENT_STEP)


def resource_agent_parameter_metadata_to_text(
    parameter: resource_agent.dto.ResourceAgentParameterDto,
) -> list[str]:
    # pylint: disable=too-many-branches
    # title line
    param_title = [parameter.name]
    if parameter.deprecated_by:
        param_title.append(
            "(deprecated by {})".format(", ".join(parameter.deprecated_by))
        )
    elif parameter.deprecated:
        param_title.append("(deprecated)")
    if parameter.required:
        param_title.append("(required)")
    if parameter.unique_group:
        if parameter.unique_group.startswith(
            resource_agent.const.DEFAULT_UNIQUE_GROUP_PREFIX
        ):
            param_title.append("(unique)")
        else:
            param_title.append(f"(unique group: {parameter.unique_group})")
    if parameter.advanced:
        param_title.append("(advanced use only)")

    # description lines
    text: list[str] = []

    if parameter.deprecated_desc:
        text.append("DEPRECATED: {parameter.deprecated_desc}")

    desc = ""
    if parameter.longdesc:
        desc = parameter.longdesc.replace("\n", " ")
    elif parameter.shortdesc:
        desc = parameter.shortdesc.replace("\n", " ")
    else:
        desc = "No description available"
    text.append(f"Description: {desc}")

    if parameter.enum_values:
        text.append(
            "Allowed values: {}".format(format_list(parameter.enum_values))
        )
    elif parameter.type:
        text.append(f"Type: {parameter.type}")

    if parameter.default:
        text.append(f"Default: {parameter.default}")

    return [" ".join(param_title)] + indent(text)


def resource_agent_metadata_to_text(
    metadata: resource_agent.dto.ResourceAgentMetadataDto,
    default_operations: List[CibResourceOperationDto],
    verbose: bool = False,
) -> List[str]:
    output = []
    _is_stonith = is_stonith(metadata.name)
    agent_name = (
        metadata.name.type
        if _is_stonith
        else get_resource_agent_full_name(metadata.name)
    )
    if metadata.shortdesc:
        output.extend(
            format_wrap_for_terminal(
                "{agent_name} - {shortdesc}".format(
                    agent_name=agent_name,
                    shortdesc=metadata.shortdesc.replace("\n", " "),
                ),
            )
        )
    else:
        output.append(agent_name)

    if metadata.longdesc:
        output.append("")
        output.extend(
            format_wrap_for_terminal(
                metadata.longdesc.replace("\n", " "), subsequent_indent=0
            )
        )

    params = []
    for param in metadata.parameters:
        if not verbose and (param.advanced or param.deprecated):
            continue
        params.extend(resource_agent_parameter_metadata_to_text(param))

    if params:
        output.append("")
        if _is_stonith:
            output.append("Stonith options:")
        else:
            output.append("Resource options:")
        output.extend(indent(params, indent_step=INDENT_STEP))

    operations = []
    for operation in default_operations:
        operations.extend(_resource_operation_to_str(operation))

    if operations:
        output.append("")
        output.append("Default operations:")
        output.extend(indent(operations, indent_step=INDENT_STEP))

    return output


class ResourcesConfigurationFacade:
    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        primitives: Sequence[CibResourcePrimitiveDto],
        groups: Sequence[CibResourceGroupDto],
        clones: Sequence[CibResourceCloneDto],
        bundles: Sequence[CibResourceBundleDto],
        filtered_ids: StringIterable = (),
        only_stonith: Optional[bool] = None,
    ) -> None:
        self._primitives = primitives
        self._groups = groups
        self._clones = clones
        self._bundles = bundles
        self._filtered_ids = frozenset(filtered_ids)
        self._only_stonith = only_stonith
        self._primitives_map = {res.id: res for res in self._primitives}
        self._bundles_map = {res.id: res for res in self._bundles}
        self._clones_map = {res.id: res for res in self._clones}
        self._groups_map = {res.id: res for res in self._groups}
        self._child_parent_map: Dict[str, str] = {}
        self._parent_child_map: Dict[str, List[str]] = defaultdict(list)
        for bundle_dto in self._bundles:
            if bundle_dto.member_id:
                self._set_parent(bundle_dto.member_id, bundle_dto.id)
        for clone_dto in self._clones:
            self._set_parent(clone_dto.member_id, clone_dto.id)
        for group_dto in self._groups:
            for primitive_id in group_dto.member_ids:
                self._set_parent(primitive_id, group_dto.id)

    @classmethod
    def from_resources_dto(
        cls, resources_dto: CibResourcesDto
    ) -> "ResourcesConfigurationFacade":
        return cls(
            resources_dto.primitives,
            resources_dto.groups,
            resources_dto.clones,
            resources_dto.bundles,
        )

    def get_parent_id(self, res_id: str) -> Optional[str]:
        return self._child_parent_map.get(res_id)

    def _get_children_ids(self, res_id: str) -> List[str]:
        return self._parent_child_map[res_id]

    def _set_parent(self, child_id: str, parent_id: str) -> None:
        if self.get_parent_id(child_id):
            raise AssertionError("invalid data")
        self._child_parent_map[child_id] = parent_id
        self._parent_child_map[parent_id].append(child_id)

    def get_primitive_dto(
        self, obj_id: str
    ) -> Optional[CibResourcePrimitiveDto]:
        return self._primitives_map.get(obj_id)

    def get_group_dto(self, obj_id: str) -> Optional[CibResourceGroupDto]:
        return self._groups_map.get(obj_id)

    def _get_any_resource_dto(self, obj_id: str) -> Optional[
        Union[
            CibResourcePrimitiveDto,
            CibResourceGroupDto,
            CibResourceCloneDto,
            CibResourceBundleDto,
        ]
    ]:
        return (
            self._primitives_map.get(obj_id)
            or self._bundles_map.get(obj_id)
            or self._clones_map.get(obj_id)
            or self._groups_map.get(obj_id)
        )

    @property
    def filtered_ids(self) -> Container[str]:
        return self._filtered_ids

    @property
    def primitives(self) -> Sequence[CibResourcePrimitiveDto]:
        return self._primitives

    @property
    def clones(self) -> Sequence[CibResourceCloneDto]:
        return self._clones

    @property
    def groups(self) -> Sequence[CibResourceGroupDto]:
        return self._groups

    @property
    def bundles(self) -> Sequence[CibResourceBundleDto]:
        return self._bundles

    def filter_stonith(
        self, allow_stonith: bool
    ) -> "ResourcesConfigurationFacade":
        primitives = [
            primitive
            for primitive in self._primitives
            if is_stonith(primitive.agent_name) == allow_stonith
            or (not allow_stonith and self.get_parent_id(primitive.id))
        ]
        if allow_stonith:
            return self.__class__(
                primitives=primitives,
                clones=[],
                bundles=[],
                groups=[],
                filtered_ids=self._filtered_ids,
                only_stonith=True,
            )
        return self.__class__(
            primitives=primitives,
            clones=self._clones,
            bundles=self._bundles,
            groups=self._groups,
            filtered_ids=self._filtered_ids,
            only_stonith=False,
        )

    def filter_resources(
        self, resource_ids_to_find: StringIterable
    ) -> "ResourcesConfigurationFacade":
        if not resource_ids_to_find:
            return self
        primitives = set()
        groups = set()
        clones = set()
        bundles = set()

        label = "resource/stonith device"
        if self._only_stonith is True:
            label = "stonith device"
        elif self._only_stonith is False:
            label = "resource"

        ids_to_process = set(resource_ids_to_find)
        processed_ids = set()

        while ids_to_process:
            resource_id = ids_to_process.pop()
            if resource_id in processed_ids:
                continue
            resource_dto = self._get_any_resource_dto(resource_id)
            if resource_dto is None:
                warn(f"Unable to find {label} '{resource_id}'")
                continue
            processed_ids.add(resource_id)
            ids_to_process.update(self._get_children_ids(resource_id))
            if isinstance(resource_dto, CibResourcePrimitiveDto):
                primitives.add(resource_id)
            elif isinstance(resource_dto, CibResourceGroupDto):
                groups.add(resource_id)
            elif isinstance(resource_dto, CibResourceCloneDto):
                clones.add(resource_id)
            elif isinstance(resource_dto, CibResourceBundleDto):
                bundles.add(resource_id)
            else:
                raise AssertionError()

        if not processed_ids:
            raise CmdLineInputError(f"No {label} found")
        return self.__class__(
            primitives=sorted(
                (self._primitives_map[res_id] for res_id in primitives),
                key=lambda obj: obj.id,
            ),
            clones=sorted(
                (self._clones_map[res_id] for res_id in clones),
                key=lambda obj: obj.id,
            ),
            groups=sorted(
                (self._groups_map[res_id] for res_id in groups),
                key=lambda obj: obj.id,
            ),
            bundles=sorted(
                (self._bundles_map[res_id] for res_id in bundles),
                key=lambda obj: obj.id,
            ),
            filtered_ids=set(resource_ids_to_find) & set(processed_ids),
            only_stonith=self._only_stonith,
        )


def _resource_agent_name_to_text(
    resource_agent_name_dto: ResourceAgentNameDto,
) -> str:
    output = f"class={resource_agent_name_dto.standard}"
    if resource_agent_name_dto.provider:
        output += f" provider={resource_agent_name_dto.provider}"
    output += f" type={resource_agent_name_dto.type}"
    return output


def _nvset_to_text(label: str, nvsets: Sequence[CibNvsetDto]) -> List[str]:
    if nvsets and nvsets[0].nvpairs:
        return nvset_dto_to_lines(nvset=nvsets[0], nvset_label=label)
    return []


def _resource_description_to_text(desc: Optional[str]) -> List[str]:
    if desc:
        return [f"Description: {desc}"]
    return []


def _resource_primitive_to_text(
    primitive_dto: CibResourcePrimitiveDto,
) -> List[str]:
    output = (
        _resource_description_to_text(primitive_dto.description)
        + _nvset_to_text("Attributes", primitive_dto.instance_attributes)
        + _nvset_to_text("Meta Attributes", primitive_dto.meta_attributes)
        + _nvset_to_text("Utilization", primitive_dto.utilization)
    )
    if primitive_dto.operations:
        operation_lines: List[str] = []
        for operation_dto in primitive_dto.operations:
            operation_lines.extend(_resource_operation_to_str(operation_dto))
        output.extend(
            ["Operations:"] + indent(operation_lines, indent_step=INDENT_STEP)
        )

    return [
        "Resource: {res_id} ({res_type})".format(
            res_id=primitive_dto.id,
            res_type=_resource_agent_name_to_text(primitive_dto.agent_name),
        )
    ] + indent(output, indent_step=INDENT_STEP)


def _resource_group_to_text(
    group_dto: CibResourceGroupDto,
    resources_facade: ResourcesConfigurationFacade,
) -> List[str]:
    output = (
        _resource_description_to_text(group_dto.description)
        + _nvset_to_text("Attributes", group_dto.instance_attributes)
        + _nvset_to_text("Meta Attributes", group_dto.meta_attributes)
    )
    for primitive_id in group_dto.member_ids:
        primitive_dto = resources_facade.get_primitive_dto(primitive_id)
        if primitive_dto is None:
            raise CmdLineInputError(
                f"Invalid data: group {group_dto.id} has no children"
            )
        output.extend(_resource_primitive_to_text(primitive_dto))
    return [f"Group: {group_dto.id}"] + indent(output, indent_step=INDENT_STEP)


def _resource_clone_to_text(
    clone_dto: CibResourceCloneDto,
    resources_facade: ResourcesConfigurationFacade,
) -> List[str]:
    output = (
        _resource_description_to_text(clone_dto.description)
        + _nvset_to_text("Attributes", clone_dto.instance_attributes)
        + _nvset_to_text("Meta Attributes", clone_dto.meta_attributes)
    )
    primitive_dto = resources_facade.get_primitive_dto(clone_dto.member_id)
    group_dto = resources_facade.get_group_dto(clone_dto.member_id)
    if primitive_dto is not None:
        output.extend(_resource_primitive_to_text(primitive_dto))
    elif group_dto is not None:
        output.extend(_resource_group_to_text(group_dto, resources_facade))
    else:
        raise CmdLineInputError(
            f"Invalid data: clone {clone_dto.id} has no children"
        )
    return [f"Clone: {clone_dto.id}"] + indent(output, indent_step=INDENT_STEP)


def _resource_bundle_container_options_to_pairs(
    options: CibResourceBundleContainerRuntimeOptionsDto,
) -> List[Tuple[str, str]]:
    option_list = [("image", options.image)]
    if options.replicas is not None:
        option_list.append(("replicas", str(options.replicas)))
    if options.replicas_per_host is not None:
        option_list.append(
            ("replicas-per-host", str(options.replicas_per_host))
        )
    if options.promoted_max is not None:
        option_list.append(("promoted-max", str(options.promoted_max)))
    if options.run_command:
        option_list.append(("run-command", options.run_command))
    if options.network:
        option_list.append(("network", options.network))
    if options.options:
        option_list.append(("options", options.options))
    return option_list


def _resource_bundle_network_options_to_pairs(
    bundle_network_dto: Optional[CibResourceBundleNetworkOptionsDto],
) -> List[Tuple[str, str]]:
    network_options: List[Tuple[str, str]] = []
    if not bundle_network_dto:
        return network_options
    if bundle_network_dto.ip_range_start:
        network_options.append(
            ("ip-range-start", bundle_network_dto.ip_range_start)
        )
    if bundle_network_dto.control_port is not None:
        network_options.append(
            ("control-port", str(bundle_network_dto.control_port))
        )
    if bundle_network_dto.host_interface:
        network_options.append(
            ("host-interface", bundle_network_dto.host_interface)
        )
    if bundle_network_dto.host_netmask is not None:
        network_options.append(
            ("host-netmask", str(bundle_network_dto.host_netmask))
        )
    if bundle_network_dto.add_host is not None:
        network_options.append(
            ("add-host", bool_to_cli_value(bundle_network_dto.add_host))
        )
    return network_options


def _resource_bundle_port_mapping_to_pairs(
    bundle_net_port_mapping_dto: CibResourceBundlePortMappingDto,
) -> List[Tuple[str, str]]:
    mapping = []
    if bundle_net_port_mapping_dto.port is not None:
        mapping.append(("port", str(bundle_net_port_mapping_dto.port)))
    if bundle_net_port_mapping_dto.internal_port is not None:
        mapping.append(
            ("internal-port", str(bundle_net_port_mapping_dto.internal_port))
        )
    if bundle_net_port_mapping_dto.range:
        mapping.append(("range", bundle_net_port_mapping_dto.range))
    return mapping


def _resource_bundle_network_port_mapping_to_str(
    bundle_net_port_mapping_dto: CibResourceBundlePortMappingDto,
) -> List[str]:
    output = format_name_value_list(
        _resource_bundle_port_mapping_to_pairs(bundle_net_port_mapping_dto)
    )
    if output and bundle_net_port_mapping_dto.id:
        output.append(f"({bundle_net_port_mapping_dto.id})")
    return output


def _resource_bundle_network_to_text(
    bundle_network_dto: Optional[CibResourceBundleNetworkOptionsDto],
) -> List[str]:
    network_options = _resource_bundle_network_options_to_pairs(
        bundle_network_dto
    )
    if network_options:
        return [
            " ".join(["Network:"] + format_name_value_list(network_options))
        ]
    return []


def _resource_bundle_port_mappings_to_text(
    bundle_port_mappings: Sequence[CibResourceBundlePortMappingDto],
) -> List[str]:
    port_mappings = [
        " ".join(_resource_bundle_network_port_mapping_to_str(port_mapping_dto))
        for port_mapping_dto in bundle_port_mappings
    ]
    if port_mappings:
        return ["Port Mapping:"] + indent(
            port_mappings, indent_step=INDENT_STEP
        )
    return []


def _resource_bundle_storage_mapping_to_pairs(
    storage_mapping: CibResourceBundleStorageMappingDto,
) -> List[Tuple[str, str]]:
    mapping = []
    if storage_mapping.source_dir:
        mapping.append(("source-dir", storage_mapping.source_dir))
    if storage_mapping.source_dir_root:
        mapping.append(("source-dir-root", storage_mapping.source_dir_root))
    mapping.append(("target-dir", storage_mapping.target_dir))
    if storage_mapping.options:
        mapping.append(("options", storage_mapping.options))
    return mapping


def _resource_bundle_storage_mapping_to_str(
    storage_mapping: CibResourceBundleStorageMappingDto,
) -> List[str]:
    return format_name_value_list(
        _resource_bundle_storage_mapping_to_pairs(storage_mapping)
    ) + [f"({storage_mapping.id})"]


def _resource_bundle_storage_to_text(
    storage_mappings: Sequence[CibResourceBundleStorageMappingDto],
) -> List[str]:
    if not storage_mappings:
        return []
    output = []
    for storage_mapping in storage_mappings:
        output.append(
            " ".join(_resource_bundle_storage_mapping_to_str(storage_mapping))
        )
    return ["Storage Mapping:"] + indent(output, indent_step=INDENT_STEP)


def _resource_bundle_to_text(
    bundle_dto: CibResourceBundleDto,
    resources_facade: ResourcesConfigurationFacade,
) -> List[str]:
    container_options = []
    if bundle_dto.container_type and bundle_dto.container_options:
        container_options.append(
            " ".join(
                ["{}:".format(str(bundle_dto.container_type).capitalize())]
                + format_name_value_list(
                    _resource_bundle_container_options_to_pairs(
                        bundle_dto.container_options
                    )
                )
            )
        )
    output = (
        _resource_description_to_text(bundle_dto.description)
        + container_options
        + _resource_bundle_network_to_text(bundle_dto.network)
        + _resource_bundle_port_mappings_to_text(bundle_dto.port_mappings)
        + _resource_bundle_storage_to_text(bundle_dto.storage_mappings)
        + _nvset_to_text("Meta Attributes", bundle_dto.meta_attributes)
    )
    if bundle_dto.member_id:
        primitive_dto = resources_facade.get_primitive_dto(bundle_dto.member_id)
        if primitive_dto is None:
            raise CmdLineInputError(
                f"Invalid data: bundle '{bundle_dto.id}' has inner primitive "
                f"resource with id '{bundle_dto.member_id}' which was not found"
            )
        output.extend(_resource_primitive_to_text(primitive_dto))
    return [f"Bundle: {bundle_dto.id}"] + indent(
        output, indent_step=INDENT_STEP
    )


def resources_to_text(
    resources_facade: ResourcesConfigurationFacade,
) -> List[str]:
    def _is_allowed_to_display_fn(res_id: str) -> bool:
        if resources_facade.filtered_ids:
            return res_id in resources_facade.filtered_ids
        return resources_facade.get_parent_id(res_id) is None

    output = []
    for primitive_dto in resources_facade.primitives:
        if _is_allowed_to_display_fn(primitive_dto.id):
            output.extend(_resource_primitive_to_text(primitive_dto))
    for group_dto in resources_facade.groups:
        if _is_allowed_to_display_fn(group_dto.id):
            output.extend(_resource_group_to_text(group_dto, resources_facade))
    for clone_dto in resources_facade.clones:
        if _is_allowed_to_display_fn(clone_dto.id):
            output.extend(_resource_clone_to_text(clone_dto, resources_facade))
    for bundle_dto in resources_facade.bundles:
        if _is_allowed_to_display_fn(bundle_dto.id):
            output.extend(
                _resource_bundle_to_text(bundle_dto, resources_facade)
            )

    return output


def _nvset_to_cmd(
    label: Optional[str],
    nvsets: Sequence[CibNvsetDto],
) -> List[str]:
    if nvsets and nvsets[0].nvpairs:
        options = pairs_to_cmd(
            (nvpair.name, nvpair.value) for nvpair in nvsets[0].nvpairs
        )
        if label:
            options = f"{label} {options}"
        return [options]
    return []


def _resource_operation_to_cmd(
    operations: Sequence[CibResourceOperationDto],
) -> List[str]:
    if not operations:
        return []
    cmd = []
    for op in operations:
        cmd.append(
            "{name} {options}".format(
                name=op.name,
                options=pairs_to_cmd(_resource_operation_to_pairs(op)),
            )
        )
    return ["op"] + indent(cmd, indent_step=INDENT_STEP)


def _resource_primitive_to_cmd(
    primitive_dto: CibResourcePrimitiveDto,
    bundle_id: Optional[str],
) -> List[List[str]]:
    _is_stonith = is_stonith(primitive_dto.agent_name)
    options = (
        _nvset_to_cmd(None, primitive_dto.instance_attributes)
        + _resource_operation_to_cmd(primitive_dto.operations)
        + _nvset_to_cmd("meta", primitive_dto.meta_attributes)
    )
    if bundle_id:
        options.append(f"bundle {bundle_id}")

    output = [
        [
            options_to_cmd(
                [
                    "pcs",
                    "stonith" if _is_stonith else "resource",
                    "create",
                    "--no-default-ops",
                    "--force",
                    "--",
                    primitive_dto.id,
                    (
                        primitive_dto.agent_name.type
                        if _is_stonith
                        else get_resource_agent_full_name(
                            primitive_dto.agent_name
                        )
                    ),
                ]
            )
        ]
        + indent(options, indent_step=INDENT_STEP)
    ]
    utilization_cmd_params = _nvset_to_cmd(None, primitive_dto.utilization)
    if utilization_cmd_params:
        output.append(
            [
                options_to_cmd(
                    ["pcs", "resource", "utilization", primitive_dto.id]
                )
            ]
            + indent(utilization_cmd_params, indent_step=INDENT_STEP)
        )

    return output


def _resource_bundle_to_cmd(
    bundle_dto: CibResourceBundleDto,
) -> List[List[str]]:
    if not (bundle_dto.container_type and bundle_dto.container_options):
        return []
    options = [
        options_to_cmd(["container", str(bundle_dto.container_type)])
    ] + indent(
        [
            pairs_to_cmd(
                _resource_bundle_container_options_to_pairs(
                    bundle_dto.container_options
                )
            )
        ],
        indent_step=INDENT_STEP,
    )
    network_options = pairs_to_cmd(
        _resource_bundle_network_options_to_pairs(bundle_dto.network)
    )
    if network_options:
        options.append(f"network {network_options}")
    for port_mapping in bundle_dto.port_mappings:
        options.append(
            "port-map {}".format(
                pairs_to_cmd(
                    _resource_bundle_port_mapping_to_pairs(port_mapping)
                )
            )
        )
    for storage_mapping in bundle_dto.storage_mappings:
        options.append(
            "storage-map {}".format(
                pairs_to_cmd(
                    _resource_bundle_storage_mapping_to_pairs(storage_mapping)
                )
            )
        )
    options.extend(_nvset_to_cmd("meta", bundle_dto.meta_attributes))
    return [
        [options_to_cmd(["pcs", "resource", "bundle", "create", bundle_dto.id])]
        + indent(options, indent_step=INDENT_STEP)
    ]


def _resource_group_to_cmd(group_dto: CibResourceGroupDto) -> List[List[str]]:
    output = []
    output.append(
        [options_to_cmd(["pcs", "resource", "group", "add", group_dto.id])]
        + indent(
            [options_to_cmd(group_dto.member_ids)],
            indent_step=INDENT_STEP,
        )
    )
    meta_options = _nvset_to_cmd(None, group_dto.meta_attributes)
    if meta_options:
        output.append(
            [options_to_cmd(["pcs", "resource", "meta", group_dto.id])]
            + indent(meta_options, indent_step=INDENT_STEP)
        )
    return output


def _resource_clone_to_cmd(clone_dto: CibResourceCloneDto) -> List[List[str]]:
    return [
        [
            options_to_cmd(
                ["pcs", "resource", "clone", clone_dto.member_id, clone_dto.id]
            )
        ]
        + indent(
            _nvset_to_cmd("meta", clone_dto.meta_attributes),
            indent_step=INDENT_STEP,
        )
    ]


def _get_stonith_ids_from_group_dto(
    group_dto: CibResourceGroupDto,
    resources_facade: ResourcesConfigurationFacade,
) -> list[str]:
    stonith_ids = []
    for member_id in group_dto.member_ids:
        primitive_dto = resources_facade.get_primitive_dto(member_id)
        if primitive_dto is None:
            raise CmdLineInputError(
                f"Invalid data: group {group_dto.id} has no children"
            )
        if is_stonith(primitive_dto.agent_name):
            stonith_ids.append(primitive_dto.id)
    return stonith_ids


def _get_stonith_ids_from_clone_dto(
    clone_dto: CibResourceCloneDto,
    resources_facade: ResourcesConfigurationFacade,
) -> list[str]:
    primitive_dto = resources_facade.get_primitive_dto(clone_dto.member_id)
    group_dto = resources_facade.get_group_dto(clone_dto.member_id)
    if primitive_dto is not None:
        return (
            [primitive_dto.id] if is_stonith(primitive_dto.agent_name) else []
        )
    if group_dto is not None:
        return _get_stonith_ids_from_group_dto(group_dto, resources_facade)
    raise CmdLineInputError(
        f"Invalid data: clone {clone_dto.id} has no children"
    )


def _warn_stonith_unsupported(
    dto: Union[CibResourceBundleDto, CibResourceGroupDto, CibResourceCloneDto],
    stonith_ids: StringIterable,
) -> None:
    if isinstance(dto, CibResourceBundleDto):
        element = "bundle resource"
    elif isinstance(dto, CibResourceGroupDto):
        element = "group"
    elif isinstance(dto, CibResourceCloneDto):
        element = "clone"
    else:
        raise AssertionError(f"unexpedted cib resource dto: {dto}")

    resource_pl = format_plural(sorted(stonith_ids), "resource")
    stonith_id_list = format_list(sorted(stonith_ids))
    warn(
        f"{element.capitalize()} '{dto.id}' contains stonith {resource_pl}: "
        f"{stonith_id_list}. {element.capitalize()} with stonith {resource_pl} "
        f"is unsupported, therefore pcs is unable to create it. The {element} "
        "will be omitted."
    )


def resources_to_cmd(
    resources_facade: ResourcesConfigurationFacade,
) -> List[List[str]]:
    # pylint: disable=too-many-branches
    output: List[List[str]] = []
    primitives_created_with_bundle = set()
    for bundle_dto in resources_facade.bundles:
        if not (bundle_dto.container_type and bundle_dto.container_options):
            warn(
                f"Bundle resource '{bundle_dto.id}' uses unsupported container "
                "type, therefore pcs is unable to create it. The resource will be omitted."
            )
            continue
        primitive_dto = None
        if bundle_dto.member_id:
            primitive_dto = resources_facade.get_primitive_dto(
                bundle_dto.member_id
            )
            if primitive_dto is None:
                raise CmdLineInputError(
                    f"Invalid data: bundle '{bundle_dto.id}' has inner "
                    f"primitive resource with id '{bundle_dto.member_id}' "
                    "which was not found"
                )
            if is_stonith(primitive_dto.agent_name):
                _warn_stonith_unsupported(bundle_dto, [bundle_dto.member_id])
                continue
        output.extend(_resource_bundle_to_cmd(bundle_dto))
        if primitive_dto:
            output.extend(
                _resource_primitive_to_cmd(primitive_dto, bundle_dto.id)
            )
            primitives_created_with_bundle.add(bundle_dto.member_id)
    for primitive_dto in resources_facade.primitives:
        # stonith in bundle, clone, group is not filtered out for resource
        # config
        if is_stonith(
            primitive_dto.agent_name
        ) and resources_facade.get_parent_id(primitive_dto.id):
            continue
        if primitive_dto.id not in primitives_created_with_bundle:
            output.extend(_resource_primitive_to_cmd(primitive_dto, None))
    for group_dto in resources_facade.groups:
        stonith_ids = _get_stonith_ids_from_group_dto(
            group_dto, resources_facade
        )
        if stonith_ids:
            _warn_stonith_unsupported(group_dto, stonith_ids)
            continue
        output.extend(_resource_group_to_cmd(group_dto))
    for clone_dto in resources_facade.clones:
        stonith_ids = _get_stonith_ids_from_clone_dto(
            clone_dto, resources_facade
        )
        if stonith_ids:
            _warn_stonith_unsupported(clone_dto, stonith_ids)
            continue
        output.extend(_resource_clone_to_cmd(clone_dto))
    return output


def _nvset_options_to_pairs(nvset_dto: CibNvsetDto) -> list[tuple[str, str]]:
    pairs = list(nvset_dto.options.items())
    pairs.append(("id", nvset_dto.id))
    return pairs


def _nvset_rule_to_cmd(nvset_dto: CibNvsetDto) -> list[str]:
    if not nvset_dto.rule:
        return []
    rule_str = shlex.quote(nvset_dto.rule.as_string)
    return [f"rule {rule_str}"]


def _defaults_to_cmd(
    defaults_command: str,
    cib_defaults_dto: CibDefaultsDto,
) -> list[list[str]]:
    command_list: list[list[str]] = []
    for meta_attributes in cib_defaults_dto.meta_attributes:
        nvset_options = pairs_to_cmd(
            sorted(_nvset_options_to_pairs(meta_attributes))
        )
        command_list.append(
            [f"{defaults_command} {nvset_options}"]
            + indent(
                (
                    _nvset_to_cmd("meta", [meta_attributes])
                    + _nvset_rule_to_cmd(meta_attributes)
                ),
                indent_step=INDENT_STEP,
            )
        )
    return command_list


def operation_defaults_to_cmd(
    cib_defaults_dto: CibDefaultsDto,
) -> list[list[str]]:
    return _defaults_to_cmd(
        "pcs -- resource op defaults set create", cib_defaults_dto
    )


def resource_defaults_to_cmd(
    cib_defaults_dto: CibDefaultsDto,
) -> list[list[str]]:
    return _defaults_to_cmd(
        "pcs -- resource defaults set create", cib_defaults_dto
    )
