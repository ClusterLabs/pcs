import math
import os.path
import time

from pcs import settings
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.file import RawFileError
from pcs.common.reports import ReportProcessor
from pcs.common.reports.item import (
    ReportItem,
)
from pcs.common.tools import format_os_error
from pcs.lib.communication.nodes import (
    CheckPacemakerStarted,
    StartCluster,
)
from pcs.lib.communication.tools import (
    run as run_com,
)
from pcs.lib.communication.tools import (
    run_and_raise,
)
from pcs.lib.corosync import config_parser
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import get_valid_timeout_seconds
from pcs.lib.tools import environment_file_to_dict


def ensure_live_env(env: LibraryEnvironment):
    not_live = []
    if not env.is_cib_live:
        not_live.append(file_type_codes.CIB)
    if not env.is_corosync_conf_live:
        not_live.append(file_type_codes.COROSYNC_CONF)
    if not_live:
        raise LibraryError(
            ReportItem.error(reports.messages.LiveEnvironmentRequired(not_live))
        )


def start_cluster(
    communicator_factory,
    report_processor: ReportProcessor,
    target_list,
    wait_timeout=False,
):
    # Large clusters take longer time to start up. So we make the timeout
    # longer for each 8 nodes:
    #  1 -  8 nodes: 1 * timeout
    #  9 - 16 nodes: 2 * timeout
    # 17 - 24 nodes: 3 * timeout
    # and so on ...
    # Users can override this and set their own timeout by specifying
    # the --request-timeout option.
    timeout = int(
        settings.default_request_timeout * math.ceil(len(target_list) / 8.0)
    )
    com_cmd = StartCluster(report_processor)
    com_cmd.set_targets(target_list)
    run_and_raise(
        communicator_factory.get_communicator(request_timeout=timeout), com_cmd
    )
    if wait_timeout is not False:
        report_processor.report_list(
            wait_for_pacemaker_to_start(
                communicator_factory.get_communicator(),
                report_processor,
                target_list,
                # wait_timeout is either None or a timeout
                timeout=wait_timeout,
            )
        )
        if report_processor.has_errors:
            raise LibraryError()


def wait_for_pacemaker_to_start(
    node_communicator,
    report_processor: ReportProcessor,
    target_list,
    timeout=None,
):
    timeout = 60 * 15 if timeout is None else timeout
    interval = 2
    stop_at = time.time() + timeout
    report_processor.report(
        ReportItem.info(
            reports.messages.WaitForNodeStartupStarted(
                sorted([target.label for target in target_list])
            )
        )
    )
    error_report_list = []
    has_errors = False
    while target_list:
        if time.time() > stop_at:
            error_report_list.append(
                ReportItem.error(reports.messages.WaitForNodeStartupTimedOut())
            )
            break
        time.sleep(interval)
        com_cmd = CheckPacemakerStarted(report_processor)
        com_cmd.set_targets(target_list)
        target_list = run_com(node_communicator, com_cmd)
        has_errors = has_errors or com_cmd.has_errors

    if error_report_list or has_errors:
        error_report_list.append(
            ReportItem.error(reports.messages.WaitForNodeStartupError())
        )
    return error_report_list


def get_validated_wait_timeout(report_processor, wait, start):
    try:
        if wait is False:
            return False
        if not start:
            report_processor.report(
                ReportItem.error(
                    reports.messages.WaitForNodeStartupWithoutStart()
                )
            )
        return get_valid_timeout_seconds(wait)
    except LibraryError as e:
        report_processor.report_list(e.args)
    return None


def is_ssl_cert_sync_enabled(report_processor: ReportProcessor):
    try:
        if os.path.isfile(settings.pcsd_config):
            with open(settings.pcsd_config, "r") as cfg_file:
                cfg = environment_file_to_dict(cfg_file.read())
                return (
                    cfg.get("PCSD_SSL_CERT_SYNC_ENABLED", "false").lower()
                    == "true"
                )
    except OSError as e:
        report_processor.report(
            ReportItem.error(
                reports.messages.FileIoError(
                    file_type_codes.PCSD_ENVIRONMENT_CONFIG,
                    RawFileError.ACTION_READ,
                    format_os_error(e),
                    file_path=settings.pcsd_config,
                )
            )
        )
    return False


def verify_corosync_conf(corosync_conf_facade):
    # This is done in pcs.lib.env.LibraryEnvironment.push_corosync_conf
    # usually. But there are special cases here which use custom corosync.conf
    # pushing so the check must be done individually.
    (
        bad_sections,
        bad_attr_names,
        bad_attr_values,
    ) = config_parser.verify_section(corosync_conf_facade.config)
    if bad_sections or bad_attr_names or bad_attr_values:
        raise LibraryError(
            ReportItem.error(
                reports.messages.CorosyncConfigCannotSaveInvalidNamesValues(
                    bad_sections,
                    bad_attr_names,
                    bad_attr_values,
                )
            )
        )
