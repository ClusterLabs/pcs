import os,sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir) 
import utils

pcs_location = "../pcs.py"

# Run pcs with -f on specified file
def pcs(testfile, args):
    return utils.run([pcs_location, "-f", testfile, "--corosync_conf=corosync.conf"] + args.split())

