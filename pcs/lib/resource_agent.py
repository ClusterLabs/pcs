from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os
from lxml import etree

from pcs import settings
from pcs.lib import error_codes
from pcs.lib.errors import LibraryError
from pcs.lib.errors import ReportItem
from pcs.lib.pacemaker_values import is_true
from pcs.lib.external import is_path_runnable
from pcs.common.tools import simple_cache


class UnsupportedResourceAgent(LibraryError):
    pass


class InvalidAgentName(LibraryError):
    pass


class AgentNotFound(LibraryError):
    pass


class UnableToGetAgentMetadata(LibraryError):
    pass


class InvalidMetadataFormat(LibraryError):
    pass


def __is_path_abs(path):
    return path == os.path.abspath(path)


def __get_text_from_dom_element(element):
    if element is None or element.text is None:
        return ""
    else:
        return element.text.strip()


def __get_invalid_metadata_format_exception():
    return InvalidMetadataFormat(ReportItem.error(
        error_codes.INVALID_METADATA_FORMAT,
        "invalid agent metadata format"
    ))


def _get_parameter(parameter_dom):
    """
    Returns dictionary that describes parameter.
    dictionary format:
    {
        name: name of parameter
        longdesc: long description,
        shortdesc: short description,
        type: data type od parameter,
        default: default value,
        required: True if is required parameter, False otherwise
    }

    parameter_dom -- parameter dom element
    """
    if parameter_dom.tag != "parameter" or parameter_dom.get("name") is None:
        raise __get_invalid_metadata_format_exception()

    longdesc = __get_text_from_dom_element(parameter_dom.find("longdesc"))
    shortdesc = __get_text_from_dom_element(parameter_dom.find("shortdesc"))

    content = parameter_dom.find("content")
    if content is None:
        val_type = "string"
    else:
        val_type = content.get("type", "string")

    return {
        "name": parameter_dom.get("name"),
        "longdesc": longdesc,
        "shortdesc": shortdesc,
        "type": val_type,
        "default": None if content is None else content.get("default"),
        "required": is_true(parameter_dom.get("required", "0"))
    }


def _get_agent_parameters(metadata_dom):
    """
    Returns list of parameters from agents metadata

    metadata_dom -- agent's metadata dom
    """
    if metadata_dom.tag != "resource-agent":
        raise __get_invalid_metadata_format_exception()

    params_el = metadata_dom.find("parameters")
    if params_el is None:
        return []

    return [
        _get_parameter(parameter) for parameter in params_el.iter("parameter")
    ]


def _get_pcmk_advanced_stonith_parameters(runner):
    """Returns advanced instance attributes for stonith devices"""
    @simple_cache
    def __get_stonithd_parameters():
        output, retval = runner.run([settings.stonithd_binary, "metadata"])
        if retval != 0:
            raise UnableToGetAgentMetadata(ReportItem.error(
                error_codes.UNABLE_TO_GET_AGENT_METADATA,
                "unable to get metadata of stonithd",
                info={"external_exitcode": retval, "external_output": output}
            ))

        try:
            params = _get_agent_parameters(etree.fromstring(output))
            for param in params:
                param.update({"advanced": True})
            return params
        except etree.XMLSyntaxError:
            raise __get_invalid_metadata_format_exception()

    return __get_stonithd_parameters()


def get_fence_agent_metadata(runner, fence_agent):
    """
    Returns dom of metadata for specified fence agent

    fence_agent -- fence agent name, should start with 'fence_'
    """

    def __get_error(info):
        return UnableToGetAgentMetadata(ReportItem.error(
            error_codes.UNABLE_TO_GET_AGENT_METADATA,
            "unable to get metadata of fence agent '{agent_name}'",
            info=info
        ))

    script_path = os.path.join(settings.fence_agent_binaries, fence_agent)

    if not (
        fence_agent.startswith("fence_") and
        __is_path_abs(script_path) and
        is_path_runnable(script_path)
    ):
        raise AgentNotFound(ReportItem.error(
            error_codes.INVALID_RESOURCE_NAME,
            "fence agent '{agent_name}' not found.",
            info={"agent_name": fence_agent}
        ))

    output, retval = runner.run([script_path, "-o", "metadata"])

    if retval != 0:
        raise __get_error({
            "agent_name": fence_agent,
            "external_exitcode": retval,
            "external_output": output
        })

    try:
        return etree.fromstring(output)
    except etree.XMLSyntaxError as e:
        raise __get_error({
            "agent_name": fence_agent,
            "error_info": str(e)
        })


def _get_nagios_resource_agent_metadata(agent):
    """
    Returns metadata dom for specified nagios resource agent

    agent -- name of nagios resource agent
    """
    agent_name = "nagios:" + agent
    metadata_path = os.path.join(settings.nagios_metadata_path, agent + ".xml")

    if not __is_path_abs(metadata_path):
        raise AgentNotFound(ReportItem.error(
            error_codes.INVALID_RESOURCE_NAME,
            "resource agent '{agent_name}' not found.",
            info={"agent_name": agent_name}
        ))

    try:
        return etree.parse(metadata_path).getroot()
    except Exception as e:
        raise UnableToGetAgentMetadata(ReportItem.error(
            error_codes.UNABLE_TO_GET_AGENT_METADATA,
            "unable to get metadata of resource agent '{agent_name}': " +
            "{error_info}",
            info={
                "agent_name": agent_name,
                "error_info": str(e)
            }
        ))


def _get_ocf_resource_agent_metadata(runner, provider, agent):
    """
    Returns metadata dom for specified ocf resource agent

    provider -- resource agent provider
    agent -- resource agent name
    """
    agent_name = "ocf:" + provider + ":" + agent

    def __get_error(info):
        return UnableToGetAgentMetadata(ReportItem.error(
            error_codes.UNABLE_TO_GET_AGENT_METADATA,
            "unable to get metadata of resource agent '{agent_name}'",
            info=info
        ))

    script_path = os.path.join(settings.ocf_resources, provider, agent)

    if not __is_path_abs(script_path) or not is_path_runnable(script_path):
        raise AgentNotFound(ReportItem.error(
            error_codes.INVALID_RESOURCE_NAME,
            "resource agent '{agent_name}' not found.",
            info={"agent_name": agent_name}
        ))

    output, retval = runner.run(
        [script_path, "meta-data"],
        env_extend={"OCF_ROOT": settings.ocf_root}
    )

    if retval != 0:
        raise __get_error({
            "agent_name": agent_name,
            "external_exitcode": retval,
            "external_output": output
        })

    try:
        return etree.fromstring(output)
    except etree.XMLSyntaxError as e:
        raise __get_error({
            "agent_name": agent_name,
            "error_info": str(e)
        })


def get_agent_desc(metadata_dom):
    """
    Returns dictionary which contains description of agent from it's metadata.
    dictionary format:
    {
        longdesc: long description
        shortdesc: short description
    }

    metadata_dom -- metadata dom of agent
    """
    if metadata_dom.tag != "resource-agent":
        raise __get_invalid_metadata_format_exception()

    shortdesc_el = metadata_dom.find("shortdesc")
    if shortdesc_el is None:
        shortdesc = metadata_dom.get("shortdesc", "")
    else:
        shortdesc = shortdesc_el.text

    return {
        "longdesc": __get_text_from_dom_element(metadata_dom.find("longdesc")),
        "shortdesc": "" if shortdesc is None else shortdesc.strip()
    }


def _filter_fence_agent_parameters(parameters):
    """
    Returns filtered list of fence agent parameters. It removes parameters
    that user should not be setting.

    parameters -- list of fence agent parameters
    """
    banned_parameters = ["debug", "action", "verbose", "version", "help"]
    return [
        param for param in parameters if param["name"] not in banned_parameters
    ]


def get_fence_agent_parameters(runner, metadata_dom):
    """
    Returns complete list of parameters for fence agent from it's metadata.

    metadata_dom -- metadata dom of fence agent
    """
    return (
        _filter_fence_agent_parameters(_get_agent_parameters(metadata_dom)) +
        _get_pcmk_advanced_stonith_parameters(runner)
    )


def get_resource_agent_parameters(metadata_dom):
    """
    Returns complete list of parameters for resource agent from it's
    metadata.

    metadata_dom -- metadata dom of resource agent
    """
    return _get_agent_parameters(metadata_dom)


def get_resource_agent_metadata(runner, agent):
    """
    Returns metadata of specified agent as dom

    agent -- agent name
    """
    error = UnsupportedResourceAgent(ReportItem.error(
        error_codes.UNSUPPORTED_RESOURCE_AGENT,
        "resource agent '{agent}' is not supported",
        info={"agent": agent}
    ))
    if agent.startswith("ocf:"):
        agent_info = agent.split(":", 2)
        if len(agent_info) != 3:
            raise error
        return _get_ocf_resource_agent_metadata(runner, *agent_info[1:])
    elif agent.startswith("nagios:"):
        return _get_nagios_resource_agent_metadata(agent.split("nagios:", 1)[1])
    else:
        raise error
