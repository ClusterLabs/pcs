import base64
import os.path
from functools import partial

from pcs import settings
from pcs.common import (
    file_type_codes,
    report_codes,
)
from pcs.common.file import FileAlreadyExists, RawFileError
from pcs.common.reports import SimpleReportProcessor
from pcs.common.tools import join_multilines
from pcs.lib import external, reports, tools
from pcs.lib.cib.resource import primitive, group
from pcs.lib.booth import (
    config_files,
    config_validators,
    constants,
    reports as booth_reports,
    resource,
    status,
)
from pcs.lib.cib.tools import get_resources, IdProvider
from pcs.lib.communication.booth import (
    BoothGetConfig,
    BoothSendConfig,
)
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.errors import LibraryError, ReportItemSeverity
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import GhostFile, raw_file_error_report
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.resource_agent import find_valid_resource_agent_by_name


def config_setup(
    env, site_list, arbitrator_list, instance_name=None,
    overwrite_existing=False
):
    """
    create booth configuration

    LibraryEnvironment env
    list site_list -- site adresses of multisite
    list arbitrator_list -- arbitrator adresses of multisite
    string instance_name -- booth instance name
    bool overwrite_existing -- allow overwriting existing files
    """
    instance_name = instance_name or constants.DEFAULT_INSTANCE_NAME
    report_processor = SimpleReportProcessor(env.report_processor)

    report_processor.report_list(
        config_validators.check_instance_name(instance_name)
    )
    report_processor.report_list(
        config_validators.create(site_list, arbitrator_list)
    )
    if report_processor.has_errors:
        raise LibraryError()

    booth_env = env.get_booth_env(instance_name)

    booth_conf = booth_env.create_facade(site_list, arbitrator_list)
    booth_conf.set_authfile(booth_env.key_path)

    report_creator = reports.get_problem_creator(
        force_code=report_codes.FORCE_FILE_OVERWRITE,
        is_forced=overwrite_existing
    )
    try:
        booth_env.key.write_raw(
            tools.generate_binary_key(
                random_bytes_count=settings.booth_authkey_bytes
            ),
            can_overwrite=overwrite_existing
        )
        booth_env.config.write_facade(
            booth_conf,
            can_overwrite=overwrite_existing
        )
    except FileAlreadyExists as e:
        report_processor.report(
            report_creator(
                reports.file_already_exists,
                e.metadata.file_type_code,
                e.metadata.path,
            )
        )
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))
    if report_processor.has_errors:
        raise LibraryError()


def config_destroy(env, instance_name=None, ignore_config_load_problems=False):
    # pylint: disable=too-many-branches
    """
    remove booth configuration files

    LibraryEnvironment env
    string instance_name -- booth instance name
    bool ignore_config_load_problems -- delete as much as possible when unable
            to read booth configs for the given booth instance
    """
    report_processor = SimpleReportProcessor(env.report_processor)
    booth_env = env.get_booth_env(instance_name)
    instance_name = booth_env.instance_name
    _ensure_live_env(env, booth_env)

    # TODO use constants in reports
    config_is_used = partial(booth_reports.booth_config_is_used, instance_name)
    if resource.find_for_config(
        get_resources(env.get_cib()),
        booth_env.config_path,
    ):
        report_processor.report(config_is_used("in cluster resource"))
    # Only systemd is currently supported. Initd does not supports multiple
    # instances (here specified by name)
    if external.is_systemctl():
        if external.is_service_running(
            env.cmd_runner(), "booth", instance_name
        ):
            report_processor.report(config_is_used("(running in systemd)"))

        if external.is_service_enabled(
            env.cmd_runner(), "booth", instance_name
        ):
            report_processor.report(config_is_used("(enabled in systemd)"))
    if report_processor.has_errors:
        raise LibraryError()

    try:
        authfile_path = None
        booth_conf = booth_env.config.read_to_facade()
        authfile_path = booth_conf.get_authfile()
    except RawFileError as e:
        report_processor.report(
            raw_file_error_report(
                e,
                force_code=report_codes.FORCE_BOOTH_DESTROY,
                is_forced_or_warning=ignore_config_load_problems,
            )
        )
    except ParserErrorException as e:
        report_processor.report_list(
            booth_env.config.parser_exception_to_report_list(
                e,
                force_code=report_codes.FORCE_BOOTH_DESTROY,
                is_forced_or_warning=ignore_config_load_problems,
            )
        )
    if report_processor.has_errors:
        raise LibraryError()

    if authfile_path:
        authfile_dir, authfile_name = os.path.split(authfile_path)
        if (authfile_dir == settings.booth_config_dir) and authfile_name:
            try:
                key_file = FileInstance.for_booth_key(authfile_name)
                key_file.raw_file.remove(fail_if_file_not_found=False)
            except RawFileError as e:
                report_processor.report(
                    raw_file_error_report(
                        e,
                        force_code=report_codes.FORCE_BOOTH_DESTROY,
                        is_forced_or_warning=ignore_config_load_problems,
                    )
                )
        else:
            report_processor.report(
                booth_reports.booth_unsupported_file_location(
                    authfile_path,
                    settings.booth_config_dir,
                    file_type_codes.BOOTH_KEY,
                )
            )
    if report_processor.has_errors:
        raise LibraryError()

    try:
        booth_env.config.raw_file.remove()
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))

    if report_processor.has_errors:
        raise LibraryError()


def config_text(env, instance_name=None, node_name=None):
    """
    get configuration in raw format

    string instance_name -- booth instance name
    string node_name -- get the config from specified node or local host if None
    """
    report_processor = SimpleReportProcessor(env.report_processor)
    booth_env = env.get_booth_env(instance_name)
    instance_name = booth_env.instance_name
    # It does not make any sense for the cli to read a ghost file and send it
    # to lib so that the lib could return it unchanged to cli. Just use 'cat'.
    # When node_name is specified, using ghost files doesn't make any sense
    # either.
    _ensure_live_env(env, booth_env)

    if node_name is None:
        try:
            return booth_env.config.read_raw()
        except RawFileError as e:
            report_processor.report(raw_file_error_report(e))
        if report_processor.has_errors:
            raise LibraryError()

    com_cmd = BoothGetConfig(env.report_processor, instance_name)
    com_cmd.set_targets([
        env.get_node_target_factory().get_target_from_hostname(node_name)
    ])
    # pylint: disable=unsubscriptable-object
    # In general, pylint is right. And it cannot know in this case code is OK.
    # It is covered by tests.
    remote_data = run_and_raise(env.get_node_communicator(), com_cmd)[0][1]
    try:
        # TODO switch to new file transfer commands (not implemented yet)
        # which send and receive configs as bytes instead of strings
        return remote_data["config"]["data"].encode("utf-8")
    except KeyError:
        raise LibraryError(reports.invalid_response_format(node_name))


def config_ticket_add(
    env, ticket_name, options, instance_name=None, allow_unknown_options=False
):
    """
    add a ticket to booth configuration

    LibraryEnvironment env
    string ticket_name -- the name of the ticket to be created
    dict options -- options for the ticket
    string instance_name -- booth instance name
    bool allow_unknown_options -- allow using options unknown to pcs
    """
    report_processor = SimpleReportProcessor(env.report_processor)
    booth_env = env.get_booth_env(instance_name)
    try:
        booth_conf = booth_env.config.read_to_facade()
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
        booth_env.config.write_facade(booth_conf, can_overwrite=True)
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))
    except ParserErrorException as e:
        report_processor.report_list(
            booth_env.config.parser_exception_to_report_list(e)
        )
    if report_processor.has_errors:
        raise LibraryError()


def config_ticket_remove(env, ticket_name, instance_name=None):
    """
    remove a ticket from booth configuration

    LibraryEnvironment env
    string ticket_name -- the name of the ticket to be removed
    string instance_name -- booth instance name
    """
    report_processor = SimpleReportProcessor(env.report_processor)
    booth_env = env.get_booth_env(instance_name)
    try:
        booth_conf = booth_env.config.read_to_facade()
        report_processor.report_list(
            config_validators.remove_ticket(booth_conf, ticket_name)
        )
        if report_processor.has_errors:
            raise LibraryError()
        booth_conf.remove_ticket(ticket_name)
        booth_env.config.write_facade(booth_conf, can_overwrite=True)
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))
    except ParserErrorException as e:
        report_processor.report_list(
            booth_env.config.parser_exception_to_report_list(e)
        )
    if report_processor.has_errors:
        raise LibraryError()


def create_in_cluster(
    env, ip, instance_name=None, allow_absent_resource_agent=False
):
    """
    Create group with ip resource and booth resource

    LibraryEnvironment env -- provides all for communication with externals
    string ip -- float ip address for the operation of the booth
    string instance_name -- booth instance name
    bool allow_absent_resource_agent -- allowing creating booth resource even
        if its agent is not installed
    """
    report_processor = SimpleReportProcessor(env.report_processor)
    booth_env = env.get_booth_env(instance_name)
    # Booth config path goes to CIB. Working with a mocked booth configs would
    # not work coorectly as the path would point to a mock file (the path to a
    # mock file is unknown to us in the lib anyway)
    # It makes sense to work with a mocked CIB, though. Users can do other
    # changes to the CIB and push them to the cluster at once.
    _ensure_live_booth_env(booth_env)
    resources_section = get_resources(env.get_cib())
    id_provider = IdProvider(resources_section)
    instance_name = booth_env.instance_name

    # validate
    if resource.find_for_config(resources_section, booth_env.config_path):
        report_processor.report(
            booth_reports.booth_already_in_cib(instance_name)
        )
    # verify the config exists and is readable
    try:
        booth_env.config.raw_file.read()
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))
    if report_processor.has_errors:
        raise LibraryError()
    # validation done

    create_id = partial(
        resource.create_resource_id,
        resources_section,
        instance_name
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
        instance_attributes={"config": booth_env.config_path},
    ))

    env.push_cib()


def remove_from_cluster(
    env, resource_remove, instance_name=None, allow_remove_multiple=False
):
    """
    Remove group with ip resource and booth resource

    LibraryEnvironment env -- provides all for communication with externals
    function resource_remove -- provisional hack til resources are moved to lib
    string instance_name -- booth instance name
    bool allow_remove_multiple -- remove all resources if more than one found
    """
    # TODO resource_remove is provisional hack til resources are moved to lib
    report_processor = SimpleReportProcessor(env.report_processor)
    booth_env = env.get_booth_env(instance_name)
    # This command does not work with booth config files at all, let's reject
    # them then.
    _ensure_live_booth_env(booth_env)

    resource.get_remover(resource_remove)(
        _find_resource_elements_for_operation(
            report_processor,
            get_resources(env.get_cib()),
            booth_env,
            allow_remove_multiple,
        )
    )


def restart(env, resource_restart, instance_name=None, allow_multiple=False):
    """
    Restart group with ip resource and booth resource

    LibraryEnvironment env -- provides all for communication with externals
    function resource_restart -- provisional hack til resources are moved to lib
    string instance_name -- booth instance name
    bool allow_remove_multiple -- remove all resources if more than one found
    """
    # TODO resource_remove is provisional hack til resources are moved to lib
    report_processor = SimpleReportProcessor(env.report_processor)
    booth_env = env.get_booth_env(instance_name)
    _ensure_live_env(env, booth_env)

    for booth_element in _find_resource_elements_for_operation(
        report_processor,
        get_resources(env.get_cib()),
        booth_env,
        allow_multiple,
    ):
        resource_restart([booth_element.attrib["id"]])


def ticket_grant(env, ticket_name, site_ip=None, instance_name=None):
    """
    Grant a ticket to the site specified by site_ip

    LibraryEnvironment env
    string ticket_name -- the name of the ticket to be granted
    string site_ip -- IP of the site to grant the ticket to, None for local
    string instance_name -- booth instance name
    """
    return _ticket_operation(
        "grant",
        env,
        ticket_name,
        site_ip=site_ip,
        instance_name=instance_name,
    )


def ticket_revoke(env, ticket_name, site_ip=None, instance_name=None):
    """
    Revoke a ticket from the site specified by site_ip

    LibraryEnvironment env
    string ticket_name -- the name of the ticket to be revoked
    string site_ip -- IP of the site to revoke the ticket from, None for local
    string instance_name -- booth instance name
    """
    return _ticket_operation(
        "revoke",
        env,
        ticket_name,
        site_ip=site_ip,
        instance_name=instance_name,
    )


def _ticket_operation(operation, env, ticket_name, site_ip, instance_name):
    booth_env = env.get_booth_env(instance_name)
    _ensure_live_env(env, booth_env)

    if not site_ip:
        site_ip_list = resource.find_bound_ip(
            get_resources(env.get_cib()),
            booth_env.config_path
        )
        if len(site_ip_list) != 1:
            raise LibraryError(
                booth_reports.booth_cannot_determine_local_site_ip()
            )
        site_ip = site_ip_list[0]

    stdout, stderr, return_code = env.cmd_runner().run([
        settings.booth_binary, operation, "-s", site_ip, ticket_name
    ])

    if return_code != 0:
        raise LibraryError(
            booth_reports.booth_ticket_operation_failed(
                operation,
                join_multilines([stderr, stdout]),
                site_ip,
                ticket_name
            )
        )


def config_sync(env, instance_name=None, skip_offline_nodes=False):
    """
    Send specified local booth configuration to all nodes in the local cluster.

    LibraryEnvironment env
    string instance_name -- booth instance name
    skip_offline_nodes -- if True offline nodes will be skipped
    """
    report_processor = SimpleReportProcessor(env.report_processor)
    booth_env = env.get_booth_env(instance_name)
    if not env.is_cib_live:
        raise LibraryError(
            reports.live_environment_required(
                [file_type_codes.CIB],
            )
        )

    cluster_nodes_names, report_list = get_existing_nodes_names(
        env.get_corosync_conf()
    )
    if not cluster_nodes_names:
        report_list.append(reports.corosync_config_no_nodes_defined())
    report_processor.report_list(report_list)

    try:
        booth_conf_data = booth_env.config.read_raw()
        booth_conf = booth_env.config.raw_to_facade(booth_conf_data)
        if isinstance(booth_env.config.raw_file, GhostFile):
            authfile_data = booth_env.key.read_raw()
            authfile_path = booth_conf.get_authfile()
            authfile_name = (
                os.path.basename(authfile_path) if authfile_path else None
            )
        else:
            authfile_name, authfile_data, authfile_report_list = (
                config_files.get_authfile_name_and_data(booth_conf)
            )
            report_processor.report_list(authfile_report_list)
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))
    except ParserErrorException as e:
        report_processor.report_list(
            booth_env.config.parser_exception_to_report_list(e)
        )
    if report_processor.has_errors:
        raise LibraryError()

    com_cmd = BoothSendConfig(
        env.report_processor,
        booth_env.instance_name,
        booth_conf_data,
        authfile=authfile_name,
        authfile_data=authfile_data,
        skip_offline_targets=skip_offline_nodes
    )
    com_cmd.set_targets(
        env.get_node_target_factory().get_target_list(
            cluster_nodes_names,
            skip_non_existing=skip_offline_nodes,
        )
    )
    run_and_raise(env.get_node_communicator(), com_cmd)


def enable_booth(env, instance_name=None):
    """
    Enable specified instance of booth service, systemd systems supported only.

    LibraryEnvironment env
    string instance_name -- booth instance name
    """
    external.ensure_is_systemd()
    booth_env = env.get_booth_env(instance_name)
    _ensure_live_env(env, booth_env)
    instance_name = booth_env.instance_name

    try:
        external.enable_service(env.cmd_runner(), "booth", instance_name)
    except external.EnableServiceError as e:
        raise LibraryError(reports.service_enable_error(
            "booth", e.message, instance=instance_name
        ))
    env.report_processor.process(reports.service_enable_success(
        "booth", instance=instance_name
    ))


def disable_booth(env, instance_name=None):
    """
    Disable specified instance of booth service, systemd systems supported only.

    LibraryEnvironment env
    string instance_name -- booth instance name
    """
    external.ensure_is_systemd()
    booth_env = env.get_booth_env(instance_name)
    _ensure_live_env(env, booth_env)
    instance_name = booth_env.instance_name

    try:
        external.disable_service(env.cmd_runner(), "booth", instance_name)
    except external.DisableServiceError as e:
        raise LibraryError(reports.service_disable_error(
            "booth", e.message, instance=instance_name
        ))
    env.report_processor.process(reports.service_disable_success(
        "booth", instance=instance_name
    ))


def start_booth(env, instance_name=None):
    """
    Start specified instance of booth service, systemd systems supported only.
        On non-systemd systems it can be run like this:
        BOOTH_CONF_FILE=<booth-file-path> /etc/initd/booth-arbitrator

    LibraryEnvironment env
    string instance_name -- booth instance name
    """
    external.ensure_is_systemd()
    booth_env = env.get_booth_env(instance_name)
    _ensure_live_env(env, booth_env)
    instance_name = booth_env.instance_name

    try:
        external.start_service(env.cmd_runner(), "booth", instance_name)
    except external.StartServiceError as e:
        raise LibraryError(reports.service_start_error(
            "booth", e.message, instance=instance_name
        ))
    env.report_processor.process(reports.service_start_success(
        "booth", instance=instance_name
    ))


def stop_booth(env, instance_name=None):
    """
    Stop specified instance of booth service, systemd systems supported only.

    LibraryEnvironment env
    string instance_name -- booth instance name
    """
    external.ensure_is_systemd()
    booth_env = env.get_booth_env(instance_name)
    _ensure_live_env(env, booth_env)
    instance_name = booth_env.instance_name

    try:
        external.stop_service(env.cmd_runner(), "booth", instance_name)
    except external.StopServiceError as e:
        raise LibraryError(reports.service_stop_error(
            "booth", e.message, instance=instance_name
        ))
    env.report_processor.process(reports.service_stop_success(
        "booth", instance=instance_name
    ))


def pull_config(env, node_name, instance_name=None):
    """
    Get config from specified node and save it on local system. It will
    rewrite existing files.

    LibraryEnvironment env
    string node_name -- name of the node from which the config should be fetched
    string instance_name -- booth instance name
    """
    report_processor = SimpleReportProcessor(env.report_processor)
    booth_env = env.get_booth_env(instance_name)
    instance_name = booth_env.instance_name
    _ensure_live_env(env, booth_env)

    env.report_processor.process(
        booth_reports.booth_fetching_config_from_node_started(
            node_name, instance_name
        )
    )
    com_cmd = BoothGetConfig(env.report_processor, instance_name)
    com_cmd.set_targets([
        env.get_node_target_factory().get_target_from_hostname(node_name)
    ])
    # pylint: disable=unsubscriptable-object
    # In general, pylint is right. And it cannot know in this case code is OK.
    # It is covered by tests.
    output = run_and_raise(env.get_node_communicator(), com_cmd)[0][1]
    try:
        # TODO adapt to new file transfer framework once it is written
        if (
            output["authfile"]["name"] is not None
            and
            output["authfile"]["data"]
        ):
            authfile_name = output["authfile"]["name"]
            report_list = config_validators.check_instance_name(authfile_name)
            if report_list:
                raise LibraryError(*report_list)
            booth_key = FileInstance.for_booth_key(authfile_name)
            booth_key.write_raw(
                base64.b64decode(
                    output["authfile"]["data"].encode("utf-8")
                ),
                can_overwrite=True
            )
        booth_env.config.write_raw(
            output["config"]["data"].encode("utf-8"),
            can_overwrite=True
        )
        env.report_processor.process(
            booth_reports.booth_config_accepted_by_node(
                name_list=[instance_name]
            )
        )
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))
    except KeyError:
        raise LibraryError(reports.invalid_response_format(node_name))
    if report_processor.has_errors:
        raise LibraryError()


def get_status(env, instance_name=None):
    """
    get booth status info

    LibraryEnvironment env
    string instance_name -- booth instance name
    """
    booth_env = env.get_booth_env(instance_name)
    _ensure_live_env(env, booth_env)
    instance_name = booth_env.instance_name
    return {
        "status": status.get_daemon_status(env.cmd_runner(), instance_name),
        "ticket": status.get_tickets_status(env.cmd_runner(), instance_name),
        "peers": status.get_peers_status(env.cmd_runner(), instance_name),
    }


def _find_resource_elements_for_operation(
    report_processor, resources_section, booth_env, allow_multiple
):
    booth_element_list = resource.find_for_config(
        resources_section,
        booth_env.config_path,
    )

    if not booth_element_list:
        report_processor.report(
            booth_reports.booth_not_exists_in_cib(booth_env.instance_name)
        )
    elif len(booth_element_list) > 1:
        report_processor.report(
            booth_reports.booth_multiple_times_in_cib(
                booth_env.instance_name,
                severity=(
                    ReportItemSeverity.WARNING if allow_multiple
                    else ReportItemSeverity.ERROR
                )
            )
        )
    if report_processor.has_errors:
        raise LibraryError()

    return booth_element_list

def _ensure_live_booth_env(booth_env):
    if booth_env.ghost_file_codes:
        raise LibraryError(
            reports.live_environment_required(booth_env.ghost_file_codes)
        )

def _ensure_live_env(env, booth_env):
    not_live = (
        booth_env.ghost_file_codes
        +
        # parenthesis are cruciual, otherwise the if..else influences
        # booth_env.ghost_file_codes as well
        ([file_type_codes.CIB] if not env.is_cib_live else [])
    )
    if not_live:
        raise LibraryError(reports.live_environment_required(not_live))
