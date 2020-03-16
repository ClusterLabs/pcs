# pylint: disable=too-many-lines
from collections.abc import Iterable
from typing import Mapping
import sys

from pcs.common import file_type_codes
from pcs.common.file import RawFileError
from pcs.common.fencing_topology import TARGET_TYPE_ATTRIBUTE

INSTANCE_SUFFIX = "@{0}"
NODE_PREFIX = "{0}: "

_type_translation = {
    "acl_group": "ACL group",
    "acl_permission": "ACL permission",
    "acl_role": "ACL role",
    "acl_target": "ACL user",
    # Pacemaker-2.0 deprecated masters. Masters are now called promotable
    # clones. We treat masters as clones. Do not report we were doing something
    # with a master, say we were doing it with a clone instead.
    "master": "clone",
    "primitive": "resource",
}
_type_articles = {
    "ACL group": "an",
    "ACL user": "an",
    "ACL role": "an",
    "ACL permission": "an",
}
_file_operation_translation = {
    RawFileError.ACTION_CHMOD: "change permissions of",
    RawFileError.ACTION_CHOWN: "change ownership of",
    RawFileError.ACTION_READ: "read",
    RawFileError.ACTION_REMOVE: "remove",
    RawFileError.ACTION_WRITE: "write",
}
_file_role_translation = {
    file_type_codes.BOOTH_CONFIG: "Booth configuration",
    file_type_codes.BOOTH_KEY: "Booth key",
    file_type_codes.COROSYNC_AUTHKEY: "Corosync authkey",
    file_type_codes.PCS_DR_CONFIG: "disaster-recovery configuration",
    file_type_codes.PACEMAKER_AUTHKEY: "Pacemaker authkey",
    file_type_codes.PCSD_ENVIRONMENT_CONFIG: "pcsd configuration",
    file_type_codes.PCSD_SSL_CERT: "pcsd SSL certificate",
    file_type_codes.PCSD_SSL_KEY: "pcsd SSL key",
    file_type_codes.PCS_KNOWN_HOSTS: "known-hosts",
    file_type_codes.PCS_SETTINGS_CONF: "pcs configuration",
}
_file_role_to_option_translation: Mapping[str, str] = {
    file_type_codes.BOOTH_CONFIG: "--booth-conf",
    file_type_codes.BOOTH_KEY: "--booth-key",
    file_type_codes.CIB: "-f",
    file_type_codes.COROSYNC_CONF: "--corosync_conf",
}

def warn(message):
    sys.stdout.write(format_message(message, "Warning: "))

def format_message(message, prefix):
    return "{0}{1}\n".format(prefix, message)

def error(message):
    sys.stderr.write(format_message(message, "Error: "))
    return SystemExit(1)

def format_fencing_level_target(target_type, target_value):
    if target_type == TARGET_TYPE_ATTRIBUTE:
        return "{0}={1}".format(target_value[0], target_value[1])
    return target_value

def format_file_action(action):
    return _file_operation_translation.get(action, action)

def format_file_role(role):
    return _file_role_translation.get(role, role)

def is_iterable_not_str(value):
    return isinstance(value, Iterable) and not isinstance(value, str)

def type_to_string(type_name, article=False):
    if not type_name:
        return ""
    # get a translation or make a type_name a string
    translated = _type_translation.get(type_name, "{0}".format(type_name))
    if not article:
        return translated
    return "{article} {type}".format(
        article=_type_articles.get(translated, "a"),
        type=translated
    )

def typelist_to_string(type_list, article=False):
    if not type_list:
        return ""
    # use set to drop duplicate items:
    # * master is translated to clone
    # * i.e. "clone, master" is translated to "clone, clone"
    # * so we want to drop the second clone
    new_list = sorted({
        # get a translation or make a type_name a string
        _type_translation.get(type_name, "{0}".format(type_name))
        for type_name in type_list
    })
    types = "/".join(new_list)
    if not article:
        return types
    return "{article} {types}".format(
        article=_type_articles.get(new_list[0], "a"),
        types=types
    )

def build_node_description(node_types):
    if not node_types:
        return  "Node"

    label = "{0} node".format

    if isinstance(node_types, str):
        return label(node_types)

    if len(node_types) == 1:
        return label(node_types[0])

    return "nor " + " or ".join([label(ntype) for ntype in node_types])
