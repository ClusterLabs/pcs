import os.path
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CURRENT_DIR, "pacemaker_metadata.d")


def write_file_to_stdout(file_name):
    with open(file_name) as file:
        sys.stdout.write(file.read())


def write_local_file_to_stdout(file_name):
    write_file_to_stdout(os.path.join(DATA_DIR, file_name))


def main():
    pcmk_binary = sys.argv[0].rsplit("/", 1)[-1]
    argv = sys.argv[1:]
    if pcmk_binary == "pacemaker-fenced":
        return pacemaker_fenced(argv)
    raise AssertionError()


def pacemaker_fenced(argv):
    if len(argv) != 1:
        raise AssertionError()
    if argv[0] != "metadata":
        raise AssertionError()
    write_local_file_to_stdout("pacemaker_fenced.xml")


if __name__ == "__main__":
    main()
