import os.path

from pcs import settings
from pcs.common import file_type_codes as code
from pcs.common.file import FileMetadata


_metadata = {
    code.BOOTH_CONFIG: lambda filename: FileMetadata(
        # The filename is expected to be complete (i.e. booth.conf) and verified
        # (i.e. no slashes in it). The caller is responsible for doing both.
        file_type_code=code.BOOTH_CONFIG,
        path=os.path.join(settings.booth_config_dir, filename),
        owner_user_name="root",
        owner_group_name="root",
        permissions=0o644,
        is_binary=False,
    ),
    code.BOOTH_KEY: lambda filename: FileMetadata(
        # The filename is expected to be complete (i.e. booth.key) and verified
        # (i.e. no slashes in it). The caller is responsible for doing both.
        file_type_code=code.BOOTH_KEY,
        path=os.path.join(settings.booth_config_dir, filename),
        owner_user_name=settings.pacemaker_uname,
        owner_group_name=settings.pacemaker_gname,
        permissions=settings.booth_authkey_file_mode,
        is_binary=True,
    ),
    code.COROSYNC_CONF: lambda: FileMetadata(
        file_type_code=code.COROSYNC_CONF,
        path=settings.corosync_conf_file,
        owner_user_name="root",
        owner_group_name="root",
        permissions=0o644,
        is_binary=False,
    ),
    code.PACEMAKER_AUTHKEY: lambda: FileMetadata(
        file_type_code=code.PACEMAKER_AUTHKEY,
        path=settings.pacemaker_authkey_file,
        owner_user_name="hacluster",
        owner_group_name="haclient",
        permissions=0o400,
        is_binary=True,
    ),
    code.PCS_KNOWN_HOSTS: lambda: FileMetadata(
        file_type_code=code.PCS_KNOWN_HOSTS,
        path=settings.pcsd_known_hosts_location,
        owner_user_name="root",
        owner_group_name="root",
        permissions=0o600,
        is_binary=False,
    ),
}

def for_file_type(file_type_code, *args, **kwargs):
    return _metadata[file_type_code](*args, **kwargs)
