import os.path
from functools import lru_cache

SYSTEMD_PATHS = [
  '/run/systemd/system',
  '/var/run/systemd/system',
]

@lru_cache()
def is_systemd():
    return any([os.path.isdir(path) for path in SYSTEMD_PATHS])
