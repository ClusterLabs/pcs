from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.common import report_codes
from pcs.lib import validate
from pcs.lib.errors import ReportListAnalyzer
from pcs.lib.pacemaker.values import sanitize_id

TAG = "bundle"

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
            _validate_container_docker_options(container_options, force_options)
        )
    report_list.extend(
        _validate_network_options(network_options, force_options)
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
    network_options, port_map, storage_map
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
    """
    bundle_element = etree.SubElement(parent_element, TAG, {"id": bundle_id})
    # TODO call the proper function once more container_types are supported
    # by pacemaker
    _append_container_docker(bundle_element, container_options)
    if network_options or port_map:
        network_element = _append_network(bundle_element, network_options)
    for port_map_options in port_map:
        _append_port_map(
            network_element, id_provider, bundle_id, port_map_options
        )
    if storage_map:
        storage_element = _append_storage(bundle_element)
    for storage_map_options in storage_map:
        _append_storage_map(
            storage_element, id_provider, bundle_id, storage_map_options
        )
    return bundle_element

def _validate_container_type(container_type):
    return validate.value_in("type", ("docker", ), "container type")({
        "type": container_type,
    })

def _validate_container_docker_options(options, force_options):
    allowed_options = [
        "image",
        "masters",
        "network",
        "options",
        "run-command",
        "replicas",
        "replicas-per-host",
    ]
    validators = [
        validate.is_required("image", "container"),
        validate.value_nonnegative_integer("masters"),
        validate.value_positive_integer("replicas"),
        validate.value_positive_integer("replicas-per-host"),
    ]
    return (
        validate.run_collection_of_option_validators(options, validators)
        +
        validate.names_in(
            allowed_options,
            options.keys(),
            "container",
            report_codes.FORCE_OPTIONS,
            force_options
        )
    )

def _validate_network_options(options, force_options):
    allowed_options = [
        "control-port",
        "host-interface",
        "host-netmask",
        "ip-range-start",
    ]
    validators = [
        # TODO add validators for other keys (ip-range-start - IPv4)
        validate.value_port_number("control-port"),
        validate.value_cond(
            "host-netmask",
            lambda value: validate.is_integer(value, 1, 32),
            "a number of bits of the mask (1-32)",
            # Leaving a possibility to force this validation, if pacemaker
            # starts supporting IPv6 or other format of the netmask
            code_to_allow_extra_values=report_codes.FORCE_OPTIONS,
            allow_extra_values=force_options
        ),
    ]
    return (
        validate.run_collection_of_option_validators(options, validators)
        +
        validate.names_in(
            allowed_options,
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

def _append_container_docker(parent_element, docker_options):
    return etree.SubElement(parent_element, "docker", docker_options)

def _append_network(parent_element, network_options):
    return etree.SubElement(parent_element, "network", network_options)

def _append_storage(parent_element):
    return etree.SubElement(parent_element, "storage")

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
    return etree.SubElement(parent_element, "port-mapping", port_map_options)

def _append_storage_map(
    parent_element, id_provider, id_base, storage_map_options
):
    if "id" not in storage_map_options:
        storage_map_options["id"] = id_provider.allocate_id(
            # use just numbers to keep the ids reasonably short
            "{0}-storage-map".format(id_base)
        )
    return etree.SubElement(
        parent_element, "storage-mapping", storage_map_options
    )
