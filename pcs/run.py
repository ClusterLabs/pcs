import sys

from pcs import settings

if settings.pcs_bundled_pacakges_dir not in sys.path:
    sys.path.insert(0, settings.pcs_bundled_pacakges_dir)

# pylint: disable=unused-import
from pcs.daemon.run import main as daemon
from pcs.snmp.pcs_snmp_agent import main as pcs_snmp_agent
