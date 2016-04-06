from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)


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
