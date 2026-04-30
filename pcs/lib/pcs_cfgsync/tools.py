from hashlib import sha1

from pcs.lib.file.instance import FileInstance
from pcs.lib.interface.config import FacadeInterface


def get_file_hash(file_instance: FileInstance, facade: FacadeInterface) -> str:
    # sha1 is used to be compatible with the old ruby implementation.
    # The hash is only used to compare and sort the files, not for security
    # reasons
    return sha1(
        file_instance.facade_to_raw(facade), usedforsecurity=False
    ).hexdigest()
