from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib import reports
from pcs.lib.errors import LibraryError
from pcs.lib.node import NodeAddresses, NodeAddressesList

class ClusterConfFacade(object):
    """
    Provides high level access to a corosync.conf file
    """

    @classmethod
    def from_string(cls, config_string):
        """
        Parse cluster.conf config and create a facade around it

        config_string -- cluster.conf file content as string
        """
        try:
            return cls(etree.fromstring(config_string))
        except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
            raise LibraryError(reports.cluster_conf_invalid_format(str(e)))

    def __init__(self, parsed_config):
        """
        Create a facade around a parsed cluster.conf config file
        parsed_config parsed cluster.conf config
        """
        self._config = parsed_config

    @property
    def config(self):
        return self._config

    def get_cluster_name(self):
        return self.config.get("name", "")

    def get_nodes(self):
        """
        Get all defined nodes
        """
        result = NodeAddressesList()
        for node in self.config.findall("./clusternodes/clusternode"):
            altname = node.find("altname")
            result.append(NodeAddresses(
                ring0=node.get("name"),
                ring1=altname.get("name") if altname is not None else None,
                name=None,
                id=node.get("nodeid")
            ))
        return result

