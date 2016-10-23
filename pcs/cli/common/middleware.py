from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from collections import namedtuple
from functools import partial

from pcs.cli.common import console_report


def build(*middleware_list):
    def run(command, env, *args, **kwargs):
        next_in_line = command
        for next_command in reversed(middleware_list):
            next_in_line = partial(next_command, next_in_line)

        return next_in_line(env, *args, **kwargs)
    return run

def cib(use_local_cib, load_cib_content, write_cib):
    """
    return configured middleware that cares about local cib
    bool use_local_cib is flag if local cib was required
    callable load_cib_content returns local cib content, take no params
    callable write_cib put content of cib to required place
    """
    def apply(next_in_line, env, *args, **kwargs):
        if use_local_cib:
            original_content = load_cib_content()
            env.cib_data = original_content

        result_of_next = next_in_line(env, *args, **kwargs)

        if use_local_cib and env.cib_data != original_content:
            write_cib(env.cib_data, env.cib_upgraded)

        return result_of_next
    return apply

def corosync_conf_existing(local_file_path):
    def apply(next_in_line, env, *args, **kwargs):
        if local_file_path:
            try:
                env.corosync_conf_data = open(local_file_path).read()
            except EnvironmentError as e:
                raise console_report.error("Unable to read {0}: {1}".format(
                    local_file_path,
                    e.strerror
                ))

        result_of_next = next_in_line(env, *args, **kwargs)

        if local_file_path:
            try:
                f = open(local_file_path, "w")
                f.write(env.corosync_conf_data)
                f.close()
            except EnvironmentError as e:
                raise console_report.error("Unable to write {0}: {1}".format(
                    local_file_path,
                    e.strerror
                ))
        return result_of_next
    return apply


def cluster_conf_read_only(local_file_path):
    def apply(next_in_line, env, *args, **kwargs):
        if local_file_path:
            try:
                env.cluster_conf_data = open(local_file_path).read()
            except EnvironmentError as e:
                raise console_report.error("Unable to read {0}: {1}".format(
                    local_file_path,
                    e.strerror
                ))

        return next_in_line(env, *args, **kwargs)
    return apply


def create_middleware_factory(**kwargs):
    return namedtuple('MiddlewareFactory', kwargs.keys())(**kwargs)
