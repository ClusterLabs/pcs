from __future__ import (
    absolute_import,
    division,
    print_function,
)

import sys
from lxml import etree
import threading

_PYTHON2 = (sys.version_info.major == 2)

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

def is_string(candidate):
    """
    Return if candidate is string.
    Simply lookin solution isinstance(candidate, "".__class__) does not work:

    >>> isinstance("", "".__class__), isinstance(u"", "".__class__)
    (True, False)

    This code also needs to deal with python2 and python3 and unicode type is in
    python2 but not in python3.
    """
    string_list = [str, bytes]
    try:
        string_list.append(unicode)
    except NameError: #unicode is not present in python3
        pass

    return any([isinstance(candidate, string) for string in string_list])

def xml_fromstring(xml):
    # If the xml contains encoding declaration such as:
    # <?xml version="1.0" encoding="UTF-8"?>
    # we get an exception in python3:
    # ValueError: Unicode strings with encoding declaration are not supported.
    # Please use bytes input or XML fragments without declaration.
    # So we encode the string to bytes.
    # In python2 we cannot do that as it causes a UnicodeDecodeError if the xml
    # contains a non-ascii character.
    return etree.fromstring(
        xml if _PYTHON2 else xml.encode("utf-8"),
        #it raises on a huge xml without the flag huge_tree=True
        #see https://bugzilla.redhat.com/show_bug.cgi?id=1506864
        etree.XMLParser(huge_tree=True)
    )
