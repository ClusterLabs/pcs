import os,sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir) 
import utils

pcs_location = "../pcs.py"

# Run pcs with -f on specified file
def pcs(testfile, args):
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
            if arg.find("'") != -1:
                in_quote = True

    return utils.run([pcs_location, "-f", testfile, "--corosync_conf=corosync.conf"] + arg_split_temp)

