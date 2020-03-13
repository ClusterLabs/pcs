# pylint: disable=too-many-lines
from collections.abc import Iterable
from typing import Mapping
import sys

from pcs.common import file_type_codes
from pcs.common.file import RawFileError
from pcs.common.fencing_topology import TARGET_TYPE_ATTRIBUTE
from pcs.common.reports import codes
from pcs.common.str_tools import (
    format_optional,
)

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

def id_belongs_to_unexpected_type(info):
    return "'{id}' is not {expected_type}".format(
        id=info["id"],
        expected_type=typelist_to_string(info["expected_types"], article=True)
    )

def object_with_id_in_unexpected_context(info):
    context_type = type_to_string(info["expected_context_type"])
    if info.get("expected_context_id", ""):
        context = "{_expected_context_type} '{expected_context_id}'".format(
            _expected_context_type=context_type,
            **info
        )
    else:
        context = "'{_expected_context_type}'".format(
            _expected_context_type=context_type,
        )
    return "{_type} '{id}' exists but does not belong to {_context}".format(
        _context=context,
        _type=type_to_string(info["type"]),
        **info
    )

def id_not_found(info):
    desc = format_optional(typelist_to_string(info["expected_types"]), "{0} ")
    if not info["context_type"] or not info["context_id"]:
        return "{desc}'{id}' does not exist".format(desc=desc, id=info["id"])

    return (
        "there is no {desc}'{id}' in the {context_type} '{context_id}'".format(
            desc=desc,
            id=info["id"],
            context_type=info["context_type"],
            context_id=info["context_id"],
        )
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

#Each value (a callable taking report_item.info) returns a message.
#Force text will be appended if necessary.
#If it is necessary to put the force text inside the string then the callable
#must take the force_text parameter.
CODE_TO_MESSAGE_BUILDER_MAP = {
    codes.ID_ALREADY_EXISTS: lambda info:
        "'{id}' already exists"
        .format(**info)
    ,

    codes.ID_BELONGS_TO_UNEXPECTED_TYPE: id_belongs_to_unexpected_type,

    codes.OBJECT_WITH_ID_IN_UNEXPECTED_CONTEXT:
        object_with_id_in_unexpected_context
    ,

    codes.ID_NOT_FOUND: id_not_found,

    codes.STONITH_RESOURCES_DO_NOT_EXIST: lambda info:
        "Stonith resource(s) '{stonith_id_list}' do not exist"
        .format(
            stonith_id_list="', '".join(info["stonith_ids"]),
            **info
        )
    ,

    codes.CIB_LOAD_ERROR: "unable to get cib",

    codes.CIB_LOAD_ERROR_SCOPE_MISSING: lambda info:
        "unable to get cib, scope '{scope}' not present in cib"
        .format(**info)
    ,

    codes.CIB_LOAD_ERROR_BAD_FORMAT: lambda info:
       "unable to get cib, {reason}"
       .format(**info)
    ,

    codes.CIB_LOAD_ERROR_GET_NODES_FOR_VALIDATION:
        "Unable to load CIB to get guest and remote nodes from it, "
        "those nodes cannot be considered in configuration validation"
    ,

    codes.CIB_CANNOT_FIND_MANDATORY_SECTION: lambda info:
        "Unable to get {section} section of cib"
        .format(**info)
    ,

    codes.CIB_PUSH_ERROR: lambda info:
        "Unable to update cib\n{reason}\n{pushed_cib}"
        .format(**info)
    ,

    codes.CIB_DIFF_ERROR: lambda info:
        "Unable to diff CIB: {reason}\n{cib_new}"
        .format(**info)
    ,

    codes.CIB_SIMULATE_ERROR: lambda info:
        "Unable to simulate changes in CIB{_reason}"
        .format(
            _reason=format_optional(info["reason"], ": {0}"),
            **info
        )
    ,

    codes.CIB_PUSH_FORCED_FULL_DUE_TO_CRM_FEATURE_SET: lambda info:
        (
            "Replacing the whole CIB instead of applying a diff, a race "
            "condition may happen if the CIB is pushed more than once "
            "simultaneously. To fix this, upgrade pacemaker to get "
            "crm_feature_set at least {required_set}, current is {current_set}."
        ).format(**info)
    ,

    codes.CIB_SAVE_TMP_ERROR: lambda info:
        "Unable to save CIB to a temporary file: {reason}"
        .format(**info)
    ,

    codes.RESOURCE_BUNDLE_ALREADY_CONTAINS_A_RESOURCE: lambda info:
        (
            "bundle '{bundle_id}' already contains resource '{resource_id}'"
            ", a bundle may contain at most one resource"
        ).format(**info)
    ,
}
