import os,sys
import difflib
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

    if "--corosync_conf" in args:
        return utils.run([pcs_location, "-f", testfile] + arg_split_temp)
    else:
        return utils.run([pcs_location, "-f", testfile, "--corosync_conf=corosync.conf"] + arg_split_temp)

# Compare output and print usable diff (diff b a)
# a is the actual output, b is what should be output
def ac(a,b):
    if a != b:
        d = difflib.Differ()
        diff = d.compare(b.splitlines(1),a.splitlines(1))
        print ""
        print "".join(diff)
        assert False,[a]

