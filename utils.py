import os, subprocess
import ccs

# usefile & filename variables are set in ccs module
usefile = False
filename = ""

# Run command, with environment and return output
def run(args):
    env_var = os.environ
    if usefile:
        env_var["CIB_file"] = filename

    p = subprocess.Popen(args, stdout=subprocess.PIPE, env = env_var)
    output = p.stdout.read()
    return output
