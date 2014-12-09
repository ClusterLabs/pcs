import os,sys
import difflib
import subprocess
import re
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir) 
import utils

pcs_location = "../pcs.py"

# Run pcs with -f on specified file
def pcs(testfile, args = ""):
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
        print ""
        print "".join(diff)
        assert False,[a]

def isMinimumPacemakerVersion(cmajor,cminor,crev):
    p = subprocess.Popen(["crm_mon","--version"], stdout=subprocess.PIPE)
    (stdout, stderr) = p.communicate()
    pacemaker_version =  stdout.split("\n")[0]
    r = re.compile(r"Pacemaker (\d+)\.(\d+)\.(\d+)")
    m = r.match(pacemaker_version)
    major = int(m.group(1))
    minor = int(m.group(2))
    rev = int(m.group(3))

    if major > cmajor or (major == cmajor and minor > cminor) or (major == cmajor and minor == cminor and rev >= crev):
        return True
    return False

