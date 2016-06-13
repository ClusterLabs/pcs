from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os
from lxml import etree

from pcs import settings
from pcs.lib import reports
from pcs.lib.errors import ReportItemSeverity
from pcs.lib.pacemaker_values import is_true
from pcs.lib.external import is_path_runnable
from pcs.common import report_codes
from pcs.common.tools import simple_cache


class ResourceAgentLibError(Exception):
    pass


class ResourceAgentCommonError(ResourceAgentLibError):
    # pylint: disable=super-init-not-called
    def __init__(self, agent):
        self.agent = agent


class UnsupportedResourceAgent(ResourceAgentCommonError):
    pass


class AgentNotFound(ResourceAgentCommonError):
    pass


class UnableToGetAgentMetadata(ResourceAgentCommonError):
    # pylint: disable=super-init-not-called
    def __init__(self, agent, message):
        self.agent = agent
        self.message = message


class InvalidMetadataFormat(ResourceAgentLibError):
    pass


def __is_path_abs(path):
    return path == os.path.abspath(path)


def __get_text_from_dom_element(element):
    if element is None or element.text is None:
        return ""
    else:
        return element.text.strip()


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
    Raises InvalidMetadataFormat if parameter_dom is not in valid format

    parameter_dom -- parameter dom element
    """
    if parameter_dom.tag != "parameter" or parameter_dom.get("name") is None:
        raise InvalidMetadataFormat()

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
    Returns list of parameters from agents metadata.
    Raises InvalidMetadataFormat if metadata_dom is not in valid format.

    metadata_dom -- agent's metadata dom
    """
    if metadata_dom.tag != "resource-agent":
        raise InvalidMetadataFormat()

    params_el = metadata_dom.find("parameters")
    if params_el is None:
        return []

    return [
        _get_parameter(parameter) for parameter in params_el.iter("parameter")
    ]


def _get_pcmk_advanced_stonith_parameters(runner):
    """
    Returns advanced instance attributes for stonith devices
    Raises UnableToGetAgentMetadata if there is problem with obtaining
        metadata of stonithd.
    Raises InvalidMetadataFormat if obtained metadata are not in valid format.

    runner -- CommandRunner
    """
    @simple_cache
    def __get_stonithd_parameters():
        output, retval = runner.run(
            [settings.stonithd_binary, "metadata"], ignore_stderr=True
        )
        if output.strip() == "":
            raise UnableToGetAgentMetadata("stonithd", output)

        try:
            params = _get_agent_parameters(etree.fromstring(output))
            for param in params:
                param["longdesc"] = "{0}\n{1}".format(
                    param["shortdesc"], param["longdesc"]
                ).strip()
                is_advanced = param["shortdesc"].startswith("Advanced use only")
                param["advanced"] = is_advanced
            return params
        except etree.XMLSyntaxError:
            raise InvalidMetadataFormat()

    return __get_stonithd_parameters()


def get_fence_agent_metadata(runner, fence_agent):
    """
    Returns dom of metadata for specified fence agent
    Raises AgentNotFound if fence_agent doesn't starts with fence_ or it is
        relative path or file is not runnable.
    Raises UnableToGetAgentMetadata if there was problem getting or
        parsing metadata.

    runner -- CommandRunner
    fence_agent -- fence agent name, should start with 'fence_'
    """
    script_path = os.path.join(settings.fence_agent_binaries, fence_agent)

    if not (
        fence_agent.startswith("fence_") and
        __is_path_abs(script_path) and
        is_path_runnable(script_path)
    ):
        raise AgentNotFound(fence_agent)

    output, retval = runner.run(
        [script_path, "-o", "metadata"], ignore_stderr=True
    )

    if output.strip() == "":
        raise UnableToGetAgentMetadata(fence_agent, output)

    try:
        return etree.fromstring(output)
    except etree.XMLSyntaxError as e:
        raise UnableToGetAgentMetadata(fence_agent, str(e))


def _get_nagios_resource_agent_metadata(agent):
    """
    Returns metadata dom for specified nagios resource agent.
    Raises AgentNotFound if agent is relative path.
    Raises UnableToGetAgentMetadata if there was problem getting or
        parsing metadata.

    agent -- name of nagios resource agent
    """
    agent_name = "nagios:" + agent
    metadata_path = os.path.join(settings.nagios_metadata_path, agent + ".xml")

    if not __is_path_abs(metadata_path):
        raise AgentNotFound(agent_name)

    try:
        return etree.parse(metadata_path).getroot()
    except Exception as e:
        raise UnableToGetAgentMetadata(agent_name, str(e))


def _get_ocf_resource_agent_metadata(runner, provider, agent):
    """
    Returns metadata dom for specified ocf resource agent
    Raises AgentNotFound if specified agent is relative path or file is not
        runnable.
    Raises UnableToGetAgentMetadata if there was problem getting or
    parsing metadata.

    runner -- CommandRunner
    provider -- resource agent provider
    agent -- resource agent name
    """
    agent_name = "ocf:" + provider + ":" + agent

    script_path = os.path.join(settings.ocf_resources, provider, agent)

    if not __is_path_abs(script_path) or not is_path_runnable(script_path):
        raise AgentNotFound(agent_name)

    output, retval = runner.run(
        [script_path, "meta-data"],
        env_extend={"OCF_ROOT": settings.ocf_root},
        ignore_stderr=True
    )

    if output.strip() == "":
        raise UnableToGetAgentMetadata(agent_name, output)

    try:
        return etree.fromstring(output)
    except etree.XMLSyntaxError as e:
        raise UnableToGetAgentMetadata(agent_name, str(e))


def get_agent_desc(metadata_dom):
    """
    Returns dictionary which contains description of agent from it's metadata.
    dictionary format:
    {
        longdesc: long description
        shortdesc: short description
    }
    Raises InvalidMetadataFormat if metadata_dom is not in valid format.

    metadata_dom -- metadata dom of agent
    """
    if metadata_dom.tag != "resource-agent":
        raise InvalidMetadataFormat()

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
    # we don't allow user to change these options, they are intended
    # to be used interactively (command line), there is no point setting them
    banned_parameters = ["debug", "verbose", "version", "help"]
    # but still, we have to let user change 'action' because of backward
    # compatibility, just marking it as not required
    for param in parameters:
        if param["name"] == "action":
            param["shortdesc"] = param.get("shortdesc", "") + "\nWARNING: " +\
                "specifying 'action' is deprecated and not necessary with " +\
                "current Pacemaker versions"
            param["required"] = False
    return [
        param for param in parameters if param["name"] not in banned_parameters
    ]


def get_fence_agent_parameters(runner, metadata_dom):
    """
    Returns complete list of parameters for fence agent from it's metadata.

    runner -- CommandRunner
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
    Raises UnsupportedResourceAgent if specified agent is not ocf or nagios
        agent.

    runner -- CommandRunner
    agent -- agent name
    """
    error = UnsupportedResourceAgent(agent)
    if agent.startswith("ocf:"):
        agent_info = agent.split(":", 2)
        if len(agent_info) != 3:
            raise error
        return _get_ocf_resource_agent_metadata(runner, *agent_info[1:])
    elif agent.startswith("nagios:"):
        return _get_nagios_resource_agent_metadata(agent.split("nagios:", 1)[1])
    else:
        raise error


def _get_action(action_el):
    """
    Returns XML action element as dictionary, where all elements attributes
    are key of dict
    Raises InvalidMetadataFormat if action_el is not in valid format.

    action_el -- action lxml.etree element
    """
    if action_el.tag != "action" or action_el.get("name") is None:
        raise InvalidMetadataFormat()

    return dict(action_el.items())


def get_agent_actions(metadata_dom):
    """
    Returns list of actions from agents metadata
    Raises InvalidMetadataFormat if metadata_dom is not in valid format.

    metadata_dom -- agent's metadata dom
    """
    if metadata_dom.tag != "resource-agent":
        raise InvalidMetadataFormat()

    actions_el = metadata_dom.find("actions")
    if actions_el is None:
        return []

    return [
        _get_action(action) for action in actions_el.iter("action")
    ]


def _validate_instance_attributes(agent_params, attrs):
    valid_attrs = [attr["name"] for attr in agent_params]
    required_missing = []

    for attr in agent_params:
        if attr["required"] and attr["name"] not in attrs:
            required_missing.append(attr["name"])

    return [attr for attr in attrs if attr not in valid_attrs], required_missing


def validate_instance_attributes(runner, instance_attrs, agent):
    """
    Validates instance attributes according to specified agent.
    Returns tuple of lists (<invalid attributes>, <missing required attributes>)

    runner -- CommandRunner
    instance_attrs -- dictionary of instance attributes, where key is
        attribute name and value is attribute value
    agent -- full name (<class>:<agent> or <class>:<provider>:<agent>)
        of resource/fence agent
    """
    if agent.startswith("stonith:"):
        agent_params = get_fence_agent_parameters(
            runner,
            get_fence_agent_metadata(runner, agent.split("stonith:", 1)[1])
        )
        bad_attrs, missing_required = _validate_instance_attributes(
            agent_params, instance_attrs
        )
        if "port" in missing_required:
            # Temporarily make "port" an optional parameter. Once we are
            # getting metadata from pacemaker, this will be reviewed and fixed.
            missing_required.remove("port")
        return bad_attrs, missing_required
    else:
        agent_params = get_resource_agent_parameters(
            get_resource_agent_metadata(runner, agent)
        )
        return _validate_instance_attributes(agent_params, instance_attrs)


def resource_agent_lib_error_to_report_item(
    e, severity=ReportItemSeverity.ERROR, forceable=False
):
    """
    Transform ResourceAgentLibError to ReportItem
    """
    force = None
    if e.__class__ == AgentNotFound:
        if severity == ReportItemSeverity.ERROR and forceable:
            force = report_codes.FORCE_UNKNOWN_AGENT
        return reports.agent_not_found(e.agent, severity, force)
    if e.__class__ == UnsupportedResourceAgent:
        if severity == ReportItemSeverity.ERROR and forceable:
            force = report_codes.FORCE_UNSUPPORTED_AGENT
        return reports.agent_not_supported(e.agent, severity, force)
    if e.__class__ == UnableToGetAgentMetadata:
        if severity == ReportItemSeverity.ERROR and forceable:
            force = report_codes.FORCE_METADATA_ISSUE
        return reports.unable_to_get_agent_metadata(
            e.agent, e.message, severity, force
        )
    if e.__class__ == InvalidMetadataFormat:
        if severity == ReportItemSeverity.ERROR and forceable:
            force = report_codes.FORCE_METADATA_ISSUE
        return reports.invalid_metadata_format(severity, force)
    if e.__class__ == ResourceAgentCommonError:
        return reports.resource_agent_general_error(e.agent)
    if e.__class__ == ResourceAgentLibError:
        return reports.resource_agent_general_error()
    raise e
