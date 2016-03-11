from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os.path
import difflib
import re
import xml.dom.minidom

from pcs.test.tools.resources import get_test_resource as rc

from pcs import utils

pcs_location = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pcs"
)
temp_cib = rc("temp-cib.xml")

class PcsRunner(object):
    def __init__(self, testfile=temp_cib):
        self.testfile = testfile


    def run(self, args):
        return pcs(self.testfile, args)


def pcs(testfile, args = ""):
    """Run pcs with -f on specified file
    Return tuple with:
        shell stdoutdata
        shell returncode
    """
    if args == "":
        args = testfile
        testfile = temp_cib
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
        corosync_conf = rc("corosync.conf")
        conf_opts.append("--corosync_conf="+corosync_conf)
    if "--cluster_conf" not in args:
        cluster_conf = rc("cluster.conf")
        conf_opts.append("--cluster_conf="+cluster_conf)
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
    output, dummy_retval = utils.run(["crm_mon", "--version"])
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
