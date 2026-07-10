from collections.abc import Mapping
from typing import cast

from pcs.common import file_type_codes, reports
from pcs.common.corosync_conf import (
    CorosyncConfDto,
    CorosyncQuorumDeviceSettingsDto,
)
from pcs.common.file import RawFileError
from pcs.common.types import (
    CorosyncTransportType,
    UnknownCorosyncTransportTypeException,
)
from pcs.lib.commands.cluster.utils import ensure_live_env, verify_corosync_conf
from pcs.lib.communication.corosync import GetCorosyncConf
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.corosync import config_facade, config_validators
from pcs.lib.corosync import constants as corosync_constants
from pcs.lib.corosync import live as corosync_live
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import raw_file_error_report
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.pcs_cfgsync.config.facade import Facade as CfgsyncCtlFacade
from pcs.lib.tools import generate_uuid


def _config_update(
    report_processor: reports.ReportProcessor,
    corosync_conf: config_facade.ConfigFacade,
    transport_options: Mapping[str, str],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
    totem_options: Mapping[str, str],
) -> None:
    transport_type = corosync_conf.get_transport()
    report_list = config_validators.update_totem(totem_options)
    if transport_type in corosync_constants.TRANSPORTS_KNET:
        report_list += config_validators.update_transport_knet(
            transport_options,
            compression_options,
            crypto_options,
            corosync_conf.get_crypto_options(),
        )
    elif transport_type in corosync_constants.TRANSPORTS_UDP:
        report_list += config_validators.update_transport_udp(
            transport_options,
            compression_options,
            crypto_options,
        )
    else:
        report_processor.report(
            reports.ReportItem.error(
                reports.messages.CorosyncConfigUnsupportedTransport(
                    transport_type, sorted(corosync_constants.TRANSPORTS_ALL)
                )
            )
        )
    if report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    corosync_conf.set_totem_options(totem_options)
    corosync_conf.set_transport_options(
        transport_options,
        compression_options,
        crypto_options,
    )
    verify_corosync_conf(corosync_conf)  # raises if corosync not valid


def _ensure_live_corosync(env: LibraryEnvironment) -> None:
    if not env.is_corosync_conf_live:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.LiveEnvironmentRequired(
                    [file_type_codes.COROSYNC_CONF]
                )
            )
        )
        raise LibraryError()


def config_update(
    env: LibraryEnvironment,
    transport_options: Mapping[str, str],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
    totem_options: Mapping[str, str],
) -> None:
    """
    Update corosync.conf in the local cluster

    env
    transport_options -- transport specific options
    compression_options -- only available for knet transport. In
        corosync.conf they are prefixed 'knet_compression_'
    crypto_options -- only available for knet transport. In corosync.conf
        they are prefixed 'crypto_'
    totem_options -- options of section 'totem' in corosync.conf
    """
    ensure_live_env(env)
    corosync_conf = env.get_corosync_conf()
    _config_update(
        env.report_processor,
        corosync_conf,
        transport_options,
        compression_options,
        crypto_options,
        totem_options,
    )
    env.push_corosync_conf(corosync_conf)


# TODO: this command will not work through API, `bytes` not json serializable
def config_update_local(
    env: LibraryEnvironment,
    corosync_conf_content: bytes,
    transport_options: Mapping[str, str],
    compression_options: Mapping[str, str],
    crypto_options: Mapping[str, str],
    totem_options: Mapping[str, str],
) -> bytes:
    """
    Update corosync.conf passed as an argument and return the updated conf

    env
    corosync_conf_content -- corosync.conf to be updated
    transport_options -- transport specific options
    compression_options -- only available for knet transport. In
        corosync.conf they are prefixed 'knet_compression_'
    crypto_options -- only available for knet transport. In corosync.conf
        they are prefixed 'crypto_'
    totem_options -- options of section 'totem' in corosync.conf
    """
    # As we are getting a corosync.conf content as an argument, we want to make
    # sure it was not given to LibraryEnvironment as well. Also we don't
    # allow/need CIB to be handled by LibraryEnvironment.
    ensure_live_env(env)
    corosync_conf_instance = FileInstance.for_corosync_conf()
    try:
        corosync_conf: config_facade.ConfigFacade = cast(
            config_facade.ConfigFacade,
            corosync_conf_instance.raw_to_facade(corosync_conf_content),
        )
    except ParserErrorException as e:
        if env.report_processor.report_list(
            corosync_conf_instance.toolbox.parser.exception_to_report_list(
                e,
                corosync_conf_instance.toolbox.file_type_code,
                None,
                force_code=None,
                is_forced_or_warning=False,
            )
        ).has_errors:
            raise LibraryError() from e
    _config_update(
        env.report_processor,
        corosync_conf,
        transport_options,
        compression_options,
        crypto_options,
        totem_options,
    )
    return corosync_conf_instance.facade_to_raw(corosync_conf)


def get_corosync_conf_struct(env: LibraryEnvironment) -> CorosyncConfDto:
    """
    Read corosync.conf from the local node and return it in a structured form
    """
    corosync_conf = env.get_corosync_conf()
    quorum_device_dto: CorosyncQuorumDeviceSettingsDto | None = None
    qd_model = corosync_conf.get_quorum_device_model()
    if qd_model is not None:
        (
            qd_model_options,
            qd_generic_options,
            qd_heuristics_options,
        ) = corosync_conf.get_quorum_device_settings()
        quorum_device_dto = CorosyncQuorumDeviceSettingsDto(
            model=qd_model,
            model_options=qd_model_options,
            generic_options=qd_generic_options,
            heuristics_options=qd_heuristics_options,
        )
    try:
        return CorosyncConfDto(
            cluster_name=corosync_conf.get_cluster_name(),
            cluster_uuid=corosync_conf.get_cluster_uuid(),
            transport=CorosyncTransportType.from_str(
                corosync_conf.get_transport()
            ),
            totem_options=corosync_conf.get_totem_options(),
            transport_options=corosync_conf.get_transport_options(),
            compression_options=corosync_conf.get_compression_options(),
            crypto_options=corosync_conf.get_crypto_options(),
            nodes=[node.to_dto() for node in corosync_conf.get_nodes()],
            links_options=corosync_conf.get_links_options(),
            quorum_options=corosync_conf.get_quorum_options(),
            quorum_device=quorum_device_dto,
        )
    except UnknownCorosyncTransportTypeException as e:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.CorosyncConfigUnsupportedTransport(
                    e.transport, sorted(corosync_constants.TRANSPORTS_ALL)
                )
            )
        ) from e


def get_corosync_conf(env: LibraryEnvironment) -> str:
    """
    Read corosync.conf from the local node and return its plain-text content
    """
    _ensure_live_corosync(env)
    return env.get_corosync_conf_data()


def get_corosync_conf_remote(env: LibraryEnvironment, node_name: str) -> str:
    """
    Read corosync.conf from a remote node and return its plain-text content

    node_name -- name of the node to fetch corosync.conf from
    """
    report_processor = env.report_processor
    target_factory = env.get_node_target_factory()
    report_list, target_list = target_factory.get_target_list_with_reports(
        [node_name], allow_skip=False, report_none_host_found=False
    )
    if report_processor.report_list(report_list).has_errors:
        raise LibraryError()
    com_cmd = GetCorosyncConf(report_processor)
    com_cmd.set_targets(target_list)
    return run_and_raise(env.get_node_communicator(), com_cmd)  # type: ignore[no-untyped-call]


def reload_corosync_conf(env: LibraryEnvironment) -> None:
    """
    Reload corosync configuration on the local node
    """
    _ensure_live_corosync(env)
    if not env.service_manager.is_running("corosync"):
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.CorosyncConfigReloadNotPossible()
            )
        )
        raise LibraryError()
    report_list = corosync_live.reload_corosync_conf(env.cmd_runner())

    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()


def _generate_cluster_uuid(
    corosync_conf: config_facade.ConfigFacade, is_forced: bool
) -> tuple[reports.ReportItemList, config_facade.ConfigFacade]:
    report_list = []
    if corosync_conf.get_cluster_uuid():
        report_list.append(
            reports.ReportItem(
                severity=reports.item.get_severity(
                    reports.codes.FORCE, is_forced
                ),
                message=reports.messages.ClusterUuidAlreadySet(),
            )
        )
        if not is_forced:
            return report_list, corosync_conf

    corosync_conf.set_cluster_uuid(generate_uuid())
    return report_list, corosync_conf


def generate_cluster_uuid(
    env: LibraryEnvironment,
    force_flags: reports.types.ForceFlags = (),
) -> None:
    """
    Add or update cluster UUID in live cluster

    env
    """
    ensure_live_env(env)
    corosync_conf = env.get_corosync_conf()
    report_list, corosync_conf = _generate_cluster_uuid(
        corosync_conf, reports.codes.FORCE in force_flags
    )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()
    env.push_corosync_conf(corosync_conf)


# TODO: this command will not work through API, `bytes` not json serializable
def generate_cluster_uuid_local(
    env: LibraryEnvironment,
    corosync_conf_content: bytes,
    force_flags: reports.types.ForceFlags = (),
) -> bytes:
    """
    Add or update cluster UUID in corosync.conf passed as an argument and return
    the updated config

    env
    corosync_conf_content -- corosync.conf to be updated
    """
    ensure_live_env(env)
    corosync_conf_instance = FileInstance.for_corosync_conf()
    try:
        corosync_conf: config_facade.ConfigFacade = cast(
            config_facade.ConfigFacade,
            corosync_conf_instance.raw_to_facade(corosync_conf_content),
        )
    except ParserErrorException as e:
        if env.report_processor.report_list(
            corosync_conf_instance.toolbox.parser.exception_to_report_list(
                e,
                corosync_conf_instance.toolbox.file_type_code,
                None,
                force_code=None,
                is_forced_or_warning=False,
            )
        ).has_errors:
            raise LibraryError() from e

    report_list, corosync_conf = _generate_cluster_uuid(
        corosync_conf, reports.codes.FORCE in force_flags
    )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    return corosync_conf_instance.facade_to_raw(corosync_conf)


def set_corosync_conf(env: LibraryEnvironment, file_content: str) -> None:
    """
    Replace corosync.conf on this node with provided file_content. Low level
    command used for distributing the file to cluster nodes.

    file_content -- new contents of corosync.conf
    """

    ensure_live_env(env)

    corosync_conf_instance = FileInstance.for_corosync_conf()
    try:
        new_corosync_conf = cast(
            config_facade.ConfigFacade,
            corosync_conf_instance.raw_to_facade(file_content.encode("utf-8")),
        )
    except ParserErrorException as e:
        env.report_processor.report_list(
            corosync_conf_instance.toolbox.parser.exception_to_report_list(
                e,
                corosync_conf_instance.toolbox.file_type_code,
                None,
                force_code=None,
                is_forced_or_warning=False,
            )
        )
        raise LibraryError() from e

    verify_corosync_conf(new_corosync_conf)  # raise if corosync is not valid

    try:
        if corosync_conf_instance.raw_file.exists():
            cfgsyncctl, report_list = __read_cfgsync_ctl()
            env.report_processor.report_list(report_list)

            corosync_conf_instance.raw_file.backup()
            # Remove old backups, but do not treat the errors as fatal so that
            # the file is actually written if we were at least able to create
            # the backup
            try:
                corosync_conf_instance.raw_file.remove_old_backups(
                    cfgsyncctl.file_backup_count
                )
            except RawFileError as e:
                env.report_processor.report(
                    raw_file_error_report(e, is_forced_or_warning=True)
                )

        corosync_conf_instance.write_facade(
            new_corosync_conf, can_overwrite=True
        )
    except RawFileError as e:
        env.report_processor.report(raw_file_error_report(e))
        raise LibraryError() from e


def __read_cfgsync_ctl() -> tuple[CfgsyncCtlFacade, reports.ReportItemList]:
    report_list: reports.ReportItemList = []
    cfgsyncctl_instance = FileInstance.for_pcs_cfgsync_ctl()
    if not cfgsyncctl_instance.raw_file.exists():
        return CfgsyncCtlFacade.create(), report_list
    try:
        return cast(
            CfgsyncCtlFacade, cfgsyncctl_instance.read_to_facade()
        ), report_list
    except RawFileError as e:
        report_list.append(raw_file_error_report(e, is_forced_or_warning=True))
    except ParserErrorException as e:
        report_list.extend(
            cfgsyncctl_instance.parser_exception_to_report_list(
                e, is_forced_or_warning=True
            )
        )
    return CfgsyncCtlFacade.create(), report_list
