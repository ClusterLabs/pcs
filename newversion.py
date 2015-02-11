#!/usr/bin/python

import sys
import os
sys.path.append("pcs")
import settings

# Get the current version, increment by 1, verify changes, git commit & tag
pcs_version_split = settings.pcs_version.split('.')
pcs_version_split[2] = str(int(pcs_version_split[2]) + 1)
new_version = ".".join(pcs_version_split)

print os.system("sed -i 's/"+settings.pcs_version+"/"+new_version + "/' setup.py")
print os.system("sed -i 's/"+settings.pcs_version+"/"+new_version + "/' pcs/settings.py")
print os.system("sed -i 's/"+settings.pcs_version+"/"+new_version + "/' pcs/pcs.8")
print os.system("sed -i 's/"+settings.pcs_version+"/"+new_version + "/' pcsd/pcsd.rb")

print os.system("git diff")
print "Look good? (y/n)"
choice = sys.stdin.read(1)
if choice != "y":
  print "Ok, exiting"
  sys.exit(0)

print os.system("git commit -a -m 'Bumped to "+new_version+"'")
print os.system("git tag "+new_version)
