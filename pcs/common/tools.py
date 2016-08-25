from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import threading


def simple_cache(func):
    cache = {
        "was_run": False,
        "value": None
    }

    def wrapper():
        if not cache["was_run"]:
            cache["value"] = func()
            cache["was_run"] = True
        return cache["value"]

    return wrapper


def run_parallel(worker, data_list):
    thread_list = []
    for args, kwargs in data_list:
        thread = threading.Thread(target=worker, args=args, kwargs=kwargs)
        thread.daemon = True
        thread_list.append(thread)
        thread.start()

    for thread in thread_list:
        thread.join()

def format_environment_error(e):
    if e.filename:
        return "{0}: '{1}'".format(e.strerror, e.filename)
    return e.strerror

def join_multilines(strings):
    return "\n".join([a.strip() for a in strings if a.strip()])
