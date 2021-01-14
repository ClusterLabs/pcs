import sys

from pcs import settings


def add_bundled_packages_to_path() -> None:
    """
    This function deals with some bundled python dependencies that are
    installed in a pcs-specific location rather than in a standard system
    location for the python packages.
    """
    if settings.pcs_bundled_pacakges_dir not in sys.path:
        sys.path.insert(0, settings.pcs_bundled_pacakges_dir)
