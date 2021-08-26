from dataclasses import dataclass, field, replace as dc_replace
import re
from typing import (
    cast,
    Container,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Type,
    Union,
)

from lxml import etree
from lxml.etree import _Element

from pcs import settings
from pcs.common import const, pacemaker, reports
from pcs.common.interface.dto import DataTransferObject, meta
from pcs.common.reports.types import SeverityLevel
from pcs.common.str_tools import format_list
from pcs.common.tools import xml_fromstring
from pcs.lib import validate
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner
from pcs.lib.pacemaker.values import is_true

# TODO: fix pylint issue
# pylint: disable=no-self-use


# These are all standards valid in cib. To get a list of standards supported by
# pacemaker in local environment, use result of "crm_resource --list-standards".
_ALLOWED_STANDARDS = {
    "ocf",
    "lsb",
    "heartbeat",
    "stonith",
    "upstart",
    "service",
    "systemd",
    "nagios",
}

STONITH_ACTION_REPLACED_BY = ["pcmk_off_action", "pcmk_reboot_action"]


### exceptions


class ResourceAgentError(Exception):
    # pylint: disable=super-init-not-called
    def __init__(self, agent_name: str, message: str = ""):
        self.agent = agent_name
        self.message = message


class UnableToGetAgentMetadata(ResourceAgentError):
    pass


class InvalidResourceAgentName(ResourceAgentError):
    pass


class InvalidStonithAgentName(ResourceAgentError):
    pass


### data classes


@dataclass(frozen=True)
class ResourceAgentName:
    standard: str
    provider: Optional[str]
    type: str

    @property
    def full_name(self) -> str:
        return ":".join(filter(None, [self.standard, self.provider, self.type]))


@dataclass(frozen=True)
class AgentParameterDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes

    # name of the parameter
    name: str
    # short description
    shortdesc: str
    # long description
    longdesc: str
    # data type of the parameter
    type: str
    # default value of the parameter
    default: Optional[str]
    # True if it is a required parameter, False otherwise
    required: bool
    # True if the parameter is meant for advanced users
    advanced: bool
    # True if the parameter is deprecated, False otherwise
    deprecated: bool
    # list of parameters deprecating this one
    deprecated_by: List[str]
    # name of a deprecated parameter obsoleted by this one
    obsoletes: Optional[str]
    # should the parameter's value be unique across same agent resources?
    unique: bool
    # pcs originated warning
    # TODO probably should not be part of the DTO, it should be produced by
    # some validator
    pcs_deprecated_warning: Optional[str]


@dataclass(frozen=True)
class AgentActionDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes

    # (start, stop, promote...), mandatory by both OCF 1.0 and 1.1
    name: str
    # mandatory by both OCF 1.0 and 1.1, sometimes not defined by agents
    timeout: Optional[str]
    # optional by both OCF 1.0 and 1.1
    interval: Optional[str]
    # optional by OCF 1.1
    # not allowed by OCF 1.0, defined in OCF 1.0 agents anyway
    role: Optional[str]
    # OCF name: 'start-delay', optional by both OCF 1.0 and 1.1
    start_delay: Optional[str] = field(metadata=meta(name="start-delay"))
    # optional by both OCF 1.0 and 1.1
    depth: Optional[str]
    # not allowed by any OCF, defined in OCF 1.0 agents anyway
    automatic: Optional[str]
    # not allowed by any OCF, defined in OCF 1.0 agents anyway
    on_target: Optional[str]


@dataclass(frozen=True)
class AgentMetadataDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes

    name: str  # full agent name: standard + provider + type
    standard: str
    provider: Optional[str]
    type: str
    shortdesc: str
    longdesc: str
    parameters: List[AgentParameterDto]
    actions: List[AgentActionDto]


### Agent wrapper / loader / facade classes


class Agent:
    """
    Base class for providing convinient access to an agent's metadata
    """

    _agent_type_label: str = "agent"

    def __init__(self, runner: CommandRunner):
        """
        create an instance which reads metadata by itself on demand
        """
        self._runner = runner
        self._metadata: Optional[_Element] = None

    def _get_name(self) -> str:
        raise NotImplementedError()

    def _get_standard(self) -> str:
        raise NotImplementedError()

    def _get_provider(self) -> Optional[str]:
        raise NotImplementedError()

    def _get_type(self) -> str:
        raise NotImplementedError()

    def _prepare_name_parts(self, name: str) -> ResourceAgentName:
        raise NotImplementedError()

    def get_name_info(self) -> AgentMetadataDto:
        """
        Get structured agent's info, only name is populated
        """
        return AgentMetadataDto(
            self._get_name(),
            self._get_standard(),
            self._get_provider(),
            self._get_type(),
            "",
            "",
            [],
            [],
        )

    def get_full_info(self) -> AgentMetadataDto:
        """
        Get structured agent's info, all items are populated
        """
        return AgentMetadataDto(
            self._get_name(),
            self._get_standard(),
            self._get_provider(),
            self._get_type(),
            self._get_shortdesc(),
            self._get_longdesc(),
            self._get_parameters(),
            self._get_raw_actions(),
        )

    def _get_shortdesc(self) -> str:
        """
        Get a short description of agent's purpose
        """
        return self._get_text_from_dom_element(
            self._get_metadata().find("shortdesc")
        ) or self._get_metadata().get("shortdesc", "")

    def _get_longdesc(self) -> str:
        """
        Get a long description of agent's purpose
        """
        return self._get_text_from_dom_element(
            self._get_metadata().find("longdesc")
        )

    def _get_parameters(self) -> List[AgentParameterDto]:
        """
        Get list of agent's parameters
        """
        params_element = self._get_metadata().find("parameters")
        if params_element is None:
            return []

        preprocessed_param_list = []
        deprecated_by_dict: Dict[str, Set[str]] = {}
        for param_el in params_element.iter("parameter"):
            param = self._get_parameter(param_el)
            if param is None:
                continue
            preprocessed_param_list.append(param)
            if param.obsoletes:
                obsoletes = param.obsoletes
                if not obsoletes in deprecated_by_dict:
                    deprecated_by_dict[obsoletes] = set()
                deprecated_by_dict[obsoletes].add(param.name)

        param_list = []
        for param in preprocessed_param_list:
            if param.name in deprecated_by_dict:
                param_list.append(
                    dc_replace(
                        param,
                        deprecated_by=sorted(deprecated_by_dict[param.name]),
                    )
                )
            else:
                param_list.append(param)

        return param_list

    def _get_parameter(
        self, parameter_element: _Element
    ) -> Optional[AgentParameterDto]:
        if parameter_element.get("name", None) is None:
            return None

        value_type = "string"
        default_value = None
        content_element = parameter_element.find("content")
        if content_element is not None:
            value_type = content_element.get("type", value_type)
            default_value = content_element.get("default", default_value)

        return AgentParameterDto(
            str(parameter_element.attrib["name"]),
            self._get_text_from_dom_element(
                parameter_element.find("shortdesc")
            ),
            self._get_text_from_dom_element(parameter_element.find("longdesc")),
            value_type,
            default_value,
            required=is_true(parameter_element.get("required", "0")),
            advanced=False,
            deprecated=is_true(parameter_element.get("deprecated", "0")),
            deprecated_by=[],
            obsoletes=parameter_element.get("obsoletes", None),
            unique=is_true(parameter_element.get("unique", "0")),
            pcs_deprecated_warning=None,
        )

    def _get_parameter_obsoleting_chains(self) -> Dict[str, List[str]]:
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
            param.name: param.obsoletes
            for param in self._get_parameters()
            if param.obsoletes
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
        self,
        parameters: Mapping[str, str],
        force: bool = False,
        # TODO remove this argument, see pcs.lib.cib.commands.remote_node.create
        # for details
        do_not_report_instance_attribute_server_exists: bool = False,
    ) -> reports.ReportItemList:
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
                {param.name for param in self._get_parameters()},
                option_type=self._agent_type_label,
                severity=reports.get_severity(reports.codes.FORCE, force),
            ).validate(parameters)
        )
        # TODO remove this "if", see pcs.lib.cib.commands.remote_node.create
        # for details
        if do_not_report_instance_attribute_server_exists:
            for report_item in report_items:
                if isinstance(report_item, reports.ReportItem) and isinstance(
                    report_item.message, reports.messages.InvalidOptions
                ):
                    report_msg = cast(
                        reports.messages.InvalidOptions, report_item.message
                    )
                    report_item.message = reports.messages.InvalidOptions(
                        report_msg.option_names,
                        sorted(
                            [
                                value
                                for value in report_msg.allowed
                                if value != "server"
                            ]
                        ),
                        report_msg.option_type,
                        report_msg.allowed_patterns,
                    )

        # report missing required parameters
        missing_parameters = self._find_missing_required_parameters(parameters)
        if missing_parameters:
            report_items.append(
                reports.ReportItem(
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
        current_parameters: Mapping[str, str],
        new_parameters: Mapping[str, str],
        force: bool = False,
    ) -> reports.ReportItemList:
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
                {param.name for param in self._get_parameters()},
                option_type=self._agent_type_label,
                severity=reports.get_severity(reports.codes.FORCE, force),
            ).validate(
                # Do not report unknown parameters already set in the CIB. They
                # have been reported already when the were added to the CIB.
                {
                    name: value
                    for name, value in new_parameters.items()
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
                reports.ReportItem(
                    severity=self._validate_report_severity(force),
                    message=reports.messages.RequiredOptionsAreMissing(
                        sorted(missing_parameters),
                        self._agent_type_label,
                    ),
                )
            )

        return report_items

    @staticmethod
    def _validate_report_severity(force: bool) -> reports.ReportItemSeverity:
        return reports.ReportItemSeverity(
            level=(
                reports.ReportItemSeverity.WARNING
                if force
                else reports.ReportItemSeverity.ERROR
            ),
            force_code=reports.codes.FORCE if not force else None,
        )

    def _find_missing_required_parameters(
        self, parameters: Mapping[str, str]
    ) -> Set[str]:
        missing_parameters = set()
        obsoleting_chains = self._get_parameter_obsoleting_chains()
        for param in self._get_parameters():
            if not param.required or param.deprecated_by:
                # non-required params are never required
                # we require non-deprecated params preferentially
                continue
            if param.name in parameters:
                # the param is not missing
                continue
            # the param is missing, maybe a deprecated one is set instead?
            if param.name in obsoleting_chains:
                obsoleted_set_instead = False
                for obsoleted_name in obsoleting_chains[param.name]:
                    if obsoleted_name in parameters:
                        obsoleted_set_instead = True
                        break
                if obsoleted_set_instead:
                    continue
            missing_parameters.add(param.name)
        return missing_parameters

    def _get_raw_actions(self) -> List[AgentActionDto]:
        actions_element = self._get_metadata().find("actions")
        if actions_element is None:
            return []
        return [
            AgentActionDto(
                str(action.attrib["name"]),
                action.get("timeout"),
                action.get("interval"),
                pacemaker.role.get_value_primary(
                    const.PcmkRoleType(str(action.attrib["role"]))
                )
                if action.get("role", None) is not None
                else action.get("role"),
                action.get("start-delay"),
                action.get("depth"),
                action.get("automatic"),
                action.get("on_target"),
            )
            for action in actions_element.iter("action")
            if action.get("name", None) is not None
        ]

    def _get_metadata(self) -> _Element:
        """
        Return metadata DOM
        Raise UnableToGetAgentMetadata if agent doesn't exist or unable to get
            or parse its metadata
        """
        if self._metadata is None:
            self._metadata = self._parse_metadata(self._load_metadata())
        return self._metadata

    def _load_metadata(self) -> str:
        raise NotImplementedError()

    def _parse_metadata(self, metadata: str) -> _Element:
        try:
            dom = xml_fromstring(metadata)
            # TODO Majority of agents don't provide valid metadata, so we skip
            # the validation for now. We want to enable it once the schema
            # and/or agents are fixed.
            # When enabling this check for overrides in child classes.
            # if os.path.isfile(settings.agent_metadata_schema):
            #    etree.DTD(file=settings.agent_metadata_schema).assertValid(dom)
            return dom
        except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
            raise UnableToGetAgentMetadata(self._get_name(), str(e)) from e

    def _get_text_from_dom_element(self, element: Optional[_Element]) -> str:
        if element is None or element.text is None:
            return ""
        return str(element.text).strip()


class FakeAgentMetadata(Agent):
    def _get_name(self) -> str:
        raise NotImplementedError()

    def _load_metadata(self) -> str:
        raise NotImplementedError()


class FencedMetadata(FakeAgentMetadata):
    def _get_standard(self) -> str:
        raise NotImplementedError()

    def _get_provider(self) -> Optional[str]:
        raise NotImplementedError()

    def _get_type(self) -> str:
        raise NotImplementedError()

    def _prepare_name_parts(self, name: str) -> ResourceAgentName:
        raise NotImplementedError()

    def _get_name(self) -> str:
        return "pacemaker-fenced"

    def _get_parameter(
        self, parameter_element: _Element
    ) -> Optional[AgentParameterDto]:
        parameter = super()._get_parameter(parameter_element)
        if parameter is None:
            return None
        # Metadata are written in such a way that a longdesc text is a
        # continuation of a shortdesc text.
        return dc_replace(
            parameter,
            longdesc=f"{parameter.shortdesc}\n{parameter.longdesc}".strip(),
            advanced=parameter.shortdesc.startswith("Advanced use only"),
        )

    def _load_metadata(self) -> str:
        stdout, stderr, dummy_retval = self._runner.run(
            [settings.pacemaker_fenced, "metadata"]
        )
        metadata = stdout.strip()
        if not metadata:
            raise UnableToGetAgentMetadata(self._get_name(), stderr.strip())
        return metadata


class CrmAgent(Agent):
    def __init__(self, runner: CommandRunner, name: str):
        super().__init__(runner)
        self._name_parts = self._prepare_name_parts(name)

    def _prepare_name_parts(self, name: str) -> ResourceAgentName:
        raise NotImplementedError()

    def _get_full_name(self) -> str:
        return self._name_parts.full_name

    def _get_standard(self) -> str:
        return self._name_parts.standard

    def _get_provider(self) -> Optional[str]:
        return self._name_parts.provider

    def _get_type(self) -> str:
        return self._name_parts.type

    # TODO this is used only in this module, put it into right place and make
    # it private
    def is_valid_metadata(self) -> bool:
        """
        If we are able to get metadata, we consider the agent existing and valid
        """
        # if the agent is valid, we do not need to load its metadata again
        try:
            self._get_metadata()
        except UnableToGetAgentMetadata:
            return False
        return True

    # TODO this is used only in this module, put it into right place and make
    # it private
    def validate_metadata(self) -> "CrmAgent":
        """
        Validate metadata by attempt to retrieve it.
        """
        self._get_metadata()
        return self

    def _load_metadata(self) -> str:
        env_path = ":".join(
            [
                # otherwise pacemaker cannot run RHEL fence agents to get their
                # metadata
                settings.fence_agent_binaries,
                # otherwise heartbeat and cluster-glue agents don't work
                "/bin",
                # otherwise heartbeat and cluster-glue agents don't work
                "/usr/bin",
            ]
        )
        stdout, stderr, retval = self._runner.run(
            [
                settings.crm_resource_binary,
                "--show-metadata",
                self._get_full_name(),
            ],
            env_extend={
                "PATH": env_path,
            },
        )
        if retval != 0:
            raise UnableToGetAgentMetadata(self._get_name(), stderr.strip())
        return stdout.strip()


class ResourceAgent(CrmAgent):
    """
    Provides convinient access to a resource agent's metadata
    """

    _agent_type_label = "resource"

    def _prepare_name_parts(self, name: str) -> ResourceAgentName:
        return _split_resource_agent_name(name)

    def _get_name(self) -> str:
        return self._get_full_name()

    def _get_parameters(self) -> List[AgentParameterDto]:
        parameters = super()._get_parameters()
        if self._get_standard() == "ocf" and (
            self._get_provider() in ("heartbeat", "pacemaker")
        ):
            trace_ra_found = False
            trace_file_found = False
            for param in parameters:
                param_name = param.name.lower()
                if param_name == "trace_ra":
                    trace_ra_found = True
                elif param_name == "trace_file":
                    trace_file_found = True
                if trace_file_found and trace_ra_found:
                    break

            if not trace_ra_found:
                shortdesc = (
                    "Set to 1 to turn on resource agent tracing"
                    " (expect large output)"
                )
                parameters.append(
                    AgentParameterDto(
                        "trace_ra",
                        shortdesc,
                        (
                            shortdesc + " The trace output will be saved to "
                            "trace_file, if set, or by default to"
                            " $HA_VARRUN/ra_trace/<type>/<id>.<action>."
                            "<timestamp> e.g. $HA_VARRUN/ra_trace/oracle/"
                            "db.start.2012-11-27.08:37:08"
                        ),
                        type="integer",
                        default="0",
                        required=False,
                        advanced=True,
                        deprecated=False,
                        deprecated_by=[],
                        obsoletes=None,
                        unique=False,
                        pcs_deprecated_warning=None,
                    )
                )
            if not trace_file_found:
                shortdesc = "Path to a file to store resource agent tracing log"
                parameters.append(
                    AgentParameterDto(
                        "trace_file",
                        shortdesc,
                        shortdesc,
                        type="string",
                        default="",
                        required=False,
                        advanced=True,
                        deprecated=False,
                        deprecated_by=[],
                        obsoletes=None,
                        unique=False,
                        pcs_deprecated_warning=None,
                    )
                )

        return parameters


class AbsentAgentMixin:
    def _load_metadata(self) -> str:
        return "<resource-agent/>"

    def validate_parameters_create(
        self,
        parameters: Mapping[str, str],
        force: bool = False,
        # TODO remove this argument, see pcs.lib.cib.commands.remote_node.create
        # for details
        do_not_report_instance_attribute_server_exists: bool = False,
    ) -> reports.ReportItemList:
        del parameters, force, do_not_report_instance_attribute_server_exists
        return []

    def validate_parameters_update(
        self,
        current_parameters: Mapping[str, str],
        new_parameters: Mapping[str, str],
        force: bool = False,
    ) -> reports.ReportItemList:
        del current_parameters, new_parameters, force
        return []


class AbsentResourceAgent(AbsentAgentMixin, ResourceAgent):
    pass


class StonithAgent(CrmAgent):
    """
    Provides convinient access to a stonith agent's metadata
    """

    _fenced_metadata: Optional[FencedMetadata] = None
    _agent_type_label: str = "stonith"

    # TODO This is only used in tests to make them work. Tests are calling this
    # to flush the cache and thus ensuring consistent behavior - the metadata
    # are always loaded in all tests. TODO: implement the cache in such a way
    # no such hack is needed al drop the cache altogether if architecture
    # allows that.
    @classmethod
    def clear_fenced_metadata_cache(cls) -> None:
        cls._fenced_metadata = None

    def _prepare_name_parts(self, name: str) -> ResourceAgentName:
        # pacemaker doesn't support stonith (nor resource) agents with : in type
        if ":" in name:
            raise InvalidStonithAgentName(name)
        return ResourceAgentName("stonith", None, name)

    def _get_name(self) -> str:
        return self._get_type()

    def _get_parameters(self) -> List[AgentParameterDto]:
        # TODO: fix pylint issue
        # pylint: disable=protected-access
        return (
            self._filter_parameters(super()._get_parameters())
            + self._get_fenced_metadata()._get_parameters()
        )

    def validate_parameters_create(
        self,
        parameters: Mapping[str, str],
        force: bool = False,
        # TODO remove this argument, see pcs.lib.cib.commands.remote_node.create
        # for details
        do_not_report_instance_attribute_server_exists: bool = False,
    ) -> reports.ReportItemList:
        report_list = super().validate_parameters_create(
            parameters, force=force
        )
        report_list.extend(
            self._validate_action_is_deprecated(parameters, force=force)
        )
        return report_list

    def validate_parameters_update(
        self,
        current_parameters: Mapping[str, str],
        new_parameters: Mapping[str, str],
        force: bool = False,
    ) -> reports.ReportItemList:
        report_list = super().validate_parameters_update(
            current_parameters, new_parameters, force=force
        )
        report_list.extend(
            self._validate_action_is_deprecated(new_parameters, force=force)
        )
        return report_list

    def _validate_action_is_deprecated(
        self, parameters: Mapping[str, str], force: bool = False
    ) -> reports.ReportItemList:
        if parameters.get("action", ""):
            return [
                reports.ReportItem(
                    self._validate_report_severity(force),
                    reports.messages.DeprecatedOption(
                        "action",
                        sorted(STONITH_ACTION_REPLACED_BY),
                        self._agent_type_label,
                    ),
                )
            ]
        return []

    def _filter_parameters(
        self, parameters: Iterable[AgentParameterDto]
    ) -> List[AgentParameterDto]:
        """
        Remove parameters that should not be available to the user.
        """
        # We don't allow the user to change these options which are only
        # intended to be used interactively on command line.
        remove_parameters = frozenset(("help", "version"))
        filtered_1 = []
        for param in parameters:
            if param.name in remove_parameters:
                continue
            if param.name == "action":
                # However we still need the user to be able to set 'action' due
                # to backward compatibility reasons. So we just mark it as not
                # required. We also move it to advanced params to indicate users
                # should not set it in most cases.
                filtered_1.append(
                    dc_replace(
                        param,
                        required=False,
                        advanced=True,
                        pcs_deprecated_warning=(
                            "Specifying 'action' is deprecated and not "
                            "necessary with current Pacemaker versions. "
                            "Use {0} instead."
                        ).format(format_list(STONITH_ACTION_REPLACED_BY)),
                    )
                )
            else:
                filtered_1.append(param)

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
            for param in filtered_1:
                if param.obsoletes in current_deprecated:
                    if param.name not in port_related_params:
                        new_deprecated.add(param.name)
                        port_related_params.add(param.name)
        filtered_2 = []
        for param in filtered_1:
            if param.name in port_related_params:
                filtered_2.append(dc_replace(param, required=False))
            else:
                filtered_2.append(param)

        return filtered_2

    def _get_fenced_metadata(self) -> FencedMetadata:
        # TODO: fix pylint issue
        # pylint: disable=protected-access
        if not self.__class__._fenced_metadata:
            self.__class__._fenced_metadata = FencedMetadata(self._runner)
        return self.__class__._fenced_metadata

    def get_provides_unfencing(self) -> bool:
        # TODO: fix pylint issue
        # pylint: disable=protected-access
        for action in self._get_raw_actions():
            if (
                action.name == "on"
                and action.on_target == "1"
                and action.automatic == "1"
            ):
                return True
        return False


class AbsentStonithAgent(AbsentAgentMixin, StonithAgent):
    def _get_parameters(self) -> List[AgentParameterDto]:
        return []


### agent name


def _split_resource_agent_name(full_agent_name: str) -> ResourceAgentName:
    # full_agent_name could be for example systemd:lvm2-pvscan@252:2
    # note that the second colon is not separator of provider and type
    match = re.match(
        "^(?P<standard>systemd|service):(?P<agent_type>[^:@]+@.*)$",
        full_agent_name,
    )
    if match:
        return ResourceAgentName(
            match.group("standard"), None, match.group("agent_type")
        )

    match = re.match(
        "^(?P<standard>[^:]+)(:(?P<provider>[^:]+))?:(?P<type>[^:]+)$",
        full_agent_name,
    )
    if not match:
        raise InvalidResourceAgentName(full_agent_name)

    standard = match.group("standard")
    provider = match.group("provider") if match.group("provider") else None
    agent_type = match.group("type")

    if standard not in _ALLOWED_STANDARDS:
        raise InvalidResourceAgentName(full_agent_name)

    if standard == "ocf" and not provider:
        raise InvalidResourceAgentName(full_agent_name)

    if standard != "ocf" and provider:
        raise InvalidResourceAgentName(full_agent_name)

    return ResourceAgentName(standard, provider, agent_type)


### get a list of standards, providers, agents


def list_resource_agents_standards(runner: CommandRunner) -> List[str]:
    """
    Return list of resource agents standards (ocf, lsb, ... ) on the local host
    """
    # retval is number of standards found
    stdout, dummy_stderr, dummy_retval = runner.run(
        [settings.crm_resource_binary, "--list-standards"]
    )
    # we are only interested in RESOURCE agents
    ignored_standards = frozenset(["stonith"])
    return _prepare_agent_list(stdout, ignored_standards)


def list_resource_agents_ocf_providers(runner: CommandRunner) -> List[str]:
    """
    Return list of resource agents ocf providers on the local host
    """
    # retval is number of providers found
    stdout, dummy_stderr, dummy_retval = runner.run(
        [settings.crm_resource_binary, "--list-ocf-providers"]
    )
    return _prepare_agent_list(stdout)


def list_resource_agents_standards_and_providers(
    runner: CommandRunner,
) -> List[str]:
    """
    Return list of all standard[:provider] on the local host
    """
    standards = list_resource_agents_standards(runner) + [
        f"ocf:{provider}"
        for provider in list_resource_agents_ocf_providers(runner)
    ]
    # do not list ocf resources twice
    try:
        standards.remove("ocf")
    except ValueError:
        pass
    return sorted(standards, key=str.lower)


def list_resource_agents(
    runner: CommandRunner, standard_provider: str
) -> List[str]:
    """
    Return list of resource agents for specified standard on the local host

    runner
    standard_provider -- standard[:provider], e.g. lsb, ocf, ocf:pacemaker
    """
    # retval is 0 on success, anything else when no agents found
    stdout, dummy_stderr, retval = runner.run(
        [settings.crm_resource_binary, "--list-agents", standard_provider]
    )
    if retval != 0:
        return []
    return _prepare_agent_list(stdout)


def list_stonith_agents(runner: CommandRunner) -> List[str]:
    """
    Return list of fence agents on the local host
    """
    # retval is 0 on success, anything else when no agents found
    stdout, dummy_stderr, retval = runner.run(
        [settings.crm_resource_binary, "--list-agents", "stonith"]
    )
    if retval != 0:
        return []
    ignored_agents = frozenset(
        [
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
        ]
    )
    return _prepare_agent_list(stdout, ignored_agents)


def _prepare_agent_list(
    agents_string: str, ignored_items: Optional[Container] = None
) -> List[str]:
    """
    Parse list of agents / standards / providers / etc provided by crm_resource
    """
    ignored = ignored_items or frozenset([])
    result = [
        name
        for name in [line.strip() for line in agents_string.splitlines()]
        if name and name not in ignored
    ]
    return sorted(result, key=str.lower)


### get an Agent instance by agent's name


def _guess_resource_agent_full_name(
    runner: CommandRunner, search_agent_name: str
) -> List[ResourceAgent]:
    """
    List resource agents matching specified search term

    search_agent_name -- part of full agent name
    """
    search_lower = search_agent_name.lower()
    # list all possible names
    possible_names = []
    for std in list_resource_agents_standards_and_providers(runner):
        for agent in list_resource_agents(runner, std):
            if search_lower == agent.lower():
                possible_names.append(f"{std}:{agent}")
    # construct agent wrappers
    agent_candidates = [
        ResourceAgent(runner, agent) for agent in possible_names
    ]
    # check if the agent is valid
    return [agent for agent in agent_candidates if agent.is_valid_metadata()]


def _guess_exactly_one_resource_agent_full_name(
    runner: CommandRunner, search_agent_name: str
) -> ResourceAgent:
    """
    Get one resource agent matching specified search term or raise LibraryError

    search_agent_name -- last part of full agent name
    """
    agents = _guess_resource_agent_full_name(runner, search_agent_name)
    if not agents:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.AgentNameGuessFoundNone(search_agent_name)
            )
        )
    if len(agents) > 1:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.AgentNameGuessFoundMoreThanOne(
                    search_agent_name,
                    sorted([agent.get_name_info().name for agent in agents]),
                )
            )
        )
    return agents[0]


def find_valid_resource_agent_by_name(
    report_processor: reports.ReportProcessor,
    runner: CommandRunner,
    name: str,
    allowed_absent: bool = False,
    absent_agent_supported: bool = True,
) -> Union[ResourceAgent, AbsentResourceAgent]:
    """
    Return instance of ResourceAgent corresponding to name

    report_processor -- tool for warning/info/error reporting
    runner -- tool for launching external commands
    name -- specifies a searched agent
    allowed_absent -- return a dummy class if agent not found
    absent_agent_supported -- should an error "agent not found" be forcible?
    """
    if ":" not in name:
        agent = _guess_exactly_one_resource_agent_full_name(runner, name)
        report_processor.report(
            reports.ReportItem.info(
                reports.messages.AgentNameGuessed(
                    name, agent.get_name_info().name
                )
            )
        )
        return agent

    return cast(
        ResourceAgent,
        _find_valid_agent_by_name(
            report_processor,
            runner,
            name,
            ResourceAgent,
            AbsentResourceAgent if allowed_absent else None,
            absent_agent_supported=absent_agent_supported,
        ),
    )


def find_valid_stonith_agent_by_name(
    report_processor: reports.ReportProcessor,
    runner: CommandRunner,
    name: str,
    allowed_absent: bool = False,
    absent_agent_supported: bool = True,
) -> Union[StonithAgent, AbsentStonithAgent]:
    """
    Return instance of StonithAgent corresponding to name

    report_processor -- tool for warning/info/error reporting
    runner -- tool for launching external commands
    name -- specifies a searched agent
    allowed_absent -- return a dummy class if agent not found
    absent_agent_supported -- should an error "agent not found" be forcible?
    """
    return cast(
        StonithAgent,
        _find_valid_agent_by_name(
            report_processor,
            runner,
            name,
            StonithAgent,
            AbsentStonithAgent if allowed_absent else None,
            absent_agent_supported=absent_agent_supported,
        ),
    )


def _find_valid_agent_by_name(
    report_processor: reports.ReportProcessor,
    runner: CommandRunner,
    name: str,
    present_agent_class: Type[CrmAgent],
    absent_agent_class: Optional[
        Type[Union[AbsentResourceAgent, AbsentStonithAgent]]
    ],
    absent_agent_supported: bool = True,
) -> CrmAgent:
    try:
        return present_agent_class(runner, name).validate_metadata()
    except (InvalidResourceAgentName, InvalidStonithAgentName) as e:
        raise LibraryError(resource_agent_error_to_report_item(e)) from e
    except UnableToGetAgentMetadata as e:
        if not absent_agent_supported:
            raise LibraryError(resource_agent_error_to_report_item(e)) from e

        if not absent_agent_class:
            raise LibraryError(
                resource_agent_error_to_report_item(e, forceable=True)
            ) from e

        report_processor.report(
            resource_agent_error_to_report_item(
                e,
                severity=reports.ReportItemSeverity.WARNING,
            )
        )

        return absent_agent_class(runner, name)


def resource_agent_error_to_report_item(
    e: ResourceAgentError,
    severity: SeverityLevel = reports.ReportItemSeverity.ERROR,
    forceable: bool = False,
) -> reports.ReportItem:
    """
    Transform ResourceAgentError to ReportItem
    """
    force = None
    if e.__class__ == UnableToGetAgentMetadata:
        if severity == reports.ReportItemSeverity.ERROR and forceable:
            force = reports.codes.FORCE
        return reports.ReportItem(
            severity=reports.ReportItemSeverity(severity, force),
            message=reports.messages.UnableToGetAgentMetadata(
                e.agent, e.message
            ),
        )
    if e.__class__ == InvalidResourceAgentName:
        return reports.ReportItem.error(
            reports.messages.InvalidResourceAgentName(e.agent)
        )
    if e.__class__ == InvalidStonithAgentName:
        return reports.ReportItem.error(
            reports.messages.InvalidStonithAgentName(e.agent)
        )
    raise e
