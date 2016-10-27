from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os
import re
from lxml import etree

from pcs import settings
from pcs.lib import reports
from pcs.lib.errors import LibraryError, ReportItemSeverity
from pcs.lib.pacemaker_values import is_true
from pcs.common import report_codes


_crm_resource = os.path.join(settings.pacemaker_binaries, "crm_resource")


class ResourceAgentError(Exception):
    # pylint: disable=super-init-not-called
    def __init__(self, agent, message=""):
        self.agent = agent
        self.message = message


class UnableToGetAgentMetadata(ResourceAgentError):
    pass

class InvalidResourceAgentName(ResourceAgentError):
    pass


def list_resource_agents_standards(runner):
    """
    Return list of resource agents standards (ocf, lsb, ... ) on the local host
    CommandRunner runner
    """
    # retval is number of standards found
    stdout, dummy_stderr, dummy_retval = runner.run([
        _crm_resource, "--list-standards"
    ])
    ignored_standards = frozenset([
        # we are only interested in RESOURCE agents
        "stonith",
    ])
    return _prepare_agent_list(stdout, ignored_standards)


def list_resource_agents_ocf_providers(runner):
    """
    Return list of resource agents ocf providers on the local host
    CommandRunner runner
    """
    # retval is number of providers found
    stdout, dummy_stderr, dummy_retval = runner.run([
        _crm_resource, "--list-ocf-providers"
    ])
    return _prepare_agent_list(stdout)


def list_resource_agents_standards_and_providers(runner):
    """
    Return list of all standard[:provider] on the local host
    CommandRunner runner
    """
    standards = (
        list_resource_agents_standards(runner)
        +
        [
            "ocf:{0}".format(provider)
            for provider in list_resource_agents_ocf_providers(runner)
        ]
    )
    # do not list ocf resources twice
    try:
        standards.remove("ocf")
    except ValueError:
        pass
    return sorted(
        standards,
        # works with both str and unicode in both python 2 and 3
        key=lambda x: x.lower()
    )


def list_resource_agents(runner, standard_provider):
    """
    Return list of resource agents for specified standard on the local host
    CommandRunner runner
    string standard_provider standard[:provider], e.g. lsb, ocf, ocf:pacemaker
    """
    # retval is 0 on success, anything else when no agents found
    stdout, dummy_stderr, retval = runner.run([
        _crm_resource, "--list-agents", standard_provider
    ])
    if retval != 0:
        return []
    return _prepare_agent_list(stdout)


def list_stonith_agents(runner):
    """
    Return list of fence agents on the local host
    CommandRunner runner
    """
    # retval is 0 on success, anything else when no agents found
    stdout, dummy_stderr, retval = runner.run([
        _crm_resource, "--list-agents", "stonith"
    ])
    if retval != 0:
        return []
    ignored_agents = frozenset([
        "fence_ack_manual",
        "fence_check",
        "fence_kdump_send",
        "fence_legacy",
        "fence_na",
        "fence_node",
        "fence_nss_wrapper",
        "fence_pcmk",
        "fence_sanlockd",
        "fence_tool",
        "fence_virtd",
        "fence_vmware_helper",
    ])
    return _prepare_agent_list(stdout, ignored_agents)


def _prepare_agent_list(agents_string, filter_list=None):
    ignored = frozenset(filter_list) if filter_list else frozenset([])
    result = [
        name
        for name in [line.strip() for line in agents_string.splitlines()]
        if name and name not in ignored
    ]
    return sorted(
        result,
        # works with both str and unicode in both python 2 and 3
        key=lambda x: x.lower()
    )


def guess_resource_agent_full_name(runner, search_agent_name):
    """
    List resource agents matching specified search term
    string search_agent_name part of full agent name
    """
    search_lower = search_agent_name.lower()
    # list all possible names
    possible_names = []
    for std in list_resource_agents_standards_and_providers(runner):
        for agent in list_resource_agents(runner, std):
            if search_lower == agent.lower():
                possible_names.append("{0}:{1}".format(std, agent))
    # construct agent wrappers
    agent_candidates = [
        ResourceAgent(runner, agent) for agent in possible_names
    ]
    # check if the agent is valid
    return [
        agent for agent in agent_candidates if agent.is_valid_metadata()
    ]


def guess_exactly_one_resource_agent_full_name(runner, search_agent_name):
    """
    Get one resource agent matching specified search term
    string search_agent_name last part of full agent name
    Raise LibraryError if zero or more than one agents found
    """
    agents = guess_resource_agent_full_name(runner, search_agent_name)
    if not agents:
        raise LibraryError(
            reports.agent_name_guess_found_none(search_agent_name)
        )
    if len(agents) > 1:
        raise LibraryError(
            reports.agent_name_guess_found_more_than_one(
                search_agent_name,
                [agent.get_name() for agent in agents]
            )
        )
    return agents[0]

def find_valid_resource_agent_by_name(
    report_processor, runner, name, allowed_absent=False
):
    if ":" not in name:
        agent = guess_exactly_one_resource_agent_full_name(runner, name)
        report_processor.process(
            reports.agent_name_guessed(name, agent.get_name())
        )
        return agent

    try:
        return ResourceAgent(runner, name).validate_metadata()
    except InvalidResourceAgentName as e:
        raise LibraryError(resource_agent_error_to_report_item(e))
    except UnableToGetAgentMetadata as e:
        if not allowed_absent:
            raise LibraryError(resource_agent_error_to_report_item(e))

        report_processor.process(resource_agent_error_to_report_item(
            e,
            severity=ReportItemSeverity.WARNING,
            forceable=True
        ))

        return AbsentResourceAgent(runner, name)

class Agent(object):
    """
    Base class for providing convinient access to an agent's metadata
    """
    def __init__(self, runner):
        """
        create an instance which reads metadata by itself on demand
        CommandRunner runner
        """
        self._runner = runner
        self._metadata = None


    def get_name(self):
        raise NotImplementedError()


    def get_name_info(self):
        """
        Get structured agent's info, only name is populated
        """
        return {
            "name": self.get_name(),
            "shortdesc":"",
            "longdesc": "",
            "parameters": [],
            "actions": [],
        }


    def get_description_info(self):
        """
        Get structured agent's info, only name and description is populated
        """
        agent_info = self.get_name_info()
        agent_info["shortdesc"] = self.get_shortdesc()
        agent_info["longdesc"] = self.get_longdesc()
        return agent_info


    def get_full_info(self):
        """
        Get structured agent's info, all items are populated
        """
        agent_info = self.get_description_info()
        agent_info["parameters"] = self.get_parameters()
        agent_info["actions"] = self.get_actions()
        return agent_info


    def get_shortdesc(self):
        """
        Get a short description of agent's purpose
        """
        return (
            self._get_text_from_dom_element(
                self._get_metadata().find("shortdesc")
            )
            or
            self._get_metadata().get("shortdesc", "")
        )


    def get_longdesc(self):
        """
        Get a long description of agent's purpose
        """
        return self._get_text_from_dom_element(
            self._get_metadata().find("longdesc")
        )


    def get_parameters(self):
        """
        Get list of agent's parameters, each parameter is described by dict:
        {
            name: name of parameter
            longdesc: long description,
            shortdesc: short description,
            type: data type od parameter,
            default: default value,
            required: True if is required parameter, False otherwise
        }
        """
        params_element = self._get_metadata().find("parameters")
        if params_element is None:
            return []
        return [
            self._get_parameter(parameter)
            for parameter in params_element.iter("parameter")
        ]


    def _get_parameter(self, parameter_element):
        value_type = "string"
        default_value = None
        content_element = parameter_element.find("content")
        if content_element is not None:
            value_type = content_element.get("type", value_type)
            default_value = content_element.get("default", default_value)

        return {
            "name": parameter_element.get("name", ""),
            "longdesc": self._get_text_from_dom_element(
                parameter_element.find("longdesc")
            ),
            "shortdesc": self._get_text_from_dom_element(
                parameter_element.find("shortdesc")
            ),
            "type": value_type,
            "default": default_value,
            "required": is_true(parameter_element.get("required", "0")),
            "advanced": False,
        }


    def validate_parameters_values(self, parameters_values):
        """
        Return tuple of lists (<invalid attributes>, <missing required attributes>)
        dict parameters_values key is attribute name and value is attribute value
        """
        # TODO Add value and type checking (e.g. if parameter["type"] is
        # integer, its value cannot be "abc"). This most probably will require
        # redefining the format of the return value and rewriting the whole
        # function, which will only be good. For now we just stick to the
        # original legacy code.
        agent_params = self.get_parameters()

        required_missing = []
        for attr in agent_params:
            if attr["required"] and attr["name"] not in parameters_values:
                required_missing.append(attr["name"])

        valid_attrs = [attr["name"] for attr in agent_params]
        return (
            [attr for attr in parameters_values if attr not in valid_attrs],
            required_missing
        )


    def get_actions(self):
        """
        Get list of agent's actions (operations)
        """
        actions_element = self._get_metadata().find("actions")
        if actions_element is None:
            return []
        # TODO Resulting dict should contain all keys defined for an action.
        # But we do not know what are those, because the metadata xml schema is
        # outdated and doesn't describe current agents' metadata xml.
        return [
            dict(action.items())
            for action in actions_element.iter("action")
        ]


    def _get_metadata(self):
        """
        Return metadata DOM
        Raise UnableToGetAgentMetadata if agent doesn't exist or unable to get
            or parse its metadata
        """
        if self._metadata is None:
            self._metadata = self._parse_metadata(self._load_metadata())
        return self._metadata


    def _load_metadata(self):
        raise NotImplementedError()


    def _parse_metadata(self, metadata):
        try:
            dom = etree.fromstring(metadata)
            # TODO Majority of agents don't provide valid metadata, so we skip
            # the validation for now. We want to enable it once the schema
            # and/or agents are fixed.
            # When enabling this check for overrides in child classes.
            #if os.path.isfile(settings.agent_metadata_schema):
            #    etree.DTD(file=settings.agent_metadata_schema).assertValid(dom)
            return dom
        except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
            raise UnableToGetAgentMetadata(self.get_name(), str(e))


    def _get_text_from_dom_element(self, element):
        if element is None or element.text is None:
            return ""
        return element.text.strip()


class FakeAgentMetadata(Agent):
    def get_name(self):
        raise NotImplementedError()


    def _load_metadata(self):
        raise NotImplementedError()


class StonithdMetadata(FakeAgentMetadata):
    def get_name(self):
        return "stonithd"


    def _get_parameter(self, parameter_element):
        parameter = super(StonithdMetadata, self)._get_parameter(
            parameter_element
        )
        # Metadata are written in such a way that a longdesc text is a
        # continuation of a shortdesc text.
        parameter["longdesc"] = "{0}\n{1}".format(
            parameter["shortdesc"],
            parameter["longdesc"]
        ).strip()
        parameter["advanced"] = parameter["shortdesc"].startswith(
            "Advanced use only"
        )
        return parameter


    def _load_metadata(self):
        stdout, stderr, dummy_retval = self._runner.run(
            [settings.stonithd_binary, "metadata"]
        )
        metadata = stdout.strip()
        if not metadata:
            raise UnableToGetAgentMetadata(self.get_name(), stderr.strip())
        return metadata


class CrmAgent(Agent):
    def __init__(self, runner, full_agent_name):
        """
        init
        CommandRunner runner
        string full_agent_name standard:provider:type or standard:type
        """
        super(CrmAgent, self).__init__(runner)
        self._full_agent_name = full_agent_name


    def get_name(self):
        return self._full_agent_name


    def is_valid_metadata(self):
        """
        If we are able to get metadata, we consider the agent existing and valid
        """
        # if the agent is valid, we do not need to load its metadata again
        try:
            self._get_metadata()
        except UnableToGetAgentMetadata:
            return False
        return True

    def validate_metadata(self):
        """
        Validate metadata by attepmt to retrieve it.
        """
        self._get_metadata()
        return self

    def _load_metadata(self):
        env_path = ":".join([
            # otherwise pacemaker cannot run RHEL fence agents to get their
            # metadata
            settings.fence_agent_binaries,
            # otherwise heartbeat and cluster-glue agents don't work
            "/bin/",
            # otherwise heartbeat and cluster-glue agents don't work
            "/usr/bin/",
        ])
        stdout, stderr, retval = self._runner.run(
            [_crm_resource, "--show-metadata", self._full_agent_name],
            env_extend={
                "PATH": env_path,
            }
        )
        if retval != 0:
            raise UnableToGetAgentMetadata(self.get_name(), stderr.strip())
        return stdout.strip()


class ResourceAgent(CrmAgent):
    """
    Provides convinient access to a resource agent's metadata
    """
    def __init__(self, runner, full_agent_name):
        if not re.match("^[^:]+(:[^:]+){1,2}$", full_agent_name):
            raise InvalidResourceAgentName(full_agent_name)
        super(ResourceAgent, self).__init__(runner, full_agent_name)

class AbsentResourceAgent(ResourceAgent):
    def _load_metadata(self):
        return "<resource-agent/>"

    def validate_parameters_values(self, parameters_values):
        return ([], [])

class StonithAgent(CrmAgent):
    """
    Provides convinient access to a stonith agent's metadata
    """

    _stonithd_metadata = None


    def __init__(self, runner, agent_name):
        super(StonithAgent, self).__init__(
            runner,
            "stonith:{0}".format(agent_name)
        )
        self._agent_name = agent_name


    def get_name(self):
        return self._agent_name


    def get_parameters(self):
        return (
            self._filter_parameters(
                super(StonithAgent, self).get_parameters()
            )
            +
            self._get_stonithd_metadata().get_parameters()
        )


    def _filter_parameters(self, parameters):
        """
        Remove parameters that should not be available to the user.
        """
        # We don't allow the user to change these options which are only
        # intended to be used interactively on command line.
        remove_parameters = frozenset([
            "debug",
            "help",
            "verbose",
            "version",
        ])
        filtered = []
        for param in parameters:
            if param["name"] in remove_parameters:
                continue
            elif param["name"] == "action":
                # However we still need the user to be able to set 'action' due
                # to backward compatibility reasons. So we just mark it as not
                # required.
                new_param = dict(param)
                new_param["shortdesc"] = "\n".join(filter(None, [
                    param.get("shortdesc", ""),
                    "WARNING: specifying 'action' is deprecated and not "
                        "necessary with current Pacemaker versions."
                    ,
                ]))
                new_param["required"] = False
                filtered.append(new_param)
            else:
                filtered.append(param)
            # 'port' parameter is required by a fence agent, but it is filled
            # automatically by pacemaker based on 'pcmk_host_map' or
            # 'pcmk_host_list' parameter (defined in stonithd metadata).
            # Pacemaker marks the 'port' parameter as not required for us.
        return filtered


    def _get_stonithd_metadata(self):
        if not self.__class__._stonithd_metadata:
            self.__class__._stonithd_metadata = StonithdMetadata(self._runner)
        return self.__class__._stonithd_metadata


    def get_actions(self):
        # In previous versions of pcs there was no way to read actions from
        # stonith agents, the functions always returned an empty list. It
        # wasn't clear if that is a mistake or an intention. We keep it that
        # way for two reasons:
        # 1) Fence agents themselfs specify the actions without any attributes
        # (interval, timeout)
        # 2) Pacemaker explained shows an example stonith agent configuration
        # in CIB with only monitor operation specified (and that pcs creates
        # automatically in "pcs stonith create" regardless of provided actions
        # from here).
        # It may be better to return real actions from this class and deal ommit
        # them in higher layers, which can decide if the actions are desired or
        # not. For now there is not enough information to do that. Code which
        # uses this is not clean enough. Once everything is cleaned we should
        # decide if it is better to move this to higher level.
        return []


    def get_provides_unfencing(self):
        # self.get_actions returns an empty list
        for action in super(StonithAgent, self).get_actions():
            if (
                action.get("name", "") == "on"
                and
                action.get("on_target", "0") == "1"
                and
                action.get("automatic", "0") == "1"
            ):
                return True
        return False


def resource_agent_error_to_report_item(
    e, severity=ReportItemSeverity.ERROR, forceable=False
):
    """
    Transform ResourceAgentError to ReportItem
    """
    force = None
    if e.__class__ == UnableToGetAgentMetadata:
        if severity == ReportItemSeverity.ERROR and forceable:
            force = report_codes.FORCE_METADATA_ISSUE
        return reports.unable_to_get_agent_metadata(
            e.agent, e.message, severity, force
        )
    if e.__class__ == InvalidResourceAgentName:
        return reports.invalid_resource_agent_name(e.agent)
    raise e
