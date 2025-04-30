from typing import Optional

from pcs.common import file_type_codes
from pcs.common.reports.dto import ReportItemContextDto

_file_role_translation = {
    file_type_codes.BOOTH_CONFIG: "Booth configuration",
    file_type_codes.BOOTH_KEY: "Booth key",
    file_type_codes.CFGSYNC_CTL: "Config synchronization configuration",
    file_type_codes.COROSYNC_AUTHKEY: "Corosync authkey",
    file_type_codes.COROSYNC_CONF: "Corosync configuration",
    file_type_codes.COROSYNC_QDEVICE_NSSDB: "QDevice certificate database",
    file_type_codes.COROSYNC_QNETD_CA_CERT: "QNetd CA certificate",
    file_type_codes.COROSYNC_QNETD_NSSDB: "QNetd certificate database",
    file_type_codes.PCS_DR_CONFIG: "disaster-recovery configuration",
    file_type_codes.PACEMAKER_AUTHKEY: "Pacemaker authkey",
    file_type_codes.PCSD_ENVIRONMENT_CONFIG: "pcsd configuration",
    file_type_codes.PCSD_SSL_CERT: "pcsd SSL certificate",
    file_type_codes.PCSD_SSL_KEY: "pcsd SSL key",
    file_type_codes.PCS_KNOWN_HOSTS: "known-hosts",
    file_type_codes.PCS_SETTINGS_CONF: "pcs configuration",
}


def add_context_to_message(
    msg: str, context: Optional[ReportItemContextDto]
) -> str:
    if context:
        msg = f"{context.node}: {msg}"
    return msg


def format_file_role(role: file_type_codes.FileTypeCode) -> str:
    return _file_role_translation.get(role, role)
