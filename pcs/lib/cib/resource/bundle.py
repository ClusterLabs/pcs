from typing import (
    List,
    Optional,
    cast,
)

from lxml import etree
from lxml.etree import _Element

from pcs.common import reports
from pcs.common.pacemaker.resource import bundle
from pcs.lib import validate
from pcs.lib.cib import (
    nvpair_multi,
    rule,
)
from pcs.lib.cib.const import TAG_RESOURCE_BUNDLE as TAG
from pcs.lib.cib.nvpair import (
    META_ATTRIBUTES_TAG,
    append_new_meta_attributes,
    arrange_first_meta_attributes,
)
from pcs.lib.cib.resource.primitive import TAG as TAG_PRIMITIVE
from pcs.lib.cib.tools import ElementSearcher
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import sanitize_id
from pcs.lib.tools import get_optional_value
from pcs.lib.xml_tools import (
    append_when_useful,
    get_sub_element,
    reset_element,
    update_attributes_remove_empty,
)

GENERIC_CONTAINER_TYPES = {"docker", "podman"}

GENERIC_CONTAINER_OPTIONS = frozenset(
    (
        "image",
        "network",
        "options",
        "promoted-max",
        "run-command",
        "replicas",
        "replicas-per-host",
    )
)

NETWORK_OPTIONS = frozenset(
    (
        "control-port",
        "host-interface",
        "host-netmask",
        "ip-range-start",
    )
)

PORT_MAP_OPTIONS = frozenset(
    (
        "id",
        "port",
        "internal-port",
        "range",
    )
)

STORAGE_MAP_OPTIONS = frozenset(
    (
        "id",
        "options",
        "source-dir",
        "source-dir-root",
        "target-dir",
    )
)


def is_bundle(resource_el: _Element) -> bool:
    return resource_el.tag == TAG


def get_parent_bundle(resource_el: _Element) -> Optional[_Element]:
    """
    Get a parent bundle of a primitive or None

    resource_el -- the primitive to get its parent bundle
    """
    parent_el = resource_el.getparent()
    if parent_el is not None and is_bundle(parent_el):
        return parent_el
    return None


def bundle_element_to_dto(
    bundle_element: _Element,
    rule_eval: Optional[rule.RuleInEffectEval] = None,
) -> bundle.CibResourceBundleDto:
    if rule_eval is None:
        rule_eval = rule.RuleInEffectEvalDummy()
    primitive_el = get_inner_resource(bundle_element)
    runtime_el = _get_container_element(bundle_element)
    network_el = bundle_element.find("network")
    return bundle.CibResourceBundleDto(
        id=str(bundle_element.attrib["id"]),
        description=bundle_element.get("description"),
        member_id=(
            str(primitive_el.attrib["id"]) if primitive_el is not None else None
        ),
        container_type=(
            bundle.ContainerType(runtime_el.tag)
            if runtime_el is not None
            else None
        ),
        container_options=(
            bundle.CibResourceBundleContainerRuntimeOptionsDto(
                image=str(runtime_el.attrib["image"]),
                replicas=get_optional_value(int, runtime_el.get("replicas")),
                replicas_per_host=get_optional_value(
                    int, runtime_el.get("replicas-per-host")
                ),
                promoted_max=get_optional_value(
                    int,
                    runtime_el.get("promoted-max") or runtime_el.get("masters"),
                ),
                run_command=runtime_el.get("run-command"),
                network=runtime_el.get("network"),
                options=runtime_el.get("options"),
            )
            if runtime_el is not None
            else None
        ),
        network=(
            _bundle_network_element_to_dto(network_el)
            if network_el is not None
            else None
        ),
        port_mappings=[
            bundle.CibResourceBundlePortMappingDto(
                id=str(net_map_el.attrib["id"]),
                port=get_optional_value(int, net_map_el.get("port")),
                internal_port=get_optional_value(
                    int, net_map_el.get("internal-port")
                ),
                range=net_map_el.get("range"),
            )
            for net_map_el in bundle_element.findall("network/port-mapping")
        ],
        storage_mappings=[
            bundle.CibResourceBundleStorageMappingDto(
                id=str(storage_el.attrib["id"]),
                source_dir=storage_el.get("source-dir"),
                source_dir_root=storage_el.get("source-dir-root"),
                target_dir=str(storage_el.attrib["target-dir"]),
                options=storage_el.get("options"),
            )
            for storage_el in bundle_element.findall("storage/storage-mapping")
        ],
        meta_attributes=[
            nvpair_multi.nvset_element_to_dto(nvset, rule_eval)
            for nvset in nvpair_multi.find_nvsets(
                bundle_element, nvpair_multi.NVSET_META
            )
        ],
        instance_attributes=[
            nvpair_multi.nvset_element_to_dto(nvset, rule_eval)
            for nvset in nvpair_multi.find_nvsets(
                bundle_element, nvpair_multi.NVSET_INSTANCE
            )
        ],
    )


def _bundle_network_element_to_dto(
    network_element: _Element,
) -> bundle.CibResourceBundleNetworkOptionsDto:
    return bundle.CibResourceBundleNetworkOptionsDto(
        ip_range_start=network_element.get("ip-range-start"),
        control_port=get_optional_value(
            int, network_element.get("control-port")
        ),
        host_interface=network_element.get("host-interface"),
        host_netmask=get_optional_value(
            int, network_element.get("host-netmask")
        ),
        add_host=get_optional_value(bool, network_element.get("add-host")),
    )


def verify(resources_el: _Element) -> reports.ReportItemList:
    """
    Check if there are configuration errors in existing bundles

    resource_el -- element with bundles
    """
    return [
        _get_report_unsupported_container(bundle_el, updating_options=False)
        for bundle_el in resources_el.iterfind(TAG)
        if not _is_supported_container(_get_container_element(bundle_el))
    ]


def validate_new(
    id_provider,
    bundle_id,
    container_type,
    container_options,
    network_options,
    port_map,
    storage_map,
    force_options=False,
):
    """
    Validate new bundle parameters, return list of report items

    IdProvider id_provider -- elements' ids generator and uniqueness checker
    string bundle_id -- id of the bundle
    string container_type -- bundle container type
    dict container_options -- container options
    dict network_options -- network options
    list of dict port_map -- list of port mapping options
    list of dict storage_map -- list of storage mapping options
    bool force_options -- return warnings instead of forceable errors
    """
    return (
        validate.ValueId(
            "id",
            option_name_for_report="bundle name",
            # with id_provider it validates that the id is available as well
            id_provider=id_provider,
        ).validate({"id": bundle_id})
        + _validate_container(container_type, container_options, force_options)
        + _validate_network_options_new(network_options, force_options)
        + _validate_port_map_list(port_map, id_provider, force_options)
        + _validate_storage_map_list(storage_map, id_provider, force_options)
    )


def append_new(  # noqa: PLR0913
    parent_element,
    id_provider,
    bundle_id,
    container_type,
    container_options,
    network_options,
    port_map,
    storage_map,
    meta_attributes,
):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    """
    Create new bundle and add it to the CIB

    etree parent_element -- the bundle will be appended to this element
    IdProvider id_provider -- elements' ids generator
    string bundle_id -- id of the bundle
    string container_type -- bundle container type
    dict container_options -- container options
    dict network_options -- network options
    list of dict port_map -- list of port mapping options
    list of dict storage_map -- list of storage mapping options
    dict meta_attributes -- meta attributes
    """
    bundle_element = etree.SubElement(parent_element, TAG, {"id": bundle_id})
    _append_container(bundle_element, container_type, container_options)
    if network_options or port_map:
        _append_network(
            bundle_element,
            id_provider,
            bundle_id,
            network_options,
            port_map,
        )
    if storage_map:
        _append_storage(bundle_element, id_provider, bundle_id, storage_map)
    if meta_attributes:
        append_new_meta_attributes(bundle_element, meta_attributes, id_provider)
    return bundle_element


def validate_reset(
    id_provider,
    bundle_el,
    container_options,
    network_options,
    port_map,
    storage_map,
    force_options=False,
):
    """
    Validate bundle parameters, return list of report items

    IdProvider id_provider -- elements' ids generator and uniqueness checker
    etree bundle_el -- the bundle to be reset
    dict container_options -- container options
    dict network_options -- network options
    list of dict port_map -- list of port mapping options
    list of dict storage_map -- list of storage mapping options
    bool force_options -- return warnings instead of forceable errors
    """
    return (
        _validate_container_reset(bundle_el, container_options, force_options)
        + _validate_network_options_new(network_options, force_options)
        + _validate_port_map_list(port_map, id_provider, force_options)
        + _validate_storage_map_list(storage_map, id_provider, force_options)
    )


def validate_reset_to_minimal(bundle_element):
    """
    Validate removing configuration of bundle_element and keep the minimal one.

    etree bundle_element -- the bundle element that will be reset
    """
    if not _is_supported_container(_get_container_element(bundle_element)):
        return [_get_report_unsupported_container(bundle_element)]
    return []


def reset_to_minimal(bundle_element):
    """
    Remove configuration of bundle_element and keep the minimal one.

    etree bundle_element -- the bundle element that will be reset
    """
    # Elements network, storage and meta_attributes must be kept even if they
    # are without children.
    # See https://bugzilla.redhat.com/show_bug.cgi?id=1642514
    # Element of container type is required.

    # There can be other elements beside bundle configuration (e.g. primitive).
    # These elements stay untouched.
    # Like any function that manipulates with cib, this also assumes prior
    # validation that container is supported.
    for child in list(bundle_element):
        if child.tag in ["network", "storage"]:
            reset_element(child)
        if child.tag == META_ATTRIBUTES_TAG:
            reset_element(child, keep_attrs=["id"])
        if child.tag in list(GENERIC_CONTAINER_TYPES):
            # GENERIC_CONTAINER_TYPES elements require the "image" attribute to
            # be set.
            reset_element(child, keep_attrs=["image"])


def _get_report_unsupported_container(
    bundle_el: _Element, updating_options: bool = True
) -> reports.ReportItem:
    """
    Create an error report for unsupported bundle container type

    bundle_el -- bundle with an unsupported container
    updating_options -- True if this was detected when changing the bundle
    """
    return reports.ReportItem.error(
        reports.messages.ResourceBundleUnsupportedContainerType(
            bundle_el.get("id", ""),
            sorted(GENERIC_CONTAINER_TYPES),
            updating_options=updating_options,
        )
    )


def validate_update(  # noqa: PLR0913
    id_provider,
    bundle_el,
    container_options,
    network_options,
    port_map_add,
    port_map_remove,
    storage_map_add,
    storage_map_remove,
    force_options=False,
):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    """
    Validate modifying an existing bundle, return list of report items

    IdProvider id_provider -- elements' ids generator and uniqueness checker
    etree bundle_el -- the bundle to be updated
    dict container_options -- container options to modify
    dict network_options -- network options to modify
    list of dict port_map_add -- list of port mapping options to add
    list of string port_map_remove -- list of port mapping ids to remove
    list of dict storage_map_add -- list of storage mapping options to add
    list of string storage_map_remove -- list of storage mapping ids to remove
    bool force_options -- return warnings instead of forceable errors
    """
    # TODO It will probably be needed to split the following validators to
    # create and update variants. It should be done once the need exists and
    # not sooner.
    return (
        _validate_container_update(bundle_el, container_options, force_options)
        + _validate_network_update(bundle_el, network_options, force_options)
        + _validate_port_map_list(port_map_add, id_provider, force_options)
        + _validate_storage_map_list(
            storage_map_add, id_provider, force_options
        )
        + _validate_map_ids_exist(
            bundle_el, "port-mapping", "port-map", port_map_remove
        )
        + _validate_map_ids_exist(
            bundle_el, "storage-mapping", "storage-map", storage_map_remove
        )
    )


def update(  # noqa: PLR0913
    id_provider,
    bundle_el,
    container_options,
    network_options,
    port_map_add,
    port_map_remove,
    storage_map_add,
    storage_map_remove,
    meta_attributes,
):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    """
    Modify an existing bundle (does not touch encapsulated resources)

    IdProvider id_provider -- elements' ids generator and uniqueness checker
    etree bundle_el -- the bundle to be updated
    dict container_options -- container options to modify
    dict network_options -- network options to modify
    list of dict port_map_add -- list of port mapping options to add
    list of string port_map_remove -- list of port mapping ids to remove
    list of dict storage_map_add -- list of storage mapping options to add
    list of string storage_map_remove -- list of storage mapping ids to remove
    dict meta_attributes -- meta attributes to update
    """
    # Do not ever remove meta_attributes, network and storage elements, even if
    # they are empty. There may be ACLs set in pacemaker which allow "write"
    # for their children (adding, changing and removing) but not themselves. In
    # such a case, removing those elements would cause the whole change to be
    # rejected by pacemaker with a "permission denied" message.
    # https://bugzilla.redhat.com/show_bug.cgi?id=1642514

    bundle_id = bundle_el.get("id")
    update_attributes_remove_empty(
        _get_container_element(bundle_el), container_options
    )

    network_element = get_sub_element(
        bundle_el, "network", append_if_missing=False
    )
    if network_options:
        update_attributes_remove_empty(network_element, network_options)
    # It's crucial to remove port maps prior to appending new ones: If we are
    # adding a port map which in any way conflicts with another one and that
    # another one is being removed in the very same command, the removal must
    # be done first, otherwise the conflict would manifest itself (and then
    # possibly the old mapping would be removed)
    if port_map_remove:
        _remove_map_elements(
            network_element.findall("port-mapping"), port_map_remove
        )
    if port_map_add:
        for port_map_options in port_map_add:
            _append_port_map(
                network_element, id_provider, bundle_id, port_map_options
            )
    append_when_useful(bundle_el, network_element)

    storage_element = get_sub_element(
        bundle_el, "storage", append_if_missing=False
    )
    # See the comment above about removing port maps prior to adding new ones.
    if storage_map_remove:
        _remove_map_elements(
            storage_element.findall("storage-mapping"), storage_map_remove
        )
    if storage_map_add:
        for storage_map_options in storage_map_add:
            _append_storage_map(
                storage_element, id_provider, bundle_id, storage_map_options
            )
    append_when_useful(bundle_el, storage_element)

    if meta_attributes:
        arrange_first_meta_attributes(bundle_el, meta_attributes, id_provider)


def is_pcmk_remote_accessible(bundle_element):
    """
    Check whenever pacemaker remote inside the bundle is accessible from
    outside. Either a control-port or an ip-range-start have to be specified in
    the network element. Returns True if accessible, False otherwise.

    etree bundle_element -- bundle element to check
    """
    network_el = bundle_element.find("network")
    if network_el is None:
        return False

    for opt in ["control-port", "ip-range-start"]:
        if network_el.get(opt):
            return True
    return False


def add_resource(bundle_element, primitive_element):
    """
    Add an existing resource to an existing bundle

    etree bundle_element -- where to add the resource to
    etree primitive_element -- the resource to be added to the bundle
    """
    # TODO possibly split to 'validate' and 'do' functions
    # a bundle may currently contain at most one primitive resource
    inner_primitive = bundle_element.find(TAG_PRIMITIVE)
    if inner_primitive is not None:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.ResourceBundleAlreadyContainsAResource(
                    bundle_element.get("id"),
                    inner_primitive.get("id"),
                )
            )
        )
    bundle_element.append(primitive_element)


def get_inner_resource(bundle_el: _Element) -> Optional[_Element]:
    resources = cast(List[_Element], bundle_el.xpath("./primitive"))
    if resources:
        return resources[0]
    return None


def _is_supported_container(container_el):
    return (
        container_el is not None and container_el.tag in GENERIC_CONTAINER_TYPES
    )


def _validate_container(container_type, container_options, force_options=False):
    if container_type not in GENERIC_CONTAINER_TYPES:
        return [
            reports.ReportItem.error(
                reports.messages.InvalidOptionValue(
                    "container type",
                    container_type,
                    GENERIC_CONTAINER_TYPES,
                )
            )
        ]
    return _validate_generic_container_options(container_options, force_options)


def _validate_generic_container_options(container_options, force_options=False):
    validators = [
        validate.NamesIn(
            GENERIC_CONTAINER_OPTIONS,
            option_type="container",
            severity=reports.item.get_severity(
                reports.codes.FORCE, force_options
            ),
        ),
        validate.IsRequiredAll(["image"], option_type="container"),
        validate.ValueNotEmpty("image", "image name"),
        validate.ValueNonnegativeInteger("promoted-max"),
        validate.ValuePositiveInteger("replicas"),
        validate.ValuePositiveInteger("replicas-per-host"),
    ]
    return validate.ValidatorAll(validators).validate(container_options)


def _validate_container_reset(bundle_el, container_options, force_options):
    # Unlike in the case of update, in reset empty options are not necessary
    # valid - user MUST set everything (including required options e.g. image).
    if container_options and not _is_supported_container(
        _get_container_element(bundle_el)
    ):
        return [_get_report_unsupported_container(bundle_el)]
    return _validate_generic_container_options(container_options, force_options)


def _validate_container_update(bundle_el, options, force_options):
    # Validate container options only if they are being updated. Empty options
    # are valid - user DOESN'T NEED to change anything.
    if not options:
        return []

    container_el = _get_container_element(bundle_el)
    if not _is_supported_container(container_el):
        return [_get_report_unsupported_container(bundle_el)]
    return _validate_generic_container_options_update(
        container_el, options, force_options
    )


def _validate_generic_container_options_update(
    container_el, options, force_options
):
    validators_optional_options = [
        validate.ValueNonnegativeInteger("promoted-max"),
        validate.ValuePositiveInteger("replicas"),
        validate.ValuePositiveInteger("replicas-per-host"),
    ]
    for val in validators_optional_options:
        val.empty_string_valid = True
    validators = [
        validate.NamesIn(
            # allow to remove options even if they are not allowed
            GENERIC_CONTAINER_OPTIONS | _options_to_remove(options),
            option_type="container",
            severity=reports.item.get_severity(
                reports.codes.FORCE, force_options
            ),
        ),
        # image is a mandatory attribute and cannot be removed
        validate.ValueNotEmpty("image", "image name"),
    ] + validators_optional_options

    deprecation_reports = []
    # Do not allow to set promoted-max if masters is set unless masters is
    # going to be removed now. CIB only allows one of them to be set.
    if (
        options.get("promoted-max")
        and container_el.get("masters")
        and options.get("masters") != ""
    ):
        deprecation_reports.append(
            reports.ReportItem.error(
                reports.messages.PrerequisiteOptionMustNotBeSet(
                    "promoted-max", "masters", "container", "container"
                )
            )
        )

    return (
        validate.ValidatorAll(validators).validate(options)
        + deprecation_reports
    )


def _validate_network_options_new(options, force_options):
    severity = reports.item.get_severity(reports.codes.FORCE, force_options)
    validators = [
        # TODO add validators for other keys (ip-range-start - IPv4)
        validate.NamesIn(
            NETWORK_OPTIONS, option_type="network", severity=severity
        ),
        validate.ValuePortNumber("control-port"),
        # Leaving a possibility to force this validation for the case pacemaker
        # starts supporting IPv6 or other format of the netmask.
        ValueHostNetmask("host-netmask", severity=severity),
    ]
    return validate.ValidatorAll(validators).validate(options)


def _is_pcmk_remote_accessible_after_update(network_el, options):
    def removing(opt):
        return options.get(opt) == ""

    def not_adding(opt):
        return options.get(opt) is None

    port_name = "control-port"
    ip_name = "ip-range-start"
    port = network_el.get(port_name)
    ip = network_el.get(ip_name)

    # 3 cases in which pcmk remote will not be accessible after an update
    # case1: port set, IP !set; removing port, !adding IP
    case1 = port and not ip and removing(port_name) and not_adding(ip_name)
    # case2: port !set, IP set; !adding port, removing IP
    case2 = not port and ip and not_adding(port_name) and removing(ip_name)
    # case3: port set, IP set; removing port, removing IP
    case3 = port and ip and removing(port_name) and removing(ip_name)

    return not (case1 or case2 or case3)


def _validate_network_update(bundle_el, options, force_options):
    network_el = bundle_el.find("network")
    if network_el is None:
        return _validate_network_options_new(options, force_options)
    return _validate_network_options_update(
        bundle_el, network_el, options, force_options
    )


def _validate_network_options_update(
    bundle_el, network_el, options, force_options
):
    report_list = []
    inner_primitive = get_inner_resource(bundle_el)
    if (
        inner_primitive is not None
        and not _is_pcmk_remote_accessible_after_update(network_el, options)
    ):
        report_list.append(
            reports.ReportItem(
                severity=reports.item.get_severity(
                    reports.codes.FORCE,
                    force_options,
                ),
                message=reports.messages.ResourceInBundleNotAccessible(
                    bundle_el.get("id"),
                    inner_primitive.get("id"),
                ),
            )
        )

    severity = reports.item.get_severity(reports.codes.FORCE, force_options)
    validators_optional_options = [
        # TODO add validators for other keys (ip-range-start - IPv4)
        validate.ValuePortNumber("control-port"),
        # Leaving a possibility to force this validation for the case pacemaker
        # starts supporting IPv6 or other format of the netmask.
        ValueHostNetmask("host-netmask", severity=severity),
    ]
    for val in validators_optional_options:
        val.empty_string_valid = True
    validators = [
        validate.NamesIn(
            # allow to remove options even if they are not allowed
            NETWORK_OPTIONS | _options_to_remove(options),
            option_type="network",
            severity=severity,
        )
    ] + validators_optional_options

    return report_list + validate.ValidatorAll(validators).validate(options)


def _validate_port_map_list(options_list, id_provider, force_options):
    severity = reports.item.get_severity(reports.codes.FORCE, force_options)
    option_type = "port-map"
    validators = [
        validate.NamesIn(
            PORT_MAP_OPTIONS, option_type=option_type, severity=severity
        ),
        validate.ValueId(
            "id", option_name_for_report="port-map id", id_provider=id_provider
        ),
        validate.DependsOnOption(
            ["internal-port"],
            "port",
            option_type=option_type,
            prerequisite_type=option_type,
        ),
        validate.IsRequiredSome(["port", "range"], option_type=option_type),
        validate.MutuallyExclusive(["port", "range"], option_type=option_type),
        validate.ValuePortNumber("port"),
        validate.ValuePortNumber("internal-port"),
        validate.ValuePortRange("range", severity=severity),
    ]
    validator_all = validate.ValidatorAll(validators)

    report_list = []
    for options in options_list:
        report_list.extend(validator_all.validate(options))
    return report_list


def _validate_storage_map_list(options_list, id_provider, force_options):
    severity = reports.item.get_severity(reports.codes.FORCE, force_options)
    option_type = "storage-map"
    validators = [
        validate.NamesIn(
            STORAGE_MAP_OPTIONS, option_type=option_type, severity=severity
        ),
        validate.ValueId(
            "id",
            option_name_for_report="storage-map id",
            id_provider=id_provider,
        ),
        validate.IsRequiredSome(
            ["source-dir", "source-dir-root"],
            option_type=option_type,
        ),
        validate.MutuallyExclusive(
            ["source-dir", "source-dir-root"],
            option_type=option_type,
        ),
        validate.IsRequiredAll(["target-dir"], option_type=option_type),
    ]
    validator_all = validate.ValidatorAll(validators)

    report_list = []
    for options in options_list:
        report_list.extend(validator_all.validate(options))
    return report_list


def _validate_map_ids_exist(bundle_el, map_type, map_label, id_list):
    report_list = []
    for _id in id_list:
        searcher = ElementSearcher(
            map_type, _id, bundle_el, element_type_desc=map_label
        )
        if not searcher.element_found():
            report_list.extend(searcher.get_errors())
    return report_list


class ValueHostNetmask(validate.ValuePredicateBase):
    def _is_valid(self, value):
        return validate.is_integer(value, 1, 32)

    def _get_allowed_values(self):
        return "a number of bits of the mask (1..32)"


def _append_container(bundle_element, container_type, container_options):
    # Do not add options with empty values. When updating, an empty value means
    # remove the option.
    update_attributes_remove_empty(
        etree.SubElement(bundle_element, container_type),
        container_options,
    )


def _append_network(
    bundle_element, id_provider, id_base, network_options, port_map
):
    network_element = etree.SubElement(bundle_element, "network")
    # Do not add options with empty values. When updating, an empty value means
    # remove the option.
    update_attributes_remove_empty(network_element, network_options)
    for port_map_options in port_map:
        _append_port_map(
            network_element, id_provider, id_base, port_map_options
        )


def _append_port_map(parent_element, id_provider, id_base, port_map_options):
    if "id" not in port_map_options:
        id_suffix = None
        if "port" in port_map_options:
            id_suffix = port_map_options["port"]
        elif "range" in port_map_options:
            id_suffix = port_map_options["range"]
        if id_suffix:
            port_map_options["id"] = id_provider.allocate_id(
                sanitize_id(f"{id_base}-port-map-{id_suffix}")
            )
    port_map_element = etree.SubElement(parent_element, "port-mapping")
    # Do not add options with empty values. When updating, an empty value means
    # remove the option.
    update_attributes_remove_empty(port_map_element, port_map_options)
    return port_map_element


def _append_storage(bundle_element, id_provider, id_base, storage_map):
    storage_element = etree.SubElement(bundle_element, "storage")
    for storage_map_options in storage_map:
        _append_storage_map(
            storage_element,
            id_provider,
            id_base,
            storage_map_options,
        )


def _append_storage_map(
    parent_element, id_provider, id_base, storage_map_options
):
    if "id" not in storage_map_options:
        storage_map_options["id"] = id_provider.allocate_id(
            # use just numbers to keep the ids reasonably short
            f"{id_base}-storage-map"
        )
    storage_map_element = etree.SubElement(parent_element, "storage-mapping")
    # Do not add options with empty values. When updating, an empty value means
    # remove the option.
    update_attributes_remove_empty(storage_map_element, storage_map_options)
    return storage_map_element


def _get_container_element(bundle_el):
    container_el = None
    for container_type in GENERIC_CONTAINER_TYPES:
        container_el = bundle_el.find(container_type)
        if container_el is not None:
            return container_el
    return None


def _remove_map_elements(element_list, id_to_remove_list):
    for el in element_list:
        if el.get("id", "") in id_to_remove_list:
            el.getparent().remove(el)


def _options_to_remove(options):
    return {
        name
        for name, value in options.items()
        if validate.is_empty_string(value)
    }
