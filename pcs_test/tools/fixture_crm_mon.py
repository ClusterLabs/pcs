from lxml import etree

from pcs_test.tools.xml import etree_to_str


def error_xml_not_connected():
    return error_xml(
        102,
        "Not connected",
        ["crm_mon: Error: cluster is not available on this node"],
    )


def error_xml(code, message, errors=()):
    dom = etree.Element(
        "pacemaker-result",
        {
            "api-version": "2.3",
            "request": "crm_mon --output-as xml",
        },
    )
    status_el = etree.SubElement(
        dom, "status", {"code": str(code), "message": message}
    )
    if errors:
        errors_el = etree.SubElement(status_el, "errors")
        for error in errors:
            etree.SubElement(errors_el, "error").text = error
    return etree_to_str(dom)


def complete_state(state_xml, resources_xml=None, nodes_xml=None):
    state_dom = etree.fromstring(state_xml)

    if resources_xml:
        resources_dom = etree.fromstring(resources_xml)
        resources_element = state_dom.find("./resources")
        if resources_element is None:
            raise AssertionError(
                "crm_mon.xml template is missing 'resources' element"
            )
        for child in _complete_state_resources(resources_dom).getchildren():
            resources_element.append(child)

    if nodes_xml:
        nodes_dom = etree.fromstring(nodes_xml)
        nodes_element = state_dom.find("./nodes")
        if nodes_element is None:
            raise AssertionError(
                "crm_mon.xml template is missing 'nodes' element"
            )
        for child in _complete_state_nodes(nodes_dom).getchildren():
            nodes_element.append(child)

    # set correct number of nodes and resources into the status
    resources_count = len(
        state_dom.xpath(
            " | ".join(
                [
                    "./resources/bundle",
                    "./resources/clone",
                    "./resources/group",
                    "./resources/resource",
                ]
            )
        )
    )
    nodes_count = len(state_dom.findall("./nodes/node"))
    state_dom.find("./summary/nodes_configured").set("number", str(nodes_count))
    state_dom.find("./summary/resources_configured").set(
        "number", str(resources_count)
    )

    return state_dom


def _complete_state_resources(resources_status):
    for resource in resources_status.iterfind(".//resource"):
        _default_element_attributes(
            resource,
            {
                "active": "true",
                "failed": "false",
                "failure_ignored": "false",
                "managed": "true",
                "nodes_running_on": "1",
                "orphaned": "false",
                "removed": "false",
                "resource_agent": "ocf::pacemaker:Dummy",
                "role": "Started",
            },
        )
    for group in resources_status.xpath(".//group"):
        _default_element_attributes(
            group,
            {
                "disabled": "false",
                "managed": "true",
            },
        )
    for clone in resources_status.xpath(".//clone"):
        _default_element_attributes(
            clone,
            {
                "disabled": "false",
                "failed": "false",
                "failure_ignored": "false",
            },
        )
    for bundle in resources_status.xpath(".//bundle"):
        _default_element_attributes(
            bundle,
            {
                "failed": "false",
                "image": "image:name",
                "type": "docker",
                "unique": "false",
            },
        )
    return resources_status


def _complete_state_nodes(nodes_status):
    for node in nodes_status.iterfind("./node"):
        _default_element_attributes(
            node,
            {
                "expected_up": "true",
                "is_dc": "false",
                "maintenance": "false",
                "online": "true",
                "pending": "false",
                "resources_running": "0",
                "shutdown": "false",
                "standby": "false",
                "standby_onfail": "false",
                "type": "member",
                "unclean": "false",
            },
        )
    return nodes_status


def _default_element_attributes(element, default_attributes):
    for name, value in default_attributes.items():
        if name not in element.attrib:
            element.attrib[name] = value
