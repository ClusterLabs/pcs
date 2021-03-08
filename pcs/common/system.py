import os.path
from functools import lru_cache

from pcs import settings


@lru_cache()
def is_systemd():
    return any([os.path.isdir(path) for path in settings.systemd_unit_path])
