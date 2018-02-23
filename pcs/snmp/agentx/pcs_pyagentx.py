import sys

from pcs import settings

# add bundled lib path to python path
if settings.pcs_bundled_pacakges_dir not in sys.path:
    sys.path.insert(0, settings.pcs_bundled_pacakges_dir)

from pyagentx import *
