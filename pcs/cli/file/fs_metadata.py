import os.path

from pcs.cli.file import file_type_codes as code
from pcs.common.file import FileMetadata


_default_metadata = dict(
    owner_user_name=None,
    owner_group_name=None,
    permissions=None,
)

_metadata = {
    code.PCS_KNOWN_HOSTS: dict(
        file_type_code=code.PCS_KNOWN_HOSTS,
        path=os.path.join(os.path.expanduser("~/.pcs"), "known-hosts"),
        permissions=0o600,
        is_binary=False,
    )
}

def for_file_type(file_type_code):
    file_metadata = _default_metadata.copy()
    file_metadata.update(_metadata[file_type_code])
    return FileMetadata(**file_metadata)
