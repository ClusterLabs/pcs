import os, subprocess
import sys
import ccs

# usefile & filename variables are set in ccs module
usefile = False
filename = ""

# Run command, with environment and return output
def run(args):
    env_var = os.environ
    if usefile:
        env_var["CIB_file"] = filename

    if not os.path.isfile(filename):
        try:
            write_empty_cib(filename)
        except IOError:
            print "Unable to write to file: " + filename
            sys.exit(1)

    try:
        p = subprocess.Popen(args, stdout=subprocess.PIPE, env = env_var)
        output = p.stdout.read()
    except OSError:
        print "Unable to locate command: " + args[0]
        sys.exit(1)

    return output

def write_empty_cib(filename):

    empty_xml = """<?xml version="1.0" encoding="UTF-8"?>
<cib admin_epoch="0" epoch="1" num_updates="1" validate-with="pacemaker-1.2">
  <configuration>
    <crm_config/>
    <nodes/>
    <resources/>
    <constraints/>
  </configuration>
  <status/>
</cib>"""
    f = open(filename, 'w')
    f.write(empty_xml)
    f.close()
