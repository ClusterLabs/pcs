#!/usr/bin/python

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
import os
import locale
import datetime

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "pcs")
)
import settings


locale.setlocale(locale.LC_ALL, ("en_US", "UTF-8"))

# Get the current version, increment by 1, verify changes, git commit & tag
pcs_version_split = settings.pcs_version.split('.')
pcs_version_split[2] = str(int(pcs_version_split[2]) + 1)
new_version = ".".join(pcs_version_split)

print(os.system("sed -i 's/"+settings.pcs_version+"/"+new_version+"/' setup.py"))
print(os.system("sed -i 's/"+settings.pcs_version+"/"+new_version+"/' pcs/settings_default.py"))
print(os.system("sed -i 's/"+settings.pcs_version+"/"+new_version+"/' pcsd/bootstrap.rb"))
print(os.system("sed -i 's/\#\# \[Unreleased\]/\#\# ["+new_version+"] - "+datetime.date.today().strftime('%Y-%m-%d')+"/' CHANGELOG.md"))

manpage_head = '.TH PCS "8" "{date}" "pcs {version}" "System Administration Utilities"'.format(
    date=datetime.date.today().strftime('%B %Y'),
    version=new_version
)
print(os.system("sed -i '1c " + manpage_head + "' pcs/pcs.8"))

print(os.system("git diff"))
print("Look good? (y/n)")
choice = sys.stdin.read(1)
if choice != "y":
    print("Ok, exiting")
    sys.exit(0)

print(os.system("git commit -a -m 'Bumped to "+new_version+"'"))
print(os.system("git tag "+new_version))
