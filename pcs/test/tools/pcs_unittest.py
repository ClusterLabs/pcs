import sys
major, minor = sys.version_info[:2]
if major == 2 and minor == 6:
    from unittest2 import *
else:
    from unittest import *
del major, minor, sys
