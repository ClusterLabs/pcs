# pylint: disable=unused-import
# pylint: disable=wrong-import-position

from .common import add_bundled_packages_to_path

add_bundled_packages_to_path()

from pcs.pcs_internal import main  # noqa: E402
