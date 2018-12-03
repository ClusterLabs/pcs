from __future__ import (
    absolute_import,
    division,
    print_function,
)

from collections import namedtuple
from lxml import etree
import re

from pcs import settings
from pcs.common import report_codes
from pcs.common.tools import xml_fromstring
from pcs.lib import reports
from pcs.lib.errors import LibraryError, ReportItemSeverity
from pcs.lib.pacemaker.values import is_true


# Operation monitor is required always! No matter if --no-default-ops was
# entered or if agent does not specify it. See
# http://clusterlabs.org/doc/en-US/Pacemaker/1.1-pcs/html-single/Pacemaker_Explained/index.html#_resource_operations
NECESSARY_CIB_ACTION_NAMES = ["monitor"]

#These are all standards valid in cib. To get a list of standards supported by
#pacemaker in local environment use result of "pcs resource standards".
STANDARD_LIST = [
    "ocf",
    "lsb",
    "heartbeat",
    "stonith",
    "upstart",
    "service",
    "systemd",
    "nagios",
]

DEFAULT_INTERVALS = {
    "monitor": "60s"
}

_STONITH_ACTION_REPLACED_BY = ("pcmk_off_action", "pcmk_reboot_action")


def get_default_interval(operation_name):
    """
    Return default interval for given operation_name.
    string operation_name
    """
    return DEFAULT_INTERVALS.get(operation_name, "0s")

def complete_all_intervals(raw_operation_list):
    """
    Return operation_list based on raw_operation_list where each item has key
    "interval".

    list of dict raw_operation_list can include items withou key "interval".
    """
    operation_list = []
    for raw_operation in raw_operation_list:
        operation = raw_operation.copy()
        if "interval" not in operation:
            operation["interval"] = get_default_interval(operation["name"])
        operation_list.append(operation)
    return operation_list

class ResourceAgentError(Exception):
    # pylint: disable=super-init-not-called
    def __init__(self, agent, message=""):
        self.agent = agent
        self.message = message


class UnableToGetAgentMetadata(ResourceAgentError):
    pass

class InvalidResourceAgentName(ResourceAgentError):
    pass

class InvalidStonithAgentName(ResourceAgentError):
    pass

class ResourceAgentName(
    namedtuple("ResourceAgentName", "standard provider type")
):
    @property
    def full_name(self):
        return ":".join(
            filter(
                None,
                [self.standard, self.provider, self.type]
            )
        )

def get_resource_agent_name_from_string(full_agent_name):
    #full_agent_name could be for example systemd:lvm2-pvscan@252:2
    #note that the second colon is not separator of provider and type
    match = re.match(
        "^(?P<standard>systemd|service):(?P<agent_type>[^:@]+@.*)$",
        full_agent_name
    )
    if match:
        return ResourceAgentName(
            match.group("standard"),
            None,
            match.group("agent_type")
        )

    match = re.match(
        "^(?P<standard>[^:]+)(:(?P<provider>[^:]+))?:(?P<type>[^:]+)$",
        full_agent_name
    )
    if not match:
        raise InvalidResourceAgentName(full_agent_name)

    standard = match.group("standard")
    provider = match.group("provider") if match.group("provider") else None
    agent_type = match.group("type")

    if standard not in STANDARD_LIST:
        raise InvalidResourceAgentName(full_agent_name)

    if standard == "ocf" and not provider:
        raise InvalidResourceAgentName(full_agent_name)

    if standard != "ocf" and provider:
        raise InvalidResourceAgentName(full_agent_name)

    return ResourceAgentName(standard, provider, agent_type)

def list_resource_agents_standards(runner):
    """
    Return list of resource agents standards (ocf, lsb, ... ) on the local host
    CommandRunner runner
    """
    # retval is number of standards found
    stdout, dummy_stderr, dummy_retval = runner.run([
        settings.crm_resource_binary, "--list-standards"
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
        settings.crm_resource_binary, "--list-ocf-providers"
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
        settings.crm_resource_binary, "--list-agents", standard_provider
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
        settings.crm_resource_binary, "--list-agents", "stonith"
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
    report_processor, runner, name,
    allowed_absent=False, absent_agent_supported=True
):
    """
    Return instance of ResourceAgent corresponding to name

    report_processor is tool for warning/info/error reporting
    runner is tool for launching external commands
    string name specifies a searched agent
    bool absent_agent_supported flag decides if is possible to allow to return
        absent agent: if is produced forceable/no-forcable error
    """
    if ":" not in name:
        agent = guess_exactly_one_resource_agent_full_name(runner, name)
        report_processor.process(
            reports.agent_name_guessed(name, agent.get_name())
        )
        return agent

    return _find_valid_agent_by_name(
        report_processor,
        runner,
        name,
        ResourceAgent,
        AbsentResourceAgent if allowed_absent else None,
        absent_agent_supported=absent_agent_supported,
    )

def find_valid_stonith_agent_by_name(
    report_processor, runner, name,
    allowed_absent=False, absent_agent_supported=True
):
    return _find_valid_agent_by_name(
        report_processor,
        runner,
        name,
        StonithAgent,
        AbsentStonithAgent if allowed_absent else None,
        absent_agent_supported=absent_agent_supported,
    )

def _find_valid_agent_by_name(
    report_processor, runner, name, PresentAgentClass, AbsentAgentClass,
    absent_agent_supported=True
):
    try:
        return PresentAgentClass(runner, name).validate_metadata()
    except (InvalidResourceAgentName, InvalidStonithAgentName) as e:
        raise LibraryError(resource_agent_error_to_report_item(e))
    except UnableToGetAgentMetadata as e:
        if not absent_agent_supported:
            raise LibraryError(resource_agent_error_to_report_item(e))

        if not AbsentAgentClass:
            raise LibraryError(resource_agent_error_to_report_item(
                    e,
                    forceable=True
            ))

        report_processor.process(resource_agent_error_to_report_item(
            e,
            severity=ReportItemSeverity.WARNING,
        ))

        return AbsentAgentClass(runner, name)

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
        agent_info["default_actions"] = self.get_cib_default_actions()
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
        param_list = []
        for param_el in params_element.iter("parameter"):
            param = self._get_parameter(param_el)
            if not param["obsoletes"]:
                param_list.append(param)
        return param_list


    def _get_parameter(self, parameter_element):
        value_type = "string"
        default_value = None
        content_element = parameter_element.find("content")
        if content_element is not None:
            value_type = content_element.get("type", value_type)
            default_value = content_element.get("default", default_value)

        return self._create_parameter({
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
            "deprecated": is_true(parameter_element.get("deprecated", "0")),
            "obsoletes": parameter_element.get("obsoletes", None),
            "unique": is_true(parameter_element.get("unique", "0")),
        })

    def _get_always_allowed_parameters(self):
        """
        This method should be overriden in descendants.

        Returns set of always allowed parameters of a agent.
        """
        return set()

    def validate_parameters(
        self, parameters,
        parameters_type="resource",
        allow_invalid=False,
        update=False
    ):
        forceable = report_codes.FORCE_OPTIONS if not allow_invalid else None
        severity = (
            ReportItemSeverity.ERROR if not allow_invalid
            else ReportItemSeverity.WARNING
        )

        report_list = []
        bad_opts, missing_req_opts = self.validate_parameters_values(
            parameters
        )

        if bad_opts:
            report_list.append(reports.invalid_options(
                bad_opts,
                sorted([attr["name"] for attr in self.get_parameters()]),
                parameters_type,
                severity=severity,
                forceable=forceable,
            ))

        if not update and missing_req_opts:
            report_list.append(reports.required_option_is_missing(
                missing_req_opts,
                parameters_type,
                severity=severity,
                forceable=forceable,
            ))

        return report_list

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
        always_allowed = self._get_always_allowed_parameters()
        for attr in agent_params:
            if attr["required"] and attr["name"] not in parameters_values:
                required_missing.append(attr["name"])

        valid_attrs = [attr["name"] for attr in agent_params]
        return (
            [
                attr for attr in parameters_values
                if attr not in valid_attrs and attr not in always_allowed
            ],
            required_missing
        )

    def _get_raw_actions(self):
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

    def get_actions(self):
        """
        Get list of agent's actions (operations). Each action is represented as
        a dict. Example: [{"name": "monitor", "timeout": 20, "interval": 10}]
        """
        action_list = []
        for raw_action in self._get_raw_actions():
            action = {}
            for key, value in raw_action.items():
                if key != "depth":
                    action[key] = value
                elif value != "0":
                    action["OCF_CHECK_LEVEL"] = value
            action_list.append(action)
        return action_list

    def _is_cib_default_action(self, action):
        return False

    def get_cib_default_actions(self, necessary_only=False):
        """
        List actions that should be put to resource on its creation.
        Note that every action has at least attribute name.
        """

        action_list = [
            action for action in self.get_actions()
            if (
                    necessary_only
                    and
                    action.get("name") in NECESSARY_CIB_ACTION_NAMES
                )
                or
                (
                    not necessary_only
                    and
                    self._is_cib_default_action(action)
                )
        ]

        for action_name in NECESSARY_CIB_ACTION_NAMES:
            if action_name not in [action["name"] for action in action_list]:
                action_list.append({"name": action_name})

        return complete_all_intervals(action_list)

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
            dom = xml_fromstring(metadata)
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

    def _create_parameter(self, properties):
        new_param = {
            "name": "",
            "longdesc": "",
            "shortdesc": "",
            "type": "string",
            "default": None,
            "required": False,
            "advanced": False,
            "deprecated": False,
            "obsoletes": None,
            "pcs_deprecated_warning": "",
            "unique": False,
        }
        new_param.update(properties)
        return new_param


class FakeAgentMetadata(Agent):
    #pylint:disable=abstract-method
    pass


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
    #pylint:disable=abstract-method
    def __init__(self, runner, name):
        """
        init
        CommandRunner runner
        """
        super(CrmAgent, self).__init__(runner)
        self._name_parts = self._prepare_name_parts(name)

    def _prepare_name_parts(self, name):
        raise NotImplementedError()

    def _get_full_name(self):
        return self._name_parts.full_name

    def get_standard(self):
        return self._name_parts.standard

    def get_provider(self):
        return self._name_parts.provider

    def get_type(self):
        return self._name_parts.type

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
            [
                settings.crm_resource_binary,
                "--show-metadata",
                self._get_full_name(),
            ],
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
    def _prepare_name_parts(self, name):
        return get_resource_agent_name_from_string(name)

    def get_name(self):
        return self._get_full_name()

    def get_parameters(self):
        parameters = super(ResourceAgent, self).get_parameters()
        if (
            self.get_standard() == "ocf"
            and
            (self.get_provider() in ("heartbeat", "pacemaker"))
        ):
            trace_ra_found = False
            trace_file_found = False
            for param in parameters:
                param_name = param["name"].lower()
                if param_name == "trace_ra":
                    trace_ra_found = True
                if param_name == "trace_file":
                    trace_file_found = True
                if trace_file_found and trace_ra_found:
                    break

            if not trace_ra_found:
                shortdesc = (
                    "Set to 1 to turn on resource agent tracing"
                    " (expect large output)"
                )
                parameters.append(self._create_parameter({
                    "name": "trace_ra",
                    "longdesc": (
                        shortdesc
                        +
                        " The trace output will be saved to trace_file, if set,"
                        " or by default to"
                        " $HA_VARRUN/ra_trace/<type>/<id>.<action>.<timestamp>"
                        " e.g. $HA_VARRUN/ra_trace/oracle/"
                        "db.start.2012-11-27.08:37:08"
                    ),
                    "shortdesc": shortdesc,
                    "type": "integer",
                    "default": 0,
                    "required": False,
                    "advanced": True,
                }))
            if not trace_file_found:
                shortdesc = (
                    "Path to a file to store resource agent tracing log"
                )
                parameters.append(self._create_parameter({
                    "name": "trace_file",
                    "longdesc": shortdesc,
                    "shortdesc": shortdesc,
                    "type": "string",
                    "default": "",
                    "required": False,
                    "advanced": True,
                }))

        return parameters

    def _is_cib_default_action(self, action):
        # Copy all actions to the CIB even those not defined in the OCF standard
        # or pacemaker. This way even custom actions defined in a resource agent
        # will be copied to the CIB and run by pacemaker if they specify
        # an interval. See https://github.com/ClusterLabs/pcs/issues/132
        return action.get("name") not in [
            # one-time action, not meant to be processed by pacemaker
            "meta-data",
            # deprecated alias of monitor
            "status",
            # one-time action, not meant to be processed by pacemaker
            "validate-all",
        ]


class AbsentAgentMixin(object):
    def _load_metadata(self):
        return "<resource-agent/>"

    def validate_parameters_values(self, parameters_values):
        return ([], [])


class AbsentResourceAgent(AbsentAgentMixin, ResourceAgent):
    pass


class StonithAgent(CrmAgent):
    """
    Provides convinient access to a stonith agent's metadata
    """
    _stonithd_metadata = None

    @classmethod
    def clear_stonithd_metadata_cache(cls):
        cls._stonithd_metadata = None

    def _prepare_name_parts(self, name):
        # pacemaker doesn't support stonith (nor resource) agents with : in type
        if ":" in name:
            raise InvalidStonithAgentName(name)
        return ResourceAgentName("stonith", None, name)

    def get_name(self):
        return self.get_type()

    def get_parameters(self):
        return (
            self._filter_parameters(
                super(StonithAgent, self).get_parameters()
            )
            +
            self._get_stonithd_metadata().get_parameters()
        )

    def _get_always_allowed_parameters(self):
        if self.get_name() in ("fence_compute", "fence_evacuate"):
            return set([
                "project-domain", "project_domain", "user-domain",
                "user_domain", "compute-domain", "compute_domain",
            ])
        return set()

    def validate_parameters(
        self, parameters,
        parameters_type="stonith",
        allow_invalid=False,
        update=False
    ):
        report_list = super(StonithAgent, self).validate_parameters(
            parameters,
            parameters_type=parameters_type,
            allow_invalid=allow_invalid,
            update=update
        )
        if parameters.get("action", ""):
            report_list.append(reports.deprecated_option(
                "action",
                _STONITH_ACTION_REPLACED_BY,
                parameters_type,
                severity=(
                    ReportItemSeverity.ERROR if not allow_invalid
                    else ReportItemSeverity.WARNING
                ),
                forceable=(
                    report_codes.FORCE_OPTIONS if not allow_invalid else None
                )
            ))
        return report_list

    def _filter_parameters(self, parameters):
        """
        Remove parameters that should not be available to the user.
        """
        # We don't allow the user to change these options which are only
        # intended to be used interactively on command line.
        remove_parameters = frozenset([
            "help",
            "version",
        ])
        filtered = []
        for param in parameters:
            if param["name"] in remove_parameters:
                continue
            elif param["name"] == "action":
                # However we still need the user to be able to set 'action' due
                # to backward compatibility reasons. So we just mark it as not
                # required. We also move it to advanced params to indicate users
                # should not set it in most cases.
                new_param = dict(param)
                new_param["required"] = False
                new_param["advanced"] = True
                new_param["pcs_deprecated_warning"] = (
                    "Specifying 'action' is deprecated and not necessary with"
                        " current Pacemaker versions. Use {0} instead."
                ).format(
                    ", ".join(
                        ["'{0}'".format(x) for x in _STONITH_ACTION_REPLACED_BY]
                    )
                )
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

    def get_provides_unfencing(self):
        # self.get_actions returns an empty list
        for action in self._get_raw_actions():
            if (
                action.get("name", "") == "on"
                and
                action.get("on_target", "0") == "1"
                and
                action.get("automatic", "0") == "1"
            ):
                return True
        return False

    def _is_cib_default_action(self, action):
        return action.get("name") == "monitor"


class AbsentStonithAgent(AbsentAgentMixin, StonithAgent):
    def get_parameters(self):
        return []


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
    if e.__class__ == InvalidStonithAgentName:
        return reports.invalid_stonith_agent_name(e.agent)
    raise e
