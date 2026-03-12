from typing import Mapping, Optional, cast

from pcs.common import reports
from pcs.common.corosync_conf import (
    CorosyncConfDto,
    CorosyncQuorumDeviceSettingsDto,
)
from pcs.common.types import (
    CorosyncTransportType,
    UnknownCorosyncTransportTypeException,
)
from pcs.lib.commands.cluster.common import (
    ensure_live_env,
    verify_corosync_conf,
)
from pcs.lib.corosync import config_facade, config_validators
from pcs.lib.corosync import constants as corosync_constants
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.file.instance import FileInstance
from pcs.lib.interface.config import ParserErrorException


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
    quorum_device_dto: Optional[CorosyncQuorumDeviceSettingsDto] = None
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
