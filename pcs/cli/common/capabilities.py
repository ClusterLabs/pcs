import os.path
from textwrap import dedent
from lxml import etree

from pcs import settings
from pcs.cli.common.console_report import error
from pcs.common.tools import xml_fromstring


def get_capabilities_definition():
    """
    Read and parse capabilities file

    The point is to return all data in python structures for further processing.
    """
    filename = os.path.join(settings.pcsd_exec_location, "capabilities.xml")
    try:
        with open(filename, mode="r") as file_:
            capabilities_xml = xml_fromstring(file_.read())
    except (EnvironmentError, etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise error(
            "Cannot read capabilities definition file '{0}': '{1}'"
            .format(filename, str(e))
        )
    capabilities = []
    for feat_xml in capabilities_xml.findall(".//capability"):
        feat = dict(feat_xml.attrib)
        desc = feat_xml.find("./description")
        # dedent and strip remove indentation in the XML file
        feat["description"] = "" if desc is None else dedent(desc.text).strip()
        capabilities.append(feat)
    return capabilities

def get_pcs_capabilities():
    """
    Get pcs capabilities form the capabilities file
    """
    return [
        {
            "id": feat["id"],
            "description": feat["description"],
        }
        for feat in get_capabilities_definition()
        if feat["in-pcs"] == "1"
    ]
