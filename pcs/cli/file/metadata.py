import os.path

from pcs.common import file_type_codes as code
from pcs.common.file import FileMetadata

_metadata = {
    code.BOOTH_CONFIG: lambda path: FileMetadata(
        file_type_code=code.BOOTH_CONFIG,
        path=path,
        owner_user_name=None,
        owner_group_name=None,
        permissions=None,
        is_binary=False,
    ),
    code.BOOTH_KEY: lambda path: FileMetadata(
        file_type_code=code.BOOTH_KEY,
        path=path,
        owner_user_name=None,
        owner_group_name=None,
        permissions=0o600,
        is_binary=True,
    ),
    code.COROSYNC_CONF: lambda path: FileMetadata(
        file_type_code=code.COROSYNC_CONF,
        path=path,
        owner_user_name=None,
        owner_group_name=None,
        permissions=0o644,
        is_binary=False,
    ),
    code.PCS_KNOWN_HOSTS: lambda: FileMetadata(
        file_type_code=code.PCS_KNOWN_HOSTS,
        path=os.path.join(os.path.expanduser("~/.pcs"), "known-hosts"),
        owner_user_name=None,
        owner_group_name=None,
        permissions=0o600,
        is_binary=False,
    ),
}


def for_file_type(file_type_code, *args, **kwargs):
    return _metadata[file_type_code](*args, **kwargs)
