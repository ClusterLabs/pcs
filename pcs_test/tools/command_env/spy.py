from urllib.parse import parse_qs

from pcs.lib.corosync.live import (
    get_local_corosync_conf as original_get_local_corosync_conf,
)


def print_caption(caption, indent=2, underline="-"):
    print(
        "\n{0}{1}\n{0}{2}".format(
            " " * indent, caption, underline * len(caption)
        )
    )


def print_initialize(spy):
    print_caption(
        "Initialize {0}".format(spy.__class__.__name__),
        indent=0,
        underline="=",
    )


def print_call(spy, name):
    print_caption("{0}: {1}".format(spy.__class__.__name__, name))


def print_line(content):
    print("    {0}".format(content))


def print_long_text(name, potentially_long_text):
    if "\n" not in potentially_long_text:
        print_line("{0}: '{1}'".format(name, potentially_long_text))
    else:
        print_line("{0}: '''\\".format(name))
        for line in potentially_long_text.split("\n"):
            print_line("  {0}".format(line))
        print_line("'''")


class NodeCommunicator:
    def __init__(self, original_node_communicator):
        print_initialize(self)
        self.__communicator = original_node_communicator

    def add_requests(self, request_list):
        print_call(self, "add_requests")
        for request in request_list:
            print_line(request)
            print_line(parse_qs(request.data))
        return self.__communicator.add_requests(request_list)

    def start_loop(self):
        for response in self.__communicator.start_loop():
            print_call(self, "yield response start")
            print_line(response)
            yield response


class Runner:
    def __init__(self, original_runner):
        print_initialize(self)
        self.__runner = original_runner

    def run(
        self, args, stdin_string=None, env_extend=None, binary_output=False
    ):
        print_call(self, "run")
        print_line("args: {0}".format(args))
        if stdin_string:
            print_long_text("stdin_string", stdin_string)
        if env_extend:
            print_line("env_extend: {0}".format(env_extend))
        if binary_output:
            print_line("binary_output: {0}".format(binary_output))
        stdout, stderr, returncode = self.__runner.run(
            args, stdin_string, env_extend, binary_output,
        )
        print_long_text("stdout", stdout)
        print_long_text("stderr", stderr)
        print_line("returncode:{0}".format(returncode))
        return stdout, stderr, returncode


def get_local_corosync_conf():
    print_caption("get_local_corosync_conf", indent=0)
    corosync_conf = original_get_local_corosync_conf()
    for line in corosync_conf.split("\n"):
        print_line(line)
    return corosync_conf
