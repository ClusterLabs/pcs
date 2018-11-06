"""
Intention of this module is to provide functions called from entry points
created by setuptools (see setup.py).

This module deals with some bundled python dependencies that are installed in
a pcs-specific location rather than in a standard system location for the python
packages.
"""
import sys

from pcs import settings

if settings.pcs_bundled_pacakges_dir not in sys.path:
    sys.path.insert(0, settings.pcs_bundled_pacakges_dir)

# pylint: disable=unused-import, wrong-import-position
from pcs.daemon.run import main as daemon
try:
    # It is possible the package `pcs.snmp` is not installed. `pcsd` does not
    # require on pcs.snmp. `pcs.snmp` should be installed when `pcs_snmp_agent`
    # is called.
    from pcs.snmp.pcs_snmp_agent import main as pcs_snmp_agent
except ImportError:
    pass
