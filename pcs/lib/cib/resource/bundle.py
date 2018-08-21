from lxml import etree

from pcs.common import report_codes
from pcs.lib import reports, validate
from pcs.lib.cib.nvpair import (
    append_new_meta_attributes,
    arrange_first_meta_attributes,
)
from pcs.lib.cib.resource.primitive import TAG as TAG_PRIMITIVE
from pcs.lib.cib.tools import find_element_by_tag_and_id
from pcs.lib.errors import (
    LibraryError,
    ReportListAnalyzer,
)
from pcs.lib.pacemaker.values import sanitize_id
from pcs.lib.xml_tools import (
    get_sub_element,
    update_attributes_remove_empty,
    remove_when_pointless,
)

TAG = "bundle"

_docker_options = set((
    "image",
    "masters",
    "network",
    "options",
    "run-command",
    "replicas",
    "replicas-per-host",
))

_network_options = set((
    "control-port",
    "host-interface",
    "host-netmask",
    "ip-range-start",
))

def is_bundle(resource_el):
    return resource_el.tag == TAG

def validate_new(
    id_provider, bundle_id, container_type, container_options, network_options,
    port_map, storage_map, force_options=False
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
    report_list = []

    report_list.extend(
        validate.run_collection_of_option_validators(
            {"id": bundle_id},
            [
                # with id_provider it validates that the id is available as well
                validate.value_id("id", "bundle name", id_provider),
            ]
        )
    )

    aux_reports = _validate_container_type(container_type)
    report_list.extend(aux_reports)
    if not ReportListAnalyzer(aux_reports).error_list:
        report_list.extend(
            # TODO call the proper function once more container_types are
            # supported by pacemaker
            _validate_container_docker_options_new(
                container_options,
                force_options
            )
        )
    report_list.extend(
        _validate_network_options_new(network_options, force_options)
    )
    report_list.extend(
        _validate_port_map_list(port_map, id_provider, force_options)
    )
    report_list.extend(
        _validate_storage_map_list(storage_map, id_provider, force_options)
    )

    return report_list

def append_new(
    parent_element, id_provider, bundle_id, container_type, container_options,
    network_options, port_map, storage_map, meta_attributes
):
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
    # TODO create the proper element once more container_types are supported
    # by pacemaker
    if container_type == 'docker':
        container_element = etree.SubElement(bundle_element, "docker")
    elif container_type == 'podman':
        container_element = etree.SubElement(bundle_element, "podman")
    # Do not add options with empty values. When updating, an empty value means
    # remove the option.
    update_attributes_remove_empty(container_element, container_options)
    if network_options or port_map:
        network_element = etree.SubElement(bundle_element, "network")
        # Do not add options with empty values. When updating, an empty value
        # means remove the option.
        update_attributes_remove_empty(network_element, network_options)
    for port_map_options in port_map:
        _append_port_map(
            network_element, id_provider, bundle_id, port_map_options
        )
    if storage_map:
        storage_element = etree.SubElement(bundle_element, "storage")
    for storage_map_options in storage_map:
        _append_storage_map(
            storage_element, id_provider, bundle_id, storage_map_options
        )
    if meta_attributes:
        append_new_meta_attributes(bundle_element, meta_attributes, id_provider)
    return bundle_element

def validate_update(
    id_provider, bundle_el, container_options, network_options,
    port_map_add, port_map_remove, storage_map_add, storage_map_remove,
    force_options=False
):
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
    report_list = []

    container_el = _get_container_element(bundle_el)
    if container_el.tag == "docker":
        # TODO call the proper function once more container types are
        # supported by pacemaker
        report_list.extend(
            _validate_container_docker_options_update(
                container_el,
                container_options,
                force_options
            )
        )

    network_el = bundle_el.find("network")
    if network_el is None:
        report_list.extend(
            _validate_network_options_new(network_options, force_options)
        )
    else:
        report_list.extend(
            _validate_network_options_update(
                bundle_el,
                network_el,
                network_options,
                force_options
            )
        )

    # TODO It will probably be needed to split the following validators to
    # create and update variants. It should be done once the need exists and
    # not sooner.
    report_list.extend(
        _validate_port_map_list(port_map_add, id_provider, force_options)
    )
    report_list.extend(
        _validate_storage_map_list(storage_map_add, id_provider, force_options)
    )
    report_list.extend(
        _validate_map_ids_exist(
            bundle_el, "port-mapping", "port-map", port_map_remove
        )
    )
    report_list.extend(
        _validate_map_ids_exist(
            bundle_el, "storage-mapping", "storage-map", storage_map_remove
        )
    )
    return report_list

def update(
    id_provider, bundle_el, container_options, network_options,
    port_map_add, port_map_remove, storage_map_add, storage_map_remove,
    meta_attributes
):
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
    bundle_id = bundle_el.get("id")
    update_attributes_remove_empty(
        _get_container_element(bundle_el),
        container_options
    )

    network_element = get_sub_element(bundle_el, "network")
    if network_options:
        update_attributes_remove_empty(network_element, network_options)
    # It's crucial to remove port maps prior to appending new ones: If we are
    # adding a port map which in any way conflicts with another one and that
    # another one is being removed in the very same command, the removal must
    # be done first, otherwise the conflict would manifest itself (and then
    # possibly the old mapping would be removed)
    if port_map_remove:
        _remove_map_elements(
            network_element.findall("port-mapping"),
            port_map_remove
        )
    for port_map_options in port_map_add:
        _append_port_map(
            network_element, id_provider, bundle_id, port_map_options
        )

    storage_element = get_sub_element(bundle_el, "storage")
    # See the comment above about removing port maps prior to adding new ones.
    if storage_map_remove:
        _remove_map_elements(
            storage_element.findall("storage-mapping"),
            storage_map_remove
        )
    for storage_map_options in storage_map_add:
        _append_storage_map(
            storage_element, id_provider, bundle_id, storage_map_options
        )

    if meta_attributes:
        arrange_first_meta_attributes(bundle_el, meta_attributes)

    # remove empty elements with no attributes
    # meta attributes are handled in their own function
    remove_when_pointless(network_element)
    remove_when_pointless(storage_element)

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
        raise LibraryError(reports.resource_bundle_already_contains_a_resource(
            bundle_element.get("id"), inner_primitive.get("id")
        ))
    bundle_element.append(primitive_element)

def get_inner_resource(bundle_el):
    resources = bundle_el.xpath("./primitive")
    if resources:
        return resources[0]
    return None

def _validate_container_type(container_type):
    return validate.value_in("type", ("docker", "podman"), "container type")({
        "type": container_type,
    })

def _validate_container_docker_options_new(options, force_options):
    validators = [
        validate.is_required("image", "container"),
        validate.value_not_empty("image", "image name"),
        validate.value_nonnegative_integer("masters"),
        validate.value_positive_integer("replicas"),
        validate.value_positive_integer("replicas-per-host"),
    ]
    return (
        validate.run_collection_of_option_validators(options, validators)
        +
        validate.names_in(
            _docker_options,
            options.keys(),
            "container",
            report_codes.FORCE_OPTIONS,
            force_options
        )
    )

def _validate_container_docker_options_update(
    docker_el, options, force_options
):
    validators = [
        # image is a mandatory attribute and cannot be removed
        validate.value_not_empty("image", "image name"),
        validate.value_empty_or_valid(
            "masters",
            validate.value_nonnegative_integer("masters")
        ),
        validate.value_empty_or_valid(
            "replicas",
            validate.value_positive_integer("replicas")
        ),
        validate.value_empty_or_valid(
            "replicas-per-host",
            validate.value_positive_integer("replicas-per-host")
        ),
    ]
    return (
        validate.run_collection_of_option_validators(options, validators)
        +
        validate.names_in(
            # allow to remove options even if they are not allowed
            _docker_options | _options_to_remove(options),
            options.keys(),
            "container",
            report_codes.FORCE_OPTIONS,
            force_options
        )
    )

def _validate_network_options_new(options, force_options):
    validators = [
        # TODO add validators for other keys (ip-range-start - IPv4)
        validate.value_port_number("control-port"),
        _value_host_netmask("host-netmask", force_options),
    ]
    return (
        validate.run_collection_of_option_validators(options, validators)
        +
        validate.names_in(
            _network_options,
            options.keys(),
            "network",
            report_codes.FORCE_OPTIONS,
            force_options
        )
    )

def _is_pcmk_remote_acccessible_after_update(network_el, options):
    port_name = "control-port"
    ip_name = "ip-range-start"
    port = network_el.get(port_name)
    ip = network_el.get(ip_name)
    removing = lambda opt: options.get(opt) == ""
    not_adding = lambda opt: options.get(opt) is None

    # 3 cases in which pcmk remote will not be accessible after an update
    # case1: port set, IP !set; removing port, !adding IP
    case1 = port and not ip and removing(port_name) and not_adding(ip_name)
    # case2: port !set, IP set; !adding port, removing IP
    case2 = not port and ip and not_adding(port_name) and removing(ip_name)
    # case3: port set, IP set; removing port, removing IP
    case3 = port and ip and removing(port_name) and removing(ip_name)

    return not (case1 or case2 or case3)

def _validate_network_options_update(
    bundle_el, network_el, options, force_options
):
    report_list = []
    inner_primitive = get_inner_resource(bundle_el)
    if (
        inner_primitive is not None
        and
        not _is_pcmk_remote_acccessible_after_update(network_el, options)
    ):
        report_list.append(
            reports.get_problem_creator(
                report_codes.FORCE_OPTIONS, force_options
            )(
                reports.resource_in_bundle_not_accessible,
                bundle_el.get("id"),
                inner_primitive.get("id")
            )
        )
    validators = [
        # TODO add validators for other keys (ip-range-start - IPv4)
        validate.value_empty_or_valid(
            "control-port",
            validate.value_port_number("control-port"),
        ),
        validate.value_empty_or_valid(
            "host-netmask",
            _value_host_netmask("host-netmask", force_options),
        ),
    ]
    return (
        report_list
        +
        validate.run_collection_of_option_validators(options, validators)
        +
        validate.names_in(
            # allow to remove options even if they are not allowed
            _network_options | _options_to_remove(options),
            options.keys(),
            "network",
            report_codes.FORCE_OPTIONS,
            force_options
        )
    )

def _validate_port_map_list(options_list, id_provider, force_options):
    allowed_options = [
        "id",
        "port",
        "internal-port",
        "range",
    ]
    validators = [
        validate.value_id("id", "port-map id", id_provider),
        validate.depends_on_option(
            "internal-port", "port", "port-map", "port-map"
        ),
        validate.is_required_some_of(["port", "range"], "port-map"),
        validate.mutually_exclusive(["port", "range"], "port-map"),
        validate.value_port_number("port"),
        validate.value_port_number("internal-port"),
        validate.value_port_range(
            "range",
            code_to_allow_extra_values=report_codes.FORCE_OPTIONS,
            allow_extra_values=force_options
        ),
    ]
    report_list = []
    for options in options_list:
        report_list.extend(
            validate.run_collection_of_option_validators(options, validators)
            +
            validate.names_in(
                allowed_options,
                options.keys(),
                "port-map",
                report_codes.FORCE_OPTIONS,
                force_options
            )
        )
    return report_list

def _validate_storage_map_list(options_list, id_provider, force_options):
    allowed_options = [
        "id",
        "options",
        "source-dir",
        "source-dir-root",
        "target-dir",
    ]
    source_dir_options = ["source-dir", "source-dir-root"]
    validators = [
        validate.value_id("id", "storage-map id", id_provider),
        validate.is_required_some_of(source_dir_options, "storage-map"),
        validate.mutually_exclusive(source_dir_options, "storage-map"),
        validate.is_required("target-dir", "storage-map"),
    ]
    report_list = []
    for options in options_list:
        report_list.extend(
            validate.run_collection_of_option_validators(options, validators)
            +
            validate.names_in(
                allowed_options,
                options.keys(),
                "storage-map",
                report_codes.FORCE_OPTIONS,
                force_options
            )
        )
    return report_list

def _validate_map_ids_exist(bundle_el, map_type, map_label, id_list):
    report_list = []
    for id in id_list:
        try:
            find_element_by_tag_and_id(
                map_type, bundle_el, id, id_types=[map_label]
            )
        except LibraryError as e:
            report_list.extend(e.args)
    return report_list

def _value_host_netmask(option_name, force_options):
    return validate.value_cond(
        option_name,
        lambda value: validate.is_integer(value, 1, 32),
        "a number of bits of the mask (1-32)",
        # Leaving a possibility to force this validation, if pacemaker
        # starts supporting IPv6 or other format of the netmask
        code_to_allow_extra_values=report_codes.FORCE_OPTIONS,
        allow_extra_values=force_options
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
                sanitize_id("{0}-port-map-{1}".format(id_base, id_suffix))
            )
    port_map_element = etree.SubElement(parent_element, "port-mapping")
    # Do not add options with empty values. When updating, an empty value means
    # remove the option.
    update_attributes_remove_empty(port_map_element, port_map_options)
    return port_map_element

def _append_storage_map(
    parent_element, id_provider, id_base, storage_map_options
):
    if "id" not in storage_map_options:
        storage_map_options["id"] = id_provider.allocate_id(
            # use just numbers to keep the ids reasonably short
            "{0}-storage-map".format(id_base)
        )
    storage_map_element = etree.SubElement(parent_element, "storage-mapping")
    # Do not add options with empty values. When updating, an empty value means
    # remove the option.
    update_attributes_remove_empty(storage_map_element, storage_map_options)
    return storage_map_element

def _get_container_element(bundle_el):
    # TODO get different types of container once supported by pacemaker
    return bundle_el.find("docker")

def _remove_map_elements(element_list, id_to_remove_list):
    for el in element_list:
        if el.get("id", "") in id_to_remove_list:
            el.getparent().remove(el)

def _options_to_remove(options):
    return set([
        name for name, value in options.items()
        if validate.is_empty_string(value)
    ])
