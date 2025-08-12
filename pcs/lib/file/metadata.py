import os.path
from typing import Optional

from pcs import settings
from pcs.common import file_type_codes as code
from pcs.common.file import FileMetadata


def _for_booth_config(filename: str) -> FileMetadata:
    return FileMetadata(
        # The filename is expected to be complete (i.e. booth.conf) and verified
        # (i.e. no slashes in it). The caller is responsible for doing both.
        file_type_code=code.BOOTH_CONFIG,
        path=os.path.join(settings.booth_config_dir, filename),
        owner_user_name="root",
        owner_group_name="root",
        permissions=0o644,
        is_binary=False,
    )


def _for_booth_key(filename: str) -> FileMetadata:
    return FileMetadata(
        # The filename is expected to be complete (i.e. booth.key) and verified
        # (i.e. no slashes in it). The caller is responsible for doing both.
        file_type_code=code.BOOTH_KEY,
        path=os.path.join(settings.booth_config_dir, filename),
        owner_user_name=settings.pacemaker_uname,
        owner_group_name=settings.pacemaker_gname,
        permissions=settings.booth_authkey_file_mode,
        is_binary=True,
    )


def _for_cfgsync_ctl() -> FileMetadata:
    return FileMetadata(
        file_type_code=code.PCS_CFGSYNC_CTL,
        path=settings.pcs_cfgsync_ctl_location,
        owner_user_name="root",
        owner_group_name="root",
        permissions=0o600,
        is_binary=False,
    )


def _for_corosync_conf() -> FileMetadata:
    return FileMetadata(
        file_type_code=code.COROSYNC_CONF,
        path=settings.corosync_conf_file,
        owner_user_name="root",
        owner_group_name="root",
        permissions=0o644,
        is_binary=False,
    )


def _for_corosync_qnetd_ca_cert() -> FileMetadata:
    return FileMetadata(
        file_type_code=code.COROSYNC_QNETD_CA_CERT,
        path=os.path.join(
            settings.corosync_qdevice_net_server_certs_dir,
            settings.corosync_qdevice_net_server_ca_file_name,
        ),
        owner_user_name="coroqnetd",
        owner_group_name="coroqnetd",
        permissions=0o600,
        is_binary=True,
    )


def _for_pacemaker_authkey() -> FileMetadata:
    return FileMetadata(
        file_type_code=code.PACEMAKER_AUTHKEY,
        path=settings.pacemaker_authkey_file,
        owner_user_name=settings.pacemaker_uname,
        owner_group_name=settings.pacemaker_gname,
        permissions=0o400,
        is_binary=True,
    )


def _for_pcs_dr_config() -> FileMetadata:
    return FileMetadata(
        file_type_code=code.PCS_DR_CONFIG,
        path=settings.pcsd_dr_config_location,
        owner_user_name="root",
        owner_group_name="root",
        permissions=0o600,
        is_binary=False,
    )


def _for_pcs_known_hosts() -> FileMetadata:
    return FileMetadata(
        file_type_code=code.PCS_KNOWN_HOSTS,
        path=settings.pcsd_known_hosts_location,
        owner_user_name="root",
        owner_group_name="root",
        permissions=0o600,
        is_binary=False,
    )


def _for_pcs_users_conf() -> FileMetadata:
    return FileMetadata(
        file_type_code=code.PCS_USERS_CONF,
        path=settings.pcsd_users_conf_location,
        owner_user_name="root",
        owner_group_name="root",
        permissions=0o600,
        is_binary=False,
    )


def _for_pcs_settings_conf() -> FileMetadata:
    return FileMetadata(
        file_type_code=code.PCS_SETTINGS_CONF,
        path=settings.pcsd_settings_conf_location,
        owner_user_name="root",
        owner_group_name="root",
        permissions=0o600,
        is_binary=False,
    )


def for_file_type(  # noqa: PLR0911
    file_type_code: code.FileTypeCode, filename: Optional[str] = None
) -> FileMetadata:
    # pylint: disable=too-many-return-statements
    if file_type_code == code.BOOTH_CONFIG:
        if not filename:
            raise AssertionError("filename must be set")
        return _for_booth_config(filename)
    if file_type_code == code.BOOTH_KEY:
        if not filename:
            raise AssertionError("filename must be set")
        return _for_booth_key(filename)
    if file_type_code == code.PCS_CFGSYNC_CTL:
        return _for_cfgsync_ctl()
    if file_type_code == code.COROSYNC_CONF:
        return _for_corosync_conf()
    if file_type_code == code.COROSYNC_QNETD_CA_CERT:
        return _for_corosync_qnetd_ca_cert()
    if file_type_code == code.PACEMAKER_AUTHKEY:
        return _for_pacemaker_authkey()
    if file_type_code == code.PCS_DR_CONFIG:
        return _for_pcs_dr_config()
    if file_type_code == code.PCS_KNOWN_HOSTS:
        return _for_pcs_known_hosts()
    if file_type_code == code.PCS_USERS_CONF:
        return _for_pcs_users_conf()
    if file_type_code == code.PCS_SETTINGS_CONF:
        return _for_pcs_settings_conf()

    raise AssertionError("Unknown file_type_code")
