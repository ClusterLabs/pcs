from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os.path
import sys
import difflib
import subprocess
import re
import xml.dom.minidom
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir)

import utils


pcs_location = "../pcs.py"

def pcs(testfile, args = ""):
    """Run pcs with -f on specified file
    Return tuple with:
        shell stdoutdata
        shell returncode
    """
    if args == "":
        args = testfile
        testfile = "temp.xml"
    arg_split = args.split()
    arg_split_temp = []
    in_quote = False
    for arg in arg_split:
        if in_quote:
            arg_split_temp[-1] = arg_split_temp[-1] + " " + arg.replace("'","")
            if arg.find("'") != -1:
                in_quote = False
        else:
            arg_split_temp.append(arg.replace("'",""))
            if arg.find("'") != -1 and not (arg[0] == "'" and arg[-1] == "'"):
                in_quote = True

    conf_opts = []
    if "--corosync_conf" not in args:
        conf_opts.append("--corosync_conf=corosync.conf")
    if "--cluster_conf" not in args:
        conf_opts.append("--cluster_conf=cluster.conf")
    return utils.run([pcs_location, "-f", testfile] + conf_opts + arg_split_temp)

# Compare output and print usable diff (diff b a)
# a is the actual output, b is what should be output
def ac(a,b):
    if a != b:
        d = difflib.Differ()
        diff = d.compare(b.splitlines(1),a.splitlines(1))
        print("")
        print("".join(diff))
        assert False,[a]

def isMinimumPacemakerVersion(cmajor,cminor,crev):
    output, retval = utils.run(["crm_mon", "--version"])
    pacemaker_version = output.split("\n")[0]
    r = re.compile(r"Pacemaker (\d+)\.(\d+)\.(\d+)")
    m = r.match(pacemaker_version)
    major = int(m.group(1))
    minor = int(m.group(2))
    rev = int(m.group(3))

    if major > cmajor or (major == cmajor and minor > cminor) or (major == cmajor and minor == cminor and rev >= crev):
        return True
    return False


def get_child_elements(el):
    return [e for e in el.childNodes if e.nodeType == xml.dom.minidom.Node.ELEMENT_NODE]
