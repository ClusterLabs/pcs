#!/usr/bin/python

import sys
import os
sys.path.append("pcs")
import settings

pcs_version = settings.pcs_version

print os.system("cp dist/pcs-"+pcs_version+".tar dist/pcs-withgems-"+pcs_version+".tar")
print os.system("tar --delete -f dist/pcs-"+pcs_version+".tar '*/pcsd/vendor'")
print os.system("gzip dist/pcs-"+pcs_version+".tar")
print os.system("gzip dist/pcs-withgems-"+pcs_version+".tar")
