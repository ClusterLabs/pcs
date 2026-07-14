from .common import add_bundled_packages_to_path

add_bundled_packages_to_path()

from pcs.daemon.run import main  # noqa: E402
