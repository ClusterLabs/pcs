import base64
import os.path
from functools import partial

from pcs import settings
from pcs.common.reports import SimpleReportProcessor
from pcs.common.tools import join_multilines
from pcs.lib import external, reports, tools
from pcs.lib.cib.resource import primitive, group
from pcs.lib.booth import (
    config_files,
    config_validators,
    reports as booth_reports,
    resource,
    status,
)
from pcs.lib.booth.config_facade import ConfigFacade
from pcs.lib.booth.config_parser import parse, build
from pcs.lib.booth.env import get_config_file_name
from pcs.lib.cib.tools import get_resources, IdProvider
from pcs.lib.communication.booth import (
    BoothGetConfig,
    BoothSendConfig,
)
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.errors import LibraryError, ReportItemSeverity
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.resource_agent import find_valid_resource_agent_by_name


def config_setup(env, site_list, arbitrator_list, overwrite_existing=False):
    """
    create booth configuration

    LibraryEnvironment env
    list site_list -- site adresses of multisite
    list arbitrator_list -- arbitrator adresses of multisite
    bool overwrite_existing -- allow overwriting existing files
    """
    report_processor = SimpleReportProcessor(env.report_processor)
    report_processor.report_list(
        config_validators.create(site_list, arbitrator_list)
    )
    if report_processor.has_errors:
        raise LibraryError()

    booth_conf = ConfigFacade.create(site_list, arbitrator_list)
    env.booth.create_key(
        tools.generate_binary_key(
            random_bytes_count=settings.booth_authkey_bytes
        ),
        overwrite_existing
    )
    booth_conf.set_authfile(env.booth.key_path)
    env.booth.create_config(build(booth_conf.config), overwrite_existing)

def config_destroy(env, ignore_config_load_problems=False):
    env.booth.command_expect_live_env()
    if not env.is_cib_live:
        raise LibraryError(reports.live_environment_required(["CIB"]))

    name = env.booth.name
    config_is_used = partial(booth_reports.booth_config_is_used, name)

    report_list = []

    if resource.find_for_config(
        get_resources(env.get_cib()),
        get_config_file_name(name),
    ):
        report_list.append(config_is_used("in cluster resource"))

    #Only systemd is currently supported. Initd does not supports multiple
    #instances (here specified by name)
    if external.is_systemctl():
        if external.is_service_running(env.cmd_runner(), "booth", name):
            report_list.append(config_is_used("(running in systemd)"))

        if external.is_service_enabled(env.cmd_runner(), "booth", name):
            report_list.append(config_is_used("(enabled in systemd)"))

    if report_list:
        raise LibraryError(*report_list)

    authfile_path = None
    try:
        booth_conf = ConfigFacade(parse(env.booth.get_config_content()))
        authfile_path = booth_conf.get_authfile()
    except LibraryError:
        if not ignore_config_load_problems:
            raise LibraryError(booth_reports.booth_cannot_identify_keyfile())

        #if content not received, not valid,... still remove config needed
        env.report_processor.process(
            booth_reports.booth_cannot_identify_keyfile(
                severity=ReportItemSeverity.WARNING
            )
        )

    if(
        authfile_path
        and
        os.path.dirname(authfile_path) == settings.booth_config_dir
    ):
        env.booth.set_key_path(authfile_path)
        env.booth.remove_key()
    env.booth.remove_config()


def config_text(env, node_name=None):
    """
    get configuration in raw format
    string node_name -- get the config from specified node or local host if None
    """
    if node_name is None:
        # TODO add name support
        return env.booth.get_config_content()

    name = env.booth.name

    com_cmd = BoothGetConfig(env.report_processor, name)
    com_cmd.set_targets([
        env.get_node_target_factory().get_target_from_hostname(node_name)
    ])
    # pylint: disable=unsubscriptable-object
    # In general, pylint is right. And it cannot know in this case code is OK.
    # It is covered by tests.
    remote_data = run_and_raise(env.get_node_communicator(), com_cmd)[0][1]
    try:
        return remote_data["config"]["data"]
    except KeyError:
        raise LibraryError(reports.invalid_response_format(node_name))


def config_ticket_add(env, ticket_name, options, allow_unknown_options=False):
    """
    add a ticket to booth configuration

    LibraryEnvironment env
    string ticket_name -- the name of the ticket to be created
    dict options -- options for the ticket
    bool allow_unknown_options -- allow using options unknown to pcs
    """
    report_processor = SimpleReportProcessor(env.report_processor)
    booth_conf = ConfigFacade(parse(env.booth.get_config_content()))
    report_processor.report_list(
        config_validators.add_ticket(
            booth_conf,
            ticket_name,
            options,
            allow_unknown_options=allow_unknown_options
        )
    )
    if report_processor.has_errors:
        raise LibraryError()

    booth_conf.add_ticket(ticket_name, options)
    env.booth.push_config(build(booth_conf.config))

def config_ticket_remove(env, ticket_name):
    """
    remove a ticket from booth configuration

    LibraryEnvironment env
    string ticket_name -- the name of the ticket to be removed
    """
    report_processor = SimpleReportProcessor(env.report_processor)
    booth_conf = ConfigFacade(parse(env.booth.get_config_content()))
    report_processor.report_list(
        config_validators.remove_ticket(booth_conf, ticket_name)
    )
    if report_processor.has_errors:
        raise LibraryError()
    booth_conf.remove_ticket(ticket_name)
    env.booth.push_config(build(booth_conf.config))

def create_in_cluster(env, ip, allow_absent_resource_agent=False):
    """
    Create group with ip resource and booth resource

    LibraryEnvironment env provides all for communication with externals
    string ip determines float ip for the operation of the booth
    bool allow_absent_resource_agent is flag allowing create booth resource even
        if its agent is not installed
    """
    resources_section = get_resources(env.get_cib())
    id_provider = IdProvider(resources_section)
    name = env.booth.name

    booth_config_file_path = get_config_file_name(name)
    if resource.find_for_config(resources_section, booth_config_file_path):
        raise LibraryError(booth_reports.booth_already_in_cib(name))

    create_id = partial(
        resource.create_resource_id,
        resources_section,
        name
    )
    get_agent = partial(
        find_valid_resource_agent_by_name,
        env.report_processor,
        env.cmd_runner(),
        allowed_absent=allow_absent_resource_agent
    )
    create_primitive = partial(
        primitive.create,
        env.report_processor,
        resources_section,
        id_provider
    )
    into_booth_group = partial(
        group.place_resource,
        group.provide_group(resources_section, create_id("group")),
    )

    into_booth_group(create_primitive(
        create_id("ip"),
        get_agent("ocf:heartbeat:IPaddr2"),
        instance_attributes={"ip": ip},
    ))
    into_booth_group(create_primitive(
        create_id("service"),
        get_agent("ocf:pacemaker:booth-site"),
        instance_attributes={"config": booth_config_file_path},
    ))

    env.push_cib()

def remove_from_cluster(env, resource_remove, allow_remove_multiple):
    #TODO resource_remove is provisional hack until resources are not moved to
    #lib
    resource.get_remover(resource_remove)(
        _find_resource_elements_for_operation(
            env, env.booth.name, allow_remove_multiple
        )
    )

def restart(env, resource_restart, allow_multiple):
    #TODO resource_restart is provisional hack until resources are not moved to
    #lib
    for booth_element in _find_resource_elements_for_operation(
        env, env.booth.name, allow_multiple
    ):
        resource_restart([booth_element.attrib["id"]])

def _ticket_operation(operation, env, ticket, site_ip):
    if not env.is_cib_live:
        raise LibraryError(reports.live_environment_required(["CIB"]))
    if not site_ip:
        site_ip_list = resource.find_bound_ip(
            get_resources(env.get_cib()),
            get_config_file_name(env.booth.name)
        )
        if len(site_ip_list) != 1:
            raise LibraryError(
                booth_reports.booth_cannot_determine_local_site_ip()
            )
        site_ip = site_ip_list[0]

    stdout, stderr, return_code = env.cmd_runner().run([
        settings.booth_binary, operation,
        "-s", site_ip,
        ticket
    ])

    if return_code != 0:
        raise LibraryError(
            booth_reports.booth_ticket_operation_failed(
                operation,
                join_multilines([stderr, stdout]),
                site_ip,
                ticket
            )
        )

ticket_grant = partial(_ticket_operation, "grant")
ticket_revoke = partial(_ticket_operation, "revoke")

def config_sync(env, skip_offline_nodes=False):
    """
    Send specified local booth configuration to all nodes in cluster.

    env -- LibraryEnvironment
    skip_offline_nodes -- if True offline nodes will be skipped
    """
    config = env.booth.get_config_content()
    booth_conf = ConfigFacade(parse(config))
    authfile_path = booth_conf.get_authfile()
    authfile_content = config_files.read_authfile(
        env.report_processor, authfile_path
    )

    cluster_nodes_names, report_list = get_existing_nodes_names(
        env.get_corosync_conf()
    )
    if not cluster_nodes_names:
        report_list.append(reports.corosync_config_no_nodes_defined())
    env.report_processor.process_list(report_list)

    com_cmd = BoothSendConfig(
        env.report_processor,
        env.booth.name,
        config,
        authfile=authfile_path,
        authfile_data=authfile_content,
        skip_offline_targets=skip_offline_nodes
    )
    com_cmd.set_targets(
        env.get_node_target_factory().get_target_list(
            cluster_nodes_names,
            skip_non_existing=skip_offline_nodes,
        )
    )
    run_and_raise(env.get_node_communicator(), com_cmd)


def enable_booth(env):
    """
    Enable specified instance of booth service. Currently it is supported only
    systemd systems.

    env -- LibraryEnvironment
    """
    external.ensure_is_systemd()
    name = env.booth.name
    try:
        external.enable_service(env.cmd_runner(), "booth", name)
    except external.EnableServiceError as e:
        raise LibraryError(reports.service_enable_error(
            "booth", e.message, instance=name
        ))
    env.report_processor.process(reports.service_enable_success(
        "booth", instance=name
    ))


def disable_booth(env):
    """
    Disable specified instance of booth service. Currently it is supported only
    systemd systems.

    env -- LibraryEnvironment
    """
    external.ensure_is_systemd()
    name = env.booth.name
    try:
        external.disable_service(env.cmd_runner(), "booth", name)
    except external.DisableServiceError as e:
        raise LibraryError(reports.service_disable_error(
            "booth", e.message, instance=name
        ))
    env.report_processor.process(reports.service_disable_success(
        "booth", instance=name
    ))


def start_booth(env):
    """
    Start specified instance of booth service. Currently it is supported only
    systemd systems. On non systems it can be run like this:
        BOOTH_CONF_FILE=<booth-file-path> /etc/initd/booth-arbitrator

    env -- LibraryEnvironment
    """
    external.ensure_is_systemd()
    name = env.booth.name
    try:
        external.start_service(env.cmd_runner(), "booth", name)
    except external.StartServiceError as e:
        raise LibraryError(reports.service_start_error(
            "booth", e.message, instance=name
        ))
    env.report_processor.process(reports.service_start_success(
        "booth", instance=name
    ))


def stop_booth(env):
    """
    Stop specified instance of booth service. Currently it is supported only
    systemd systems.

    env -- LibraryEnvironment
    """
    external.ensure_is_systemd()
    name = env.booth.name
    try:
        external.stop_service(env.cmd_runner(), "booth", name)
    except external.StopServiceError as e:
        raise LibraryError(reports.service_stop_error(
            "booth", e.message, instance=name
        ))
    env.report_processor.process(reports.service_stop_success(
        "booth", instance=name
    ))


def pull_config(env, node_name):
    """
    Get config from specified node and save it on local system. It will
    rewrite existing files.

    env -- LibraryEnvironment
    node_name -- string, name of node from which config should be fetched
    """
    name = env.booth.name
    env.report_processor.process(
        booth_reports.booth_fetching_config_from_node_started(node_name, name)
    )
    com_cmd = BoothGetConfig(env.report_processor, name)
    com_cmd.set_targets([
        env.get_node_target_factory().get_target_from_hostname(node_name)
    ])
    # pylint: disable=unsubscriptable-object
    # In general, pylint is right. And it cannot know in this case code is OK.
    # It is covered by tests.
    output = run_and_raise(env.get_node_communicator(), com_cmd)[0][1]
    try:
        env.booth.create_config(output["config"]["data"], True)
        if (
            output["authfile"]["name"] is not None and
            output["authfile"]["data"]
        ):
            env.booth.set_key_path(os.path.join(
                settings.booth_config_dir, output["authfile"]["name"]
            ))
            env.booth.create_key(
                base64.b64decode(
                    output["authfile"]["data"].encode("utf-8")
                ),
                True
            )
        env.report_processor.process(
            booth_reports.booth_config_accepted_by_node(name_list=[name])
        )
    except KeyError:
        raise LibraryError(reports.invalid_response_format(node_name))


def get_status(env):
    name = env.booth.name
    return {
        "status": status.get_daemon_status(env.cmd_runner(), name),
        "ticket": status.get_tickets_status(env.cmd_runner(), name),
        "peers": status.get_peers_status(env.cmd_runner(), name),
    }

def _find_resource_elements_for_operation(env, name, allow_multiple):
    booth_element_list = resource.find_for_config(
        get_resources(env.get_cib()),
        get_config_file_name(name),
    )

    if not booth_element_list:
        raise LibraryError(booth_reports.booth_not_exists_in_cib(name))

    if len(booth_element_list) > 1:
        if not allow_multiple:
            raise LibraryError(booth_reports.booth_multiple_times_in_cib(name))
        env.report_processor.process(
            booth_reports.booth_multiple_times_in_cib(
                name,
                severity=ReportItemSeverity.WARNING,
            )
        )

    return booth_element_list
