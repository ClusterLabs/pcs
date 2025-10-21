from collections import defaultdict
from dataclasses import replace as dc_replace
from typing import (
    Dict,
    Iterable,
    List,
    Optional,
    Set,
)

from pcs.common import reports
from pcs.common.types import StringIterable
from pcs.lib import validate
from pcs.lib.external import CommandRunner

from . import const
from .error import (
    ResourceAgentError,
    resource_agent_error_to_report_item,
)
from .name import name_to_void_metadata
from .ocf_transform import ocf_version_to_ocf_unified
from .pcs_transform import (
    get_additional_trace_parameters,
    ocf_unified_to_pcs,
)
from .types import (
    CrmAttrAgent,
    CrmResourceAgent,
    FakeAgentName,
    ResourceAgentMetadata,
    ResourceAgentName,
    ResourceAgentParameter,
)
from .xml import (
    load_crm_attribute_metadata,
    load_crm_resource_metadata,
    load_fake_agent_metadata,
    load_metadata,
    parse_metadata,
)


class ResourceAgentFacade:
    """
    Provides metadata of and validators for a resource / stonith agent
    """

    def __init__(
        self,
        metadata: ResourceAgentMetadata,
        additional_parameters: Optional[
            Iterable[ResourceAgentParameter]
        ] = None,
    ) -> None:
        """
        metadata -- parsed OCF metadata in a universal format (not version specific)
        additional_parameters -- resource parameters defined outside an agent
        """
        self._raw_metadata = metadata
        self._additional_parameters = additional_parameters
        self._pcs_metadata_cache: Optional[ResourceAgentMetadata] = None

    @property
    def metadata(self) -> ResourceAgentMetadata:
        """
        Return cleaned agent metadata
        """
        if self._pcs_metadata_cache is None:
            self._pcs_metadata_cache = self._get_metadata()
        return self._pcs_metadata_cache

    def _get_metadata(self) -> ResourceAgentMetadata:
        pcs_metadata = ocf_unified_to_pcs(self._raw_metadata)
        if self._additional_parameters:
            pcs_metadata = dc_replace(
                pcs_metadata,
                parameters=(
                    pcs_metadata.parameters + list(self._additional_parameters)
                ),
            )
        return pcs_metadata

    # Facade provides just a basic validation checking that required parameters
    # are set and all set parameters are known to an agent. Missing checks are:
    # 1. values checks - if a param is an integer, then "abc" is not valid
    # 2. errors should be emitted when a deprecated parameter and a
    #    parameter obsoleting it are set at the same time
    # 3. possibly some other checks
    # All of these have been missing in pcs since ever (ad 1. agents have not
    # provided enough info for us to do such validations, ad 3. there were no
    # deprecated parameters before). The checks should be implemented in agents
    # themselves, so we're not adding them now either.

    def get_validators_allowed_parameters(
        self, force: bool = False
    ) -> List[validate.ValidatorInterface]:
        """
        Return validators checking for specified parameters names

        force -- if True, validators produce a warning instead of an error
        """
        return [
            validate.NamesIn(
                {param.name for param in self.metadata.parameters},
                self._validator_option_type,
                severity=reports.item.get_severity(reports.codes.FORCE, force),
            )
        ]

    def get_validators_deprecated_parameters(
        self,
    ) -> List[validate.ValidatorInterface]:
        """
        Return validators looking for deprecated parameters
        """
        # Setting deprecated parameters always emit a warning - we want to allow
        # using them not to break backward compatibility.
        return [
            validate.DeprecatedOption(
                [param.name],
                param.deprecated_by,
                self._validator_option_type,
                severity=reports.ReportItemSeverity.warning(),
            )
            for param in self.metadata.parameters
            if param.deprecated
        ]

    def get_validators_required_parameters(
        self,
        force: bool = False,
        only_parameters: Optional[StringIterable] = None,
    ) -> List[validate.ValidatorInterface]:
        """
        Return validators checking if required parameters were specified

        force -- if True, validators produce a warning instead of an error
        only_parameters -- if set, only specified parameters are checked
        """
        validators: List[validate.ValidatorInterface] = []
        severity = reports.item.get_severity(reports.codes.FORCE, force)
        only_parameters = only_parameters or set()

        required_not_obsoleting: Set[str] = set()
        all_params_deprecated_by = self._get_all_params_deprecated_by()
        for param in self.metadata.parameters:
            if not param.required or param.deprecated:
                continue
            deprecated_by_param = all_params_deprecated_by[param.name]
            if only_parameters and not (
                {param.name} | deprecated_by_param
            ).intersection(only_parameters):
                continue
            if deprecated_by_param:
                validators.append(
                    validate.IsRequiredSome(
                        {param.name} | deprecated_by_param,
                        self._validator_option_type,
                        deprecated_option_name_list=deprecated_by_param,
                        severity=severity,
                    )
                )
            else:
                required_not_obsoleting.add(param.name)

        if required_not_obsoleting:
            validators.append(
                validate.IsRequiredAll(
                    required_not_obsoleting,
                    self._validator_option_type,
                    severity,
                )
            )

        return validators

    @property
    def _validator_option_type(self) -> str:
        return "stonith" if self.metadata.name.is_stonith else "resource"

    def _get_all_params_deprecated_by(self) -> Dict[str, Set[str]]:
        new_olds_map: Dict[str, Set[str]] = defaultdict(set)
        for param in self.metadata.parameters:
            for new_name in param.deprecated_by:
                new_olds_map[new_name].add(param.name)

        result: Dict[str, Set[str]] = defaultdict(set)
        for param in self.metadata.parameters:
            discovered = new_olds_map[param.name]
            while discovered:
                result[param.name] |= discovered
                new_discovered = set()
                for name in discovered:
                    new_discovered |= new_olds_map[name]
                discovered = new_discovered - result[param.name]
        return result


class ResourceAgentFacadeFactory:
    """
    Creates ResourceAgentFacade instances
    """

    def __init__(
        self, runner: CommandRunner, report_processor: reports.ReportProcessor
    ) -> None:
        self._runner = runner
        self._report_processor = report_processor
        self._fenced_metadata: Optional[ResourceAgentMetadata] = None

    def facade_from_parsed_name(
        self, name: ResourceAgentName
    ) -> ResourceAgentFacade:
        """
        Create ResourceAgentFacade based on specified agent name

        name -- agent name to get a facade for
        """
        return self._facade_from_metadata(
            ocf_version_to_ocf_unified(
                parse_metadata(name, load_metadata(self._runner, name))
            )
        )

    def void_facade_from_parsed_name(
        self, name: ResourceAgentName
    ) -> ResourceAgentFacade:
        """
        Create ResourceAgentFacade for a non-existent agent

        name -- name of a non-existent agent to put into the facade
        """
        return self._facade_from_metadata(name_to_void_metadata(name))

    def facade_from_crm_attribute(
        self, agent_name: CrmAttrAgent
    ) -> ResourceAgentFacade:
        return ResourceAgentFacade(self._get_crm_attribute_metadata(agent_name))

    def _facade_from_metadata(
        self, metadata: ResourceAgentMetadata
    ) -> ResourceAgentFacade:
        additional_parameters = []
        if metadata.name.is_stonith:
            additional_parameters += self._get_fenced_parameters()
        if metadata.name.standard == "ocf" and metadata.name.provider in (
            "heartbeat",
            "pacemaker",
        ):
            additional_parameters += get_additional_trace_parameters(
                metadata.parameters
            )
        return ResourceAgentFacade(metadata, additional_parameters)

    def _get_fake_agent_metadata(
        self, agent_name: FakeAgentName
    ) -> ResourceAgentMetadata:
        return ocf_version_to_ocf_unified(
            parse_metadata(
                ResourceAgentName(const.FAKE_AGENT_STANDARD, None, agent_name),
                load_fake_agent_metadata(self._runner, agent_name),
            )
        )

    def _get_crm_attribute_metadata(
        self, agent_name: CrmAttrAgent
    ) -> ResourceAgentMetadata:
        return ocf_version_to_ocf_unified(
            parse_metadata(
                ResourceAgentName(const.FAKE_AGENT_STANDARD, None, agent_name),
                load_crm_attribute_metadata(self._runner, agent_name),
            )
        )

    def _get_fenced_parameters(self) -> List[ResourceAgentParameter]:
        if self._fenced_metadata is None:
            agent_name = const.PACEMAKER_FENCED
            try:
                self._fenced_metadata = ocf_unified_to_pcs(
                    self._get_fake_agent_metadata(agent_name)
                )
            except ResourceAgentError as e:
                # If pcs is unable to load fenced metadata, cache an empty
                # metadata in order to prevent further futile attempts to load
                # them.
                # Since we are recovering from the failure, we report it as a
                # warning.
                self._report_processor.report(
                    resource_agent_error_to_report_item(
                        e, severity=reports.ReportItemSeverity.warning()
                    )
                )
                self._fenced_metadata = name_to_void_metadata(
                    ResourceAgentName(
                        const.FAKE_AGENT_STANDARD, None, agent_name
                    )
                )
        return self._fenced_metadata.parameters


# definition is no provided by pacemaker yet
_ADDITIONAL_FENCING_META_ATTRIBUTES = [
    ResourceAgentParameter(
        name="provides",
        shortdesc=None,
        longdesc="Any special capability provided by the fence device.",
        type="string",
        default=None,
        enum_values=None,
        required=False,
        advanced=False,
        deprecated=False,
        deprecated_by=[],
        deprecated_desc=None,
        unique_group=None,
        reloadable=False,
    )
]


def get_crm_resource_metadata(
    runner: CommandRunner, agent_name: CrmResourceAgent
) -> list[ResourceAgentParameter]:
    """
    Return parsed metadata from crm_resource --list-options=TYPE.

    runner -- external processes runner
    agent_name -- name of pacemaker part whose metadata we want to get
    """
    load_agent_name = (
        agent_name if agent_name != const.STONITH_META else const.PRIMITIVE_META
    )
    parameters_metadata = ocf_unified_to_pcs(
        ocf_version_to_ocf_unified(
            parse_metadata(
                ResourceAgentName(
                    const.FAKE_AGENT_STANDARD, None, load_agent_name
                ),
                load_crm_resource_metadata(runner, load_agent_name),
            )
        )
    ).parameters
    if agent_name == const.STONITH_META:
        parameters_metadata += _ADDITIONAL_FENCING_META_ATTRIBUTES
    return parameters_metadata
