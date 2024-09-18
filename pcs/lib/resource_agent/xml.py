from typing import (
    List,
    Optional,
    Tuple,
    Union,
)

from lxml import etree
from lxml.etree import _Element

from pcs import settings
from pcs.common.str_tools import join_multilines
from pcs.common.tools import xml_fromstring
from pcs.lib.external import CommandRunner
from pcs.lib.pacemaker.api_result import (
    get_api_result_dom,
    get_status_from_api_result,
)
from pcs.lib.xml_tools import etree_to_str

from . import const
from .error import (
    UnableToGetAgentMetadata,
    UnsupportedOcfVersion,
)
from .types import (
    FakeAgentName,
    ResourceAgentActionOcf1_0,
    ResourceAgentActionOcf1_1,
    ResourceAgentMetadataOcf1_0,
    ResourceAgentMetadataOcf1_1,
    ResourceAgentName,
    ResourceAgentParameterOcf1_0,
    ResourceAgentParameterOcf1_1,
)

### load metadata


def _load_metadata_xml(
    runner: CommandRunner, agent_name: ResourceAgentName
) -> str:
    """
    Run pacemaker tool to get raw metadata from an agent

    runner -- external processes runner
    agent_name -- name of an agent whose metadata we want to get
    """
    env_path = ":".join(
        [
            # otherwise pacemaker cannot run RHEL fence agents to get their
            # metadata
            settings.fence_agent_execs,
            # otherwise heartbeat and cluster-glue agents don't work
            "/bin",
            # otherwise heartbeat and cluster-glue agents don't work
            "/usr/bin",
        ]
    )
    stdout, stderr, retval = runner.run(
        [settings.crm_resource_exec, "--show-metadata", agent_name.full_name],
        env_extend={"PATH": env_path},
    )
    if retval != 0:
        raise UnableToGetAgentMetadata(agent_name.full_name, stderr.strip())
    return stdout.strip()


def _load_fake_agent_metadata_xml(
    runner: CommandRunner, agent_name: FakeAgentName
) -> str:
    """
    Run pacemaker tool to get raw metadata from pacemaker

    runner -- external processes runner
    agent_name -- name of pacemaker part whose metadata we want to get
    """
    name_to_executable = {
        const.PACEMAKER_BASED: settings.pacemaker_based_exec,
        const.PACEMAKER_CONTROLD: settings.pacemaker_controld_exec,
        const.PACEMAKER_FENCED: settings.pacemaker_fenced_exec,
        const.PACEMAKER_SCHEDULERD: settings.pacemaker_schedulerd_exec,
    }
    if agent_name not in name_to_executable:
        raise UnableToGetAgentMetadata(agent_name, "Unknown agent")
    stdout, stderr, dummy_retval = runner.run(
        [name_to_executable[agent_name], "metadata"]
    )
    metadata = stdout.strip()
    if not metadata:
        raise UnableToGetAgentMetadata(agent_name, stderr.strip())
    return metadata


def _load_fake_agent_crm_attribute_metadata_xml(
    runner: CommandRunner, agent_name: FakeAgentName
) -> str:
    """
    Run pacemaker crm_attribute to get raw metadata from pacemaker in form of
    pacemaker api_result. Get the resource-agent element from the
    pacemaker-result element and convert it to xml string. Other pacemaker
    tools do not return metadata in api_result format.

    runner -- external processes runner
    agent_name -- name of pacemaker part whose metadata we want to get
    """
    name_to_list_options_type = {
        const.CLUSTER_OPTIONS: "cluster",
    }
    if agent_name not in name_to_list_options_type:
        raise UnableToGetAgentMetadata(agent_name, "Unknown agent")
    stdout, stderr, retval = runner.run(
        [
            settings.crm_attribute_exec,
            "--list-options",
            name_to_list_options_type[agent_name],
            "--output-as",
            "xml",
        ]
    )
    try:
        dom = get_api_result_dom(stdout)
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise UnableToGetAgentMetadata(
            agent_name, join_multilines([stderr, stdout])
        ) from e
    if retval != 0:
        status = get_status_from_api_result(dom)
        raise UnableToGetAgentMetadata(
            agent_name, join_multilines([status.message] + list(status.errors))
        )
    resource_agent_el = dom.find("./resource-agent")
    if resource_agent_el is None:
        raise UnableToGetAgentMetadata(
            agent_name, join_multilines([stderr, stdout])
        )
    return etree_to_str(resource_agent_el)


def _get_ocf_version(metadata: _Element) -> str:
    """
    Extract OCF version from agent metadata XML

    metadata -- metadata XML document
    """
    version = metadata.findtext("./version")
    return const.OCF_1_0 if version is None else version.strip()


def _metadata_xml_to_dom(metadata: str) -> _Element:
    """
    Parse metadata string to XML document and validate against RNG schema

    metadata -- metadata string to parse
    """
    dom = xml_fromstring(metadata)
    ocf_version = _get_ocf_version(dom)
    if ocf_version == const.OCF_1_0:
        etree.RelaxNG(file=settings.path.ocf_1_0_schema).assertValid(dom)
    elif ocf_version == const.OCF_1_1:
        etree.RelaxNG(file=settings.path.ocf_1_1_schema).assertValid(dom)
    return dom


def load_metadata(
    runner: CommandRunner, agent_name: ResourceAgentName
) -> _Element:
    """
    Return specified agent's metadata as an XML document

    runner -- external processes runner
    agent_name -- name of an agent whose metadata we want to get
    """
    try:
        return _metadata_xml_to_dom(_load_metadata_xml(runner, agent_name))
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise UnableToGetAgentMetadata(agent_name.full_name, str(e)) from e


def load_fake_agent_metadata(
    runner: CommandRunner, agent_name: FakeAgentName
) -> _Element:
    """
    Return pacemaker metadata as an XML document

    runner -- external processes runner
    agent_name -- name of pacemaker part whose metadata we want to get
    """
    try:
        return _metadata_xml_to_dom(
            _load_fake_agent_metadata_xml(runner, agent_name)
        )
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise UnableToGetAgentMetadata(agent_name, str(e)) from e


def load_fake_agent_crm_attribute_metadata_xml(
    runner: CommandRunner, agent_name: FakeAgentName
) -> _Element:
    """
    Return pacemaker metadata as an XML document

    runner -- external processes runner
    agent_name -- name of pacemaker part whose metadata we want to get
    """
    try:
        return _metadata_xml_to_dom(
            _load_fake_agent_crm_attribute_metadata_xml(runner, agent_name)
        )
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise UnableToGetAgentMetadata(agent_name, str(e)) from e


### parse metadata


def parse_metadata(
    name: ResourceAgentName, metadata: _Element
) -> Union[ResourceAgentMetadataOcf1_0, ResourceAgentMetadataOcf1_1]:
    """
    Parse XML metadata to a dataclass

    name -- name of an agent
    metadata -- metadata XML document
    """
    ocf_version = _get_ocf_version(metadata)
    if ocf_version == const.OCF_1_0:
        return _parse_agent_1_0(name, metadata)
    if ocf_version == const.OCF_1_1:
        return _parse_agent_1_1(name, metadata)
    raise UnsupportedOcfVersion(name.full_name, ocf_version)


def _parse_agent_1_0(
    name: ResourceAgentName, metadata: _Element
) -> ResourceAgentMetadataOcf1_0:
    """
    Parse OCF 1.0 XML metadata to a dataclass

    name -- name of an agent
    metadata -- metadata XML document
    """
    parameters_el = metadata.find("./parameters")
    actions_el = metadata.find("./actions")
    return ResourceAgentMetadataOcf1_0(
        name=name,
        shortdesc=_get_shortdesc(metadata) or metadata.get("shortdesc"),
        longdesc=_get_longdesc(metadata),
        parameters=(
            []
            if parameters_el is None
            else _parse_parameters_1_0(parameters_el)
        ),
        actions=([] if actions_el is None else _parse_actions_1_0(actions_el)),
    )


def _parse_agent_1_1(
    name: ResourceAgentName, metadata: _Element
) -> ResourceAgentMetadataOcf1_1:
    """
    Parse OCF 1.1 XML metadata to a dataclass

    name -- name of an agent
    metadata -- metadata XML document
    """
    parameters_el = metadata.find("./parameters")
    actions_el = metadata.find("./actions")
    return ResourceAgentMetadataOcf1_1(
        name=name,
        shortdesc=_get_shortdesc(metadata),
        longdesc=_get_longdesc(metadata),
        parameters=(
            []
            if parameters_el is None
            else _parse_parameters_1_1(parameters_el)
        ),
        actions=([] if actions_el is None else _parse_actions_1_1(actions_el)),
    )


def _parse_parameter_content(
    parameter_el: _Element,
) -> Tuple[str, Optional[str], Optional[List[str]]]:
    value_type = "string"
    default_value = None
    enum_values = None
    content_el = parameter_el.find("content")
    if content_el is not None:
        value_type = content_el.get("type", value_type)
        default_value = content_el.get("default", default_value)
        if value_type == "select":
            enum_values = [
                str(option_el.attrib["value"])
                for option_el in content_el.iterfind("./option")
            ]
    return value_type, default_value, enum_values


def _parse_parameters_1_0(
    element: _Element,
) -> List[ResourceAgentParameterOcf1_0]:
    result = []
    for parameter_el in element.iter("parameter"):
        value_type, default_value, enum_values = _parse_parameter_content(
            parameter_el
        )
        result.append(
            ResourceAgentParameterOcf1_0(
                name=str(parameter_el.attrib["name"]),
                shortdesc=_get_shortdesc(parameter_el),
                longdesc=_get_longdesc(parameter_el),
                type=value_type,
                default=default_value,
                enum_values=enum_values,
                required=parameter_el.get("required"),
                deprecated=parameter_el.get("deprecated"),
                obsoletes=parameter_el.get("obsoletes"),
                unique=parameter_el.get("unique"),
            )
        )
    return result


def _parse_parameters_1_1(
    element: _Element,
) -> List[ResourceAgentParameterOcf1_1]:
    result = []
    for parameter_el in element.iter("parameter"):
        value_type, default_value, enum_values = _parse_parameter_content(
            parameter_el
        )

        deprecated, deprecated_by, deprecated_desc = False, [], None
        deprecated_el = parameter_el.find("deprecated")
        if deprecated_el is not None:
            deprecated = True
            deprecated_by = [
                str(replaced_with_el.attrib["name"])
                for replaced_with_el in deprecated_el.iterfind("replaced-with")
            ]
            deprecated_desc = _get_desc(deprecated_el)

        result.append(
            ResourceAgentParameterOcf1_1(
                name=str(parameter_el.attrib["name"]),
                shortdesc=_get_shortdesc(parameter_el),
                longdesc=_get_longdesc(parameter_el),
                type=value_type,
                default=default_value,
                enum_values=enum_values,
                required=parameter_el.get("required"),
                advanced=parameter_el.get("advanced"),
                deprecated=deprecated,
                deprecated_by=deprecated_by,
                deprecated_desc=deprecated_desc,
                unique_group=parameter_el.get("unique-group"),
                reloadable=parameter_el.get("reloadable"),
            )
        )
    return result


def _parse_actions_1_0(element: _Element) -> List[ResourceAgentActionOcf1_0]:
    return [
        ResourceAgentActionOcf1_0(
            name=str(action.attrib["name"]),
            timeout=action.get("timeout"),
            interval=action.get("interval"),
            role=action.get("role"),
            start_delay=action.get("start-delay"),
            depth=action.get("depth"),
            automatic=action.get("automatic"),
            on_target=action.get("on_target"),
        )
        for action in element.iter("action")
    ]


def _parse_actions_1_1(element: _Element) -> List[ResourceAgentActionOcf1_1]:
    return [
        ResourceAgentActionOcf1_1(
            name=str(action.attrib["name"]),
            timeout=action.get("timeout"),
            interval=action.get("interval"),
            role=action.get("role"),
            start_delay=action.get("start-delay"),
            depth=action.get("depth"),
            automatic=action.get("automatic"),
            on_target=action.get("on_target"),
        )
        for action in element.iter("action")
    ]


def _get_desc(element: _Element) -> Optional[str]:
    return _get_text_from_dom_element(element.find("desc"))


def _get_shortdesc(element: _Element) -> Optional[str]:
    return _get_text_from_dom_element(element.find("shortdesc"))


def _get_longdesc(element: _Element) -> Optional[str]:
    return _get_text_from_dom_element(element.find("longdesc"))


def _get_text_from_dom_element(element: Optional[_Element]) -> Optional[str]:
    return (
        None
        if element is None or element.text is None
        else str(element.text).strip()
    )
