from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial


def build(*middleware_list):
    def run(command, lib, argv, modificators):
        next = command
        for next_command in reversed(middleware_list):
            next = partial(next_command, next)

        next(lib, argv, modificators)
    return run

def cib(use_local_cib, cib_content, write_cib):
    def apply(next, lib, argv, modificators):
        if use_local_cib:
            lib.env.cib_data = cib_content

        next(lib, argv, modificators)

        if use_local_cib:
            write_cib(lib.env.cib_data)
    return apply

def corosync_conf(next, lib, argv, modificators):
    next(lib, argv, modificators)
