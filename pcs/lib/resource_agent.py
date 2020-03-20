import re
from collections import namedtuple
from typing import cast
from lxml import etree

from pcs import settings
from pcs.common import reports
from pcs.common.reports import (
    ReportItem,
    ReportItemSeverity,
    ReportProcessor,
)
from pcs.common.tools import xml_fromstring
from pcs.lib import validate
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner
from pcs.lib.pacemaker.values import is_true

# TODO: fix
# pylint: disable=no-self-use

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

STONITH_ACTION_REPLACED_BY = ("pcmk_off_action", "pcmk_reboot_action")


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
            ReportItem.error(
                reports.messages.AgentNameGuessFoundNone(search_agent_name)
            )
        )
    if len(agents) > 1:
        raise LibraryError(
            ReportItem.error(
                reports.messages.AgentNameGuessFoundMoreThanOne(
                    search_agent_name,
                    [agent.get_name() for agent in agents]
                )
            )
        )
    return agents[0]

def find_valid_resource_agent_by_name(
    report_processor: ReportProcessor,
    runner: CommandRunner,
    name: str,
    allowed_absent=False,
    absent_agent_supported=True
):
    """
    Return instance of ResourceAgent corresponding to name

    report_processor -- tool for warning/info/error reporting
    runner -- tool for launching external commands
    name -- specifies a searched agent
    absent_agent_supported -- flag decides if is possible to allow to return
        absent agent: if is produced forceable/no-forcable error
    """
    if ":" not in name:
        agent = guess_exactly_one_resource_agent_full_name(runner, name)
        report_processor.report(
            ReportItem.info(
                reports.messages.AgentNameGuessed(name, agent.get_name())
            )
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
    report_processor: ReportProcessor,
    runner: CommandRunner,
    name,
    allowed_absent=False,
    absent_agent_supported=True,
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
    report_processor: ReportProcessor,
    runner: CommandRunner,
    name,
    PresentAgentClass,
    AbsentAgentClass,
    absent_agent_supported=True,
):
    # pylint: disable=invalid-name
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

        report_processor.report(
            resource_agent_error_to_report_item(
                e,
                severity=ReportItemSeverity.WARNING,
            )
        )

        return AbsentAgentClass(runner, name)

class Agent():
    """
    Base class for providing convinient access to an agent's metadata
    """
    _agent_type_label = "agent"

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
            name: name of the parameter
            longdesc: long description,
            shortdesc: short description,
            type: data type of the parameter,
            default: default value,
            required: True if it is a required parameter, False otherwise
            advanced: True if the parameter is considered for advanced users
            deprecated: True if it is a deprecated parameter, False otherwise
            deprecated_by: list of parameters deprecating this one
            obsoletes: name of a deprecated parameter obsoleted by this one
            unique: True if the parameter's value should be unique across same
                agent resources, False otherwise
            pcs_deprecated_warning: pcs originated warning
        }
        """
        params_element = self._get_metadata().find("parameters")
        if params_element is None:
            return []

        param_list = []
        deprecated_by_dict = {}
        for param_el in params_element.iter("parameter"):
            param = self._get_parameter(param_el)
            param_list.append(param)
            if param["obsoletes"]:
                obsoletes = param["obsoletes"]
                if not obsoletes in deprecated_by_dict:
                    deprecated_by_dict[obsoletes] = set()
                deprecated_by_dict[obsoletes].add(param["name"])

        for param in param_list:
            if param["name"] in deprecated_by_dict:
                param["deprecated_by"] = sorted(
                    deprecated_by_dict[param["name"]]
                )

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
            "deprecated": is_true(parameter_element.get("deprecated", "0")),
            "obsoletes": parameter_element.get("obsoletes", None),
            "unique": is_true(parameter_element.get("unique", "0")),
        })

    def _get_parameter_obsoleting_chains(self):
        """
        get a dict describing parameters obsoleting

        Each key is a parameter which obsoletes parameters but is not itself
        obsoleted by any other parameter. Values are lists of obsoleted
        parameters: the first one is obsoleted by the key, the second one is
        obsoleted by the first one and so on.
        """
        # In meta-data, each param can have 'obsoletes' attribute containing a
        # name of a single param obsoleted by the param in question. That means:
        # 1) a deprecated param can be obsoleted by more than one param
        # 2) a param can obsolete none or one param
        # 3) there may be a loop (A obsoletes B, B obsoletes A)
        # This info is crucial when dealing with obsoleting and deprecated
        # params and it is reflected in the following piece of code.

        # first, get simple obsoleting mapping
        new_old = {
            param["name"]: param["obsoletes"]
            for param in self.get_parameters()
            if param["obsoletes"]
        }

        chains = {}
        # for each param which is not obsoleted
        for new_param in new_old:
            # start a new chain
            deprecated_by_new = []
            current_new = new_param
            # while current parameter obsoletes anything
            while current_new in new_old:
                # get the obsoleted parameter
                old = new_old[current_new]
                # if there is a loop, break
                if old in deprecated_by_new or old == current_new:
                    break
                # add the obsoleted parameter to the chain
                deprecated_by_new.append(old)
                # check if the obsoleted parameter obsoletes anything
                current_new = old
            if deprecated_by_new:
                chains[new_param] = deprecated_by_new
        return chains

    def validate_parameters_create(
        self, parameters, force=False,
        # TODO remove this argument, see pcs.lib.cib.commands.remote_node.create
        # for details
        do_not_report_instance_attribute_server_exists=False
    ):
        # This is just a basic validation checking that required parameters are
        # set and all set parameters are known to an agent. Missing checks are:
        # 1. values checks - if a param is an integer, then "abc" is not valid
        # 2. warnings should be emitted when a deprecated param is set
        # 3. errors should be emitted when a deprecated parameter and a
        #    parameter obsoleting it are set at the same time
        # 4. possibly some other checks
        # All of these have been missing in pcs since ever (ad 1. agents have
        # never provided enough info for us to do such validations, ad 2. and
        # 3. there were no deprecated parameters before). The checks should be
        # implemented in agents themselves, so I'm not adding them now either.
        report_items = []

        # report unknown parameters
        report_items.extend(
            validate.NamesIn(
                {param["name"] for param in self.get_parameters()},
                option_type=self._agent_type_label,
                **validate.set_warning(reports.codes.FORCE_OPTIONS, force)
            ).validate(parameters)
        )
        # TODO remove this "if", see pcs.lib.cib.commands.remote_node.create
        # for details
        if do_not_report_instance_attribute_server_exists:
            for report_item in report_items:
                if (
                    isinstance(report_item, ReportItem)
                    and
                    isinstance(
                        report_item.message, reports.messages.InvalidOptions
                    )
                ):
                    report_msg = cast(
                        reports.messages.InvalidOptions, report_item.message
                    )
                    report_item.message = reports.messages.InvalidOptions(
                        report_msg.option_names,
                        sorted([
                            value for value in report_msg.allowed
                            if value != "server"
                        ]),
                        report_msg.option_type,
                        report_msg.allowed_patterns,
                    )

        # report missing required parameters
        missing_parameters = self._find_missing_required_parameters(
            parameters
        )
        if missing_parameters:
            report_items.append(
                ReportItem(
                    severity=self._validate_report_severity(force),
                    message=reports.messages.RequiredOptionsAreMissing(
                        sorted(missing_parameters),
                        self._agent_type_label,
                    ),
                )
            )

        return report_items

    def validate_parameters_update(
        self,
        current_parameters,
        new_parameters,
        force=False
    ):
        # This is just a basic validation checking that required parameters are
        # set and all set parameters are known to an agent. Missing checks are:
        # 1. values checks - if a param is an integer, then "abc" is not valid
        # 2. warnings should be emitted when a deprecated param is set
        # 3. errors should be emitted when a deprecated parameter and a
        #    parameter obsoleting it are set at the same time
        # 4. possibly some other checks
        # All of these have been missing in pcs since ever (ad 1. agents have
        # never provided enough info for us to do such validations, ad 2. and
        # 3. there were no deprecated parameters before). The checks should be
        # implemented in agents themselves, so I'm not adding them now either.
        report_items = []

        # get resulting set of agent's parameters
        final_parameters = dict(current_parameters)
        for name, value in new_parameters.items():
            if value:
                final_parameters[name] = value
            else:
                if name in final_parameters:
                    del final_parameters[name]

        # report unknown parameters
        report_items.extend(
            validate.NamesIn(
                {param["name"] for param in self.get_parameters()},
                option_type=self._agent_type_label,
                **validate.set_warning(reports.codes.FORCE_OPTIONS, force)
            ).validate(
                # Do not report unknown parameters already set in the CIB. They
                # have been reported already when the were added to the CIB.
                {
                    name: value for name, value in new_parameters.items()
                    if name not in current_parameters
                }
            )
        )

        # report missing or removed required parameters
        missing_parameters = self._find_missing_required_parameters(
            final_parameters
        )
        if missing_parameters:
            report_items.append(
                ReportItem(
                    severity=self._validate_report_severity(force),
                    message=reports.messages.RequiredOptionsAreMissing(
                        sorted(missing_parameters),
                        self._agent_type_label,
                    ),
                )
            )

        return report_items

    # TODO: remove
    @staticmethod
    def _validate_report_forcible_severity(force):
        forcible = reports.codes.FORCE_OPTIONS if not force else None
        severity = (
            ReportItemSeverity.ERROR if not force
            else ReportItemSeverity.WARNING
        )
        return forcible, severity

    @staticmethod
    def _validate_report_severity(
        force: bool
    ) -> reports.item.ReportItemSeverity:
        return reports.item.ReportItemSeverity(
            level=(
                ReportItemSeverity.WARNING if force
                else ReportItemSeverity.ERROR
            ),
            force_code=reports.codes.FORCE_OPTIONS if not force else None,
        )


    def _find_missing_required_parameters(self, parameters):
        missing_parameters = set()
        obsoleting_chains = self._get_parameter_obsoleting_chains()
        for param in self.get_parameters():
            if not param["required"] or param["deprecated_by"]:
                # non-required params are never required
                # we require non-deprecated params preferentially
                continue
            if param["name"] in parameters:
                # the param is not missing
                continue
            # the param is missing, maybe a deprecated one is set instead?
            if param["name"] in obsoleting_chains:
                obsoleted_set_instead = False
                for obsoleted_name in obsoleting_chains[param["name"]]:
                    if obsoleted_name in parameters:
                        obsoleted_set_instead = True
                        break
                if obsoleted_set_instead:
                    continue
            missing_parameters.add(param["name"])
        return missing_parameters

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
        # pylint: disable=unused-argument
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
            "deprecated_by": [],
            "obsoletes": None,
            "pcs_deprecated_warning": "",
            "unique": False,
        }
        new_param.update(properties)
        return new_param


class FakeAgentMetadata(Agent):
    #pylint:disable=abstract-method
    pass


class FencedMetadata(FakeAgentMetadata):
    def get_name(self):
        return "pacemaker-fenced"


    def _get_parameter(self, parameter_element):
        parameter = super(FencedMetadata, self)._get_parameter(
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
            [settings.pacemaker_fenced, "metadata"]
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
    _agent_type_label = "resource"

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


class AbsentAgentMixin():
    def _load_metadata(self):
        return "<resource-agent/>"

    def validate_parameters_create(
        self, parameters, force=False,
        # TODO remove this argument, see pcs.lib.cib.commands.remote_node.create
        # for details
        do_not_report_instance_attribute_server_exists=False
    ):
        # pylint: disable=unused-argument
        return []

    def validate_parameters_update(
        # pylint: disable=unused-argument
        self,
        current_parameters,
        new_parameters,
        force=False
    ):
        return []


class AbsentResourceAgent(AbsentAgentMixin, ResourceAgent):
    pass


class StonithAgent(CrmAgent):
    """
    Provides convinient access to a stonith agent's metadata
    """
    _fenced_metadata = None
    _agent_type_label = "stonith"

    @classmethod
    def clear_fenced_metadata_cache(cls):
        cls._fenced_metadata = None

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
            self._get_fenced_metadata().get_parameters()
        )

    def validate_parameters_create(
        self, parameters, force=False,
        # TODO remove this argument, see pcs.lib.cib.commands.remote_node.create
        # for details
        do_not_report_instance_attribute_server_exists=False
    ):
        report_list = super(StonithAgent, self).validate_parameters_create(
            parameters,
            force=force
        )
        report_list.extend(
            self._validate_action_is_deprecated(parameters, force=force)
        )
        return report_list

    def validate_parameters_update(
        self,
        current_parameters,
        new_parameters,
        force=False
    ):
        report_list = super(StonithAgent, self).validate_parameters_update(
            current_parameters,
            new_parameters,
            force=force
        )
        report_list.extend(
            self._validate_action_is_deprecated(new_parameters, force=force)
        )
        return report_list

    def _validate_action_is_deprecated(self, parameters, force=False):
        if parameters.get("action", ""):
            return [
                ReportItem(
                    self._validate_report_severity(force),
                    reports.messages.DeprecatedOption(
                        "action",
                        sorted(STONITH_ACTION_REPLACED_BY),
                        self._agent_type_label,
                    )
                )
            ]
        return []

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
            if param["name"] == "action":
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
                        ["'{0}'".format(x) for x in STONITH_ACTION_REPLACED_BY]
                    )
                )
                filtered.append(new_param)
            else:
                filtered.append(param)

        # 'port' parameter is required by a fence agent, but it is filled
        # automatically by pacemaker based on 'pcmk_host_map' or
        # 'pcmk_host_list' parameter (defined in fenced metadata). Pacemaker
        # marks 'port' parameter as not required for us.
        # It, however, doesn't mark any parameters deprecating 'port' as not
        # required se we must do so ourselves.
        port_related_params = set(["port"])
        new_deprecated = set(["port"])
        while new_deprecated:
            current_deprecated = new_deprecated
            new_deprecated = set()
            for param in filtered:
                if param["obsoletes"] in current_deprecated:
                    if param["name"] not in port_related_params:
                        new_deprecated.add(param["name"])
                        port_related_params.add(param["name"])
        for param in filtered:
            if param["name"] in port_related_params:
                param["required"] = False

        return filtered

    def _get_fenced_metadata(self):
        # pylint: disable=protected-access
        if not self.__class__._fenced_metadata:
            self.__class__._fenced_metadata = FencedMetadata(self._runner)
        return self.__class__._fenced_metadata

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
            force = reports.codes.FORCE_METADATA_ISSUE
        return ReportItem(
            severity=reports.item.ReportItemSeverity(severity, force),
            message=reports.messages.UnableToGetAgentMetadata(
                e.agent, e.message
            ),
        )
    if e.__class__ == InvalidResourceAgentName:
        return ReportItem.error(
            reports.messages.InvalidResourceAgentName(e.agent)
        )
    if e.__class__ == InvalidStonithAgentName:
        return ReportItem.error(
            reports.messages.InvalidStonithAgentName(e.agent)
        )
    raise e
