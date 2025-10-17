from dataclasses import replace as dc_replace

from pcs.common.resource_agent.dto import ResourceAgentParameterDto
from pcs.lib.resource_agent import (
    ResourceMetaAttributesMetadataDto,
)

_ADDITIONAL_FENCING_META_ATTRIBUTES_DTO = [
    ResourceAgentParameterDto(
        name="provides",
        shortdesc=None,
        longdesc=(
            "Any special capability provided by the fence device. Currently, "
            "only one such capability is meaningful: unfencing."
        ),
        type="string",
        default=None,
        enum_values=None,
        required=False,
        advanced=False,
        deprecated=False,
        deprecated_by=[],
        deprecated_desc=None,
        unique_group=None,
        reloadable=False,
    )
]


def get_primitive_meta_attributes_dto(
    is_fencing=False,
) -> ResourceMetaAttributesMetadataDto:
    metadata_dto = ResourceMetaAttributesMetadataDto(
        metadata=[
            ResourceAgentParameterDto(
                name="priority",
                shortdesc="Resource assignment priority",
                longdesc=(
                    "Resource assignment priority.\nIf not all resources can "
                    "be active, the cluster will stop lower-priority "
                    "resources in order to keep higher-priority ones active."
                ),
                type="score",
                default="0",
                enum_values=None,
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="critical",
                shortdesc=(
                    "Default value for influence in colocation constraints"
                ),
                longdesc=(
                    "Default value for influence in colocation constraints.\n"
                    "Use this value as the default for influence in all "
                    "colocation constraints involving this resource, as well "
                    "as in the implicit colocation constraints created if "
                    "this resource is in a group."
                ),
                type="boolean",
                default="true",
                enum_values=None,
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="target-role",
                shortdesc=(
                    "State the cluster should attempt to keep this resource in"
                ),
                longdesc=(
                    "State the cluster should attempt to keep this resource "
                    'in.\n"Stopped" forces the resource to be stopped. '
                    '"Started" allows the resource to be started (and in the '
                    "case of promotable clone resources, promoted if "
                    'appropriate). "Unpromoted" allows the resource to be '
                    "started, but only in the unpromoted role if the resource "
                    'is promotable. "Promoted" is equivalent to "Started".'
                ),
                type="select",
                default="Started",
                enum_values=[
                    "Stopped",
                    "Started",
                    "Unpromoted",
                    "Promoted",
                ],
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="is-managed",
                shortdesc=(
                    "Whether the cluster is allowed to actively change the "
                    "resource's state"
                ),
                longdesc=(
                    "Whether the cluster is allowed to actively change the "
                    "resource's state.\nIf false, the cluster will not start, "
                    "stop, promote, or demote the resource on any node. "
                    "Recurring actions for the resource are unaffected. If "
                    "true, a true value for the maintenance-mode cluster "
                    "option, the maintenance node attribute, or the "
                    "maintenance resource meta-attribute overrides this."
                ),
                type="boolean",
                default="true",
                enum_values=None,
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="maintenance",
                shortdesc=(
                    "If true, the cluster will not schedule any actions "
                    "involving the resource"
                ),
                longdesc=(
                    "If true, the cluster will not schedule any actions "
                    "involving the resource.\nIf true, the cluster will not "
                    "start, stop, promote, or demote the resource on any node, "
                    "and will pause any recurring monitors (except those "
                    'specifying role as "Stopped"). If false, a true value '
                    "for the maintenance-mode cluster option or maintenance "
                    "node attribute overrides this."
                ),
                type="boolean",
                default="false",
                enum_values=None,
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="resource-stickiness",
                shortdesc=(
                    "Score to add to the current node when a resource is "
                    "already active"
                ),
                longdesc=(
                    "Score to add to the current node when a resource is "
                    "already active.\nScore to add to the current node when a "
                    "resource is already active. This allows running resources "
                    "to stay where they are, even if they would be placed "
                    "elsewhere if they were being started from a stopped "
                    "state. The default is 1 for individual clone instances, "
                    "and 0 for all other resources."
                ),
                type="score",
                default=None,
                enum_values=None,
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="requires",
                shortdesc="Conditions under which the resource can be started",
                longdesc=(
                    "Conditions under which the resource can "
                    "be started.\n"
                    "Conditions under which the resource can "
                    'be started. "nothing" means the cluster '
                    'can always start this resource. "quorum" '
                    "means the cluster can start this resource "
                    "only if a majority of the configured "
                    'nodes are active. "fencing" means the '
                    "cluster can start this resource only if a "
                    "majority of the configured nodes are "
                    "active and any failed or unknown nodes "
                    'have been fenced. "unfencing" means the '
                    "cluster can start this resource only if a "
                    "majority of the configured nodes are "
                    "active and any failed or unknown nodes "
                    "have been fenced, and only on nodes that "
                    "have been unfenced. The default is "
                    '"quorum" for resources with a class of '
                    'stonith; otherwise, "unfencing" if '
                    "unfencing is active in the cluster; "
                    'otherwise, "fencing" if the '
                    "fencing-enabled cluster option is true; "
                    'otherwise, "quorum".'
                ),
                type="select",
                default=None,
                enum_values=[
                    "nothing",
                    "quorum",
                    "fencing",
                    "unfencing",
                ],
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="migration-threshold",
                shortdesc=(
                    "Number of failures on a node before the resource becomes "
                    "ineligible to run there."
                ),
                longdesc=(
                    "Number of failures on a node before the "
                    "resource becomes ineligible to run "
                    "there.\n"
                    "Number of failures that may occur for "
                    "this resource on a node, before that node "
                    "is marked ineligible to host this "
                    "resource. A value of 0 indicates that "
                    "this feature is disabled (the node will "
                    "never be marked ineligible). By contrast, "
                    'the cluster treats "INFINITY" (the '
                    "default) as a very large but finite "
                    "number. This option has an effect only if "
                    "the failed operation specifies its "
                    'on-fail attribute as "restart" (the '
                    "default), and additionally for failed "
                    "start operations, if the "
                    "start-failure-is-fatal cluster property "
                    "is set to false."
                ),
                type="score",
                default="INFINITY",
                enum_values=None,
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="failure-timeout",
                shortdesc=(
                    "Number of seconds before acting as if a failure had not "
                    "occurred"
                ),
                longdesc=(
                    "Number of seconds before acting as if a failure had not "
                    "occurred.\nNumber of seconds after a failed action for "
                    "this resource before acting as if the failure had not "
                    "occurred, and potentially allowing the resource back to "
                    "the node on which it failed. A value of 0 indicates that "
                    "this feature is disabled."
                ),
                type="duration",
                default="0",
                enum_values=None,
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="multiple-active",
                shortdesc=(
                    "What to do if the cluster finds the resource active on "
                    "more than one node"
                ),
                longdesc=(
                    "What to do if the cluster finds the "
                    "resource active on more than one node.\n"
                    "What to do if the cluster finds the "
                    "resource active on more than one node. "
                    '"block" means to mark the resource as '
                    'unmanaged. "stop_only" means to stop all '
                    "active instances of this resource and "
                    'leave them stopped. "stop_start" means to '
                    "stop all active instances of this "
                    "resource and start the resource in one "
                    'location only. "stop_unexpected" means to '
                    "stop all active instances of this "
                    "resource except where the resource should "
                    "be active. (This should be used only when "
                    "extra instances are not expected to "
                    "disrupt existing instances, and the "
                    "resource agent's monitor of an existing "
                    "instance is capable of detecting any "
                    "problems that could be caused. Note that "
                    "any resources ordered after this one will "
                    "still need to be restarted.)"
                ),
                type="select",
                default="stop_start",
                enum_values=[
                    "block",
                    "stop_only",
                    "stop_start",
                    "stop_unexpected",
                ],
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="allow-migrate",
                shortdesc=(
                    'Whether the cluster should try to "live '
                    'migrate" this resource when it needs to '
                    "be moved"
                ),
                longdesc=(
                    'Whether the cluster should try to "live '
                    'migrate" this resource when it needs to '
                    "be moved.\n"
                    'Whether the cluster should try to "live '
                    'migrate" this resource when it needs to '
                    "be moved. The default is true for "
                    "ocf:pacemaker:remote resources, and false "
                    "otherwise."
                ),
                type="boolean",
                default=None,
                enum_values=None,
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="allow-unhealthy-nodes",
                shortdesc=(
                    "Whether the resource should be allowed "
                    "to run on a node even if the node's "
                    "health score would otherwise prevent it"
                ),
                longdesc=None,
                type="boolean",
                default="false",
                enum_values=None,
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="container-attribute-target",
                shortdesc="Where to check user-defined node attributes",
                longdesc=(
                    "Where to check user-defined node "
                    "attributes.\n"
                    "Whether to check user-defined node "
                    "attributes on the physical host where a "
                    "container is running or on the local "
                    "node. This is usually set for a bundle "
                    "resource and inherited by the bundle's "
                    'primitive resource. A value of "host" '
                    "means to check user-defined node "
                    "attributes on the underlying physical "
                    "host. Any other value means to check "
                    "user-defined node attributes on the local "
                    "node (for a bundled primitive resource, "
                    "this is the bundle node)."
                ),
                type="string",
                default=None,
                enum_values=None,
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="remote-node",
                shortdesc=(
                    "Name of the Pacemaker Remote guest node "
                    "this resource is associated with, if any"
                ),
                longdesc=(
                    "Name of the Pacemaker Remote guest node "
                    "this resource is associated with, if "
                    "any.\n"
                    "Name of the Pacemaker Remote guest node "
                    "this resource is associated with, if any. "
                    "If specified, this both enables the "
                    "resource as a guest node and defines the "
                    "unique name used to identify the guest "
                    "node. The guest must be configured to run "
                    "the Pacemaker Remote daemon when it is "
                    "started. WARNING: This value cannot "
                    "overlap with any resource or node IDs."
                ),
                type="string",
                default=None,
                enum_values=None,
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="remote-addr",
                shortdesc=(
                    "If remote-node is specified, the IP address or hostname "
                    "used to connect to the guest via Pacemaker Remote"
                ),
                longdesc=(
                    "If remote-node is specified, the IP address or hostname "
                    "used to connect to the guest via Pacemaker Remote.\nIf "
                    "remote-node is specified, the IP address or hostname "
                    "used to connect to the guest via Pacemaker Remote. The "
                    "Pacemaker Remote daemon on the guest must be configured "
                    "to accept connections on this address. The default is "
                    "the value of the remote-node meta-attribute."
                ),
                type="string",
                default=None,
                enum_values=None,
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="remote-port",
                shortdesc=(
                    "If remote-node is specified, port on the guest used for "
                    "its Pacemaker Remote connection"
                ),
                longdesc=(
                    "If remote-node is specified, port on the guest used for "
                    "its Pacemaker Remote connection.\nIf remote-node is "
                    "specified, the port on the guest used for its Pacemaker "
                    "Remote connection. The Pacemaker Remote daemon on the "
                    "guest must be configured to listen "
                    "on this port."
                ),
                type="port",
                default="3121",
                enum_values=None,
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="remote-connect-timeout",
                shortdesc=(
                    "If remote-node is specified, how long before a pending "
                    "Pacemaker Remote guest connection times out."
                ),
                longdesc=None,
                type="timeout",
                default="60s",
                enum_values=None,
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
            ResourceAgentParameterDto(
                name="remote-allow-migrate",
                shortdesc=(
                    "If remote-node is specified, this acts as the "
                    "allow-migrate meta-attribute for the implicit remote "
                    "connection resource (ocf:pacemaker:remote)."
                ),
                longdesc=None,
                type="boolean",
                default="true",
                enum_values=None,
                required=False,
                advanced=False,
                deprecated=False,
                deprecated_by=[],
                deprecated_desc=None,
                unique_group=None,
                reloadable=False,
            ),
        ],
        is_fencing=is_fencing,
    )
    if is_fencing:
        metadata_dto = dc_replace(
            metadata_dto,
            metadata=list(metadata_dto.metadata)
            + _ADDITIONAL_FENCING_META_ATTRIBUTES_DTO,
        )
    return metadata_dto
