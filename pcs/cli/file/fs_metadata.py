import os.path

from pcs.common import file_type_codes as code
from pcs.common.file import FileMetadata


_default_metadata = dict(
    owner_user_name=None,
    owner_group_name=None,
    permissions=None,
)

_metadata = {
    code.BOOTH_CONFIG: lambda path: dict(
        file_type_code=code.BOOTH_CONFIG,
        path=path,
        is_binary=False,
    ),
    code.BOOTH_KEY: lambda path: dict(
        file_type_code=code.BOOTH_KEY,
        path=path,
        permissions=0o600,
        is_binary=True,
    ),
    code.PCS_KNOWN_HOSTS: lambda: dict(
        file_type_code=code.PCS_KNOWN_HOSTS,
        path=os.path.join(os.path.expanduser("~/.pcs"), "known-hosts"),
        permissions=0o600,
        is_binary=False,
    )
}

def for_file_type(file_type_code, *args, **kwargs):
    file_metadata = _default_metadata.copy()
    file_metadata.update(_metadata[file_type_code](*args, **kwargs))
    return FileMetadata(**file_metadata)
