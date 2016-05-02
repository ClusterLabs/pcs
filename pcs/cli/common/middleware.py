from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial


def build(*middleware_list):
    def run(command, lib, argv, modificators):
        next_in_line = command
        for next_command in reversed(middleware_list):
            next_in_line = partial(next_command, next_in_line)

        next_in_line(lib, argv, modificators)
    return run

def cib(use_local_cib, cib_content, write_cib):
    def apply(next_in_line, lib, argv, modificators):
        if use_local_cib:
            lib.env.cib_data = cib_content

        next_in_line(lib, argv, modificators)

        if use_local_cib:
            write_cib(lib.env.cib_data)
    return apply

def corosync_conf(next_in_line, lib, argv, modificators):
    next_in_line(lib, argv, modificators)
