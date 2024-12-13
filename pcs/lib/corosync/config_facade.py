from typing import (
    Any,
    Generator,
    Mapping,
    Optional,
    Sequence,
    TypeVar,
    overload,
)

from pcs import settings
from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.common.types import (
    StringCollection,
    StringSequence,
)
from pcs.lib.corosync import constants
from pcs.lib.corosync.config_parser import Section
from pcs.lib.corosync.node import (
    CorosyncNode,
    CorosyncNodeAddress,
)
from pcs.lib.errors import LibraryError
from pcs.lib.interface.config import FacadeInterface

_KNET_COMPRESSION_OPTIONS_PREFIX = "knet_compression_"
_KNET_CRYPTO_OPTIONS_PREFIX = "crypto_"

T = TypeVar("T")


class ConfigFacade(FacadeInterface):
    # pylint: disable=too-many-public-methods
    """
    Provides high level access to a corosync config file
    """

    @classmethod
    def create(
        cls,
        cluster_name: str,
        node_list: Sequence[Mapping[str, Any]],
        transport: str,
    ) -> "ConfigFacade":
        """
        Create a minimal config

        cluster_name -- a name of a cluster
        node_list -- list of dict: name, addrs
        transport -- corosync transport
        """
        root = Section("")
        totem_section = Section("totem")
        nodelist_section = Section("nodelist")
        quorum_section = Section("quorum")
        logging_section = Section("logging")
        root.add_section(totem_section)
        root.add_section(nodelist_section)
        root.add_section(quorum_section)
        root.add_section(logging_section)

        totem_section.add_attribute("version", "2")
        totem_section.add_attribute("cluster_name", cluster_name)
        totem_section.add_attribute("transport", transport)
        quorum_section.add_attribute("provider", "corosync_votequorum")
        logging_section.add_attribute("to_logfile", "yes")
        logging_section.add_attribute("logfile", settings.corosync_log_file)
        logging_section.add_attribute("to_syslog", "yes")
        logging_section.add_attribute("timestamp", "on")

        for node_id, node_options in enumerate(node_list, 1):
            nodelist_section.add_section(
                cls._create_node_section(
                    node_id, node_options, list(range(constants.LINKS_MAX))
                )
            )

        self = cls(root)
        # pylint: disable=protected-access
        self.__update_two_node()

        return self

    def __init__(self, parsed_config: Section):
        """
        Create a facade around a parsed corosync config file

        parsed_config -- parsed corosync config
        """
        super().__init__(parsed_config)
        # set to True if changes cannot be applied on running cluster
        self._need_stopped_cluster = False
        # set to True if qdevice reload is required to apply changes
        self._need_qdevice_reload = False

    @property
    def need_stopped_cluster(self) -> bool:
        return self._need_stopped_cluster

    @property
    def need_qdevice_reload(self) -> bool:
        return self._need_qdevice_reload

    def get_cluster_name(self) -> str:
        return self._get_option_value("totem", "cluster_name", "")

    def get_cluster_uuid(self) -> Optional[str]:
        return self._get_option_value("totem", "cluster_uuid")

    def set_cluster_uuid(self, cluster_uuid: str) -> None:
        """
        Updates or adds a cluster UUID, assumes that UUID can be rewritten

        cluster_uuid - new cluster UUID
        """
        totem_section_list = self.__ensure_section(self.config, "totem")
        self.__set_section_options(
            totem_section_list, {"cluster_uuid": cluster_uuid}
        )
        self.__remove_empty_sections(self.config)

    # To get a list of nodenames use pcs.lib.node.get_existing_nodes_names

    def get_nodes(self) -> list[CorosyncNode]:
        """
        Get all defined nodes
        """
        result = []
        for nodelist in self.config.get_sections("nodelist"):
            for node_section in nodelist.get_sections("node"):
                # first, load all the nodes key-value pairs so that the last
                # value for each key wins
                node_data = self._get_node_data(node_section)
                if not node_data:
                    continue
                # add the node data to the resulting list
                result.append(
                    CorosyncNode(
                        node_data.get("name"),
                        [
                            CorosyncNodeAddress(
                                node_data[f"ring{i}_addr"], str(i)
                            )
                            for i in range(constants.LINKS_MAX)
                            if node_data.get(f"ring{i}_addr")
                        ],
                        node_data.get("nodeid"),
                    )
                )
        return result

    def _get_used_nodeid_list(self) -> list[str]:
        used_ids = []
        for nodelist in self.config.get_sections("nodelist"):
            for node_section in nodelist.get_sections("node"):
                used_ids.extend(
                    [attr[1] for attr in node_section.get_attributes("nodeid")]
                )
        return used_ids

    @staticmethod
    def _get_nodeid_generator(
        used_ids: StringSequence,
    ) -> Generator[int, None, None]:
        # used_ids content is extracted from corosync.conf. We keep it as
        # strings to avoid potential issues if loaded nodeid is not a number.
        used_ids_set = set(used_ids)
        current_id = 1
        while True:
            current_id_str = str(current_id)
            if current_id_str not in used_ids_set:
                yield current_id
                used_ids_set.add(current_id_str)
            current_id += 1

    @staticmethod
    def _get_node_data(node_section: Section) -> dict[str, str]:
        return {
            attr_name: attr_value
            for attr_name, attr_value in node_section.get_attributes()
            if attr_name in constants.NODE_OPTIONS
        }

    def get_used_linknumber_list(self) -> list[int]:
        for nodelist_section in self.config.get_sections("nodelist"):
            for node_section in nodelist_section.get_sections("node"):
                node_data = self._get_node_data(node_section)
                if not node_data:
                    continue
                return [
                    i
                    for i in range(constants.LINKS_MAX)
                    if node_data.get(f"ring{i}_addr")
                ]
        return []

    @staticmethod
    def _create_node_section(
        node_id: int,
        node_options: Mapping[str, Any],
        link_ids: Sequence[int],
    ) -> Section:
        node_section = Section("node")
        for link_id, link_addr in zip(
            link_ids, node_options["addrs"], strict=False
        ):
            node_section.add_attribute(f"ring{link_id}_addr", link_addr)
        node_section.add_attribute("name", str(node_options["name"]))
        node_section.add_attribute("nodeid", str(node_id))
        return node_section

    def add_nodes(self, node_list: Sequence[Mapping[str, Any]]) -> None:
        """
        Add nodes to a config with a nonempty nodelist

        node_list -- list of dict: name, addrs
        """
        nodelist_section = self.__ensure_section(self.config, "nodelist")[-1]
        node_id_generator = self._get_nodeid_generator(
            self._get_used_nodeid_list()
        )
        for node_options in node_list:
            nodelist_section.add_section(
                self._create_node_section(
                    next(node_id_generator),
                    node_options,
                    self.get_used_linknumber_list(),
                )
            )
        self.__update_two_node()

    def remove_nodes(self, node_name_list: StringCollection) -> None:
        """
        Remove nodes from a config

        node_name_list -- names of nodes to remove
        """
        for nodelist_section in self.config.get_sections("nodelist"):
            for node_section in nodelist_section.get_sections("node"):
                node_data = self._get_node_data(node_section)
                if node_data.get("name") in node_name_list:
                    nodelist_section.del_section(node_section)
        self.__remove_empty_sections(self.config)
        self.__update_two_node()

    def create_link_list(self, link_list: Sequence[Mapping[str, str]]) -> None:
        """
        Add a link list to a config without one

        link_list -- list of dicts with link_list options
        """
        available_link_numbers = list(range(constants.LINKS_KNET_MAX))
        linknumber_missing = []
        links = []

        for link in link_list:
            if "linknumber" in link:
                try:
                    available_link_numbers.remove(int(link["linknumber"]))
                except ValueError as e:
                    raise AssertionError(f"Invalid link number: {e}") from e
                links.append(dict(link))
            else:
                linknumber_missing.append(link)

        for link_missing_linknumber in linknumber_missing:
            link = dict(link_missing_linknumber)
            try:
                link["linknumber"] = str(available_link_numbers.pop(0))
            except IndexError as e:
                raise AssertionError(
                    f"Link number no longer available: {e}"
                ) from e
            links.append(link)

        for link in sorted(links, key=lambda item: item["linknumber"]):
            self._set_link_options(link)

    def add_link(
        self, node_addr_map: Mapping[str, str], options: Mapping[str, str]
    ) -> None:
        """
        Add a new link to nodelist and create an interface section with options

        node_addr_map -- key: node name, value: node address for the link
        link_options -- link options
        """
        # Get a linknumber
        options_updated = dict(options)
        if "linknumber" in options_updated:
            linknumber = options_updated["linknumber"]
        else:
            linknumber = None
            used_links = self.get_used_linknumber_list()
            available_links = range(constants.LINKS_KNET_MAX)
            for candidate in available_links:
                if candidate not in used_links:
                    linknumber = str(candidate)
                    break
            if linknumber is None:
                raise AssertionError("No link number available")
            options_updated["linknumber"] = linknumber

        # Add addresses
        for nodelist_section in self.config.get_sections("nodelist"):
            for node_section in nodelist_section.get_sections("node"):
                node_name = self._get_node_data(node_section).get("name")
                if node_name is not None and node_name in node_addr_map:
                    node_section.add_attribute(
                        f"ring{linknumber}_addr", node_addr_map[node_name]
                    )

        # Add link options.
        if options_updated:
            self._set_link_options(options_updated)

    def _set_link_options(
        self,
        options: Mapping[str, str],
        interface_section_list: Optional[Sequence[Section]] = None,
        linknumber: Optional[str] = None,
    ) -> None:
        """
        Add a new or change an existing interface section with link options

        options -- link options
        interface_section_list -- list of existing sections to be changed
        linknumber -- linknumber to set to a newly created section
        """
        # If the only option is "linknumber" then there is no point in adding
        # the options at all. It would mean there are no options for the
        # particular link.
        if not [name for name in options if name != "linknumber"]:
            return

        options_to_set = self.__translate_link_options(options)
        if not interface_section_list:
            new_section = Section("interface")
            if linknumber:
                new_section.set_attribute("linknumber", linknumber)
            totem_section = self.__ensure_section(self.config, "totem")[-1]
            totem_section.add_section(new_section)
            interface_section_list = [new_section]
        self.__set_section_options(interface_section_list, options_to_set)
        self.__remove_empty_sections(self.config)

    def remove_links(self, link_list: StringCollection) -> None:
        """
        Remove links from nodelist and relevant interface sections from totem

        link_list -- list of linknumbers to be removed
        """
        # Do not break when the interface / address is found to be sure to
        # remove all of them (config format allows to have more interface
        # sections / addresses for one link).
        for totem_section in self.config.get_sections("totem"):
            for interface_section in totem_section.get_sections("interface"):
                interface_number = interface_section.get_attribute_value(
                    "linknumber",
                    # if no linknumber is set, corosync treats it as 0
                    "0",
                )
                if interface_number in link_list:
                    totem_section.del_section(interface_section)
        for link_number in link_list:
            for nodelist_section in self.config.get_sections("nodelist"):
                for node_section in nodelist_section.get_sections("node"):
                    node_section.del_attributes_by_name(
                        f"ring{link_number}_addr"
                    )
        self.__remove_empty_sections(self.config)

    def update_link(
        self,
        linknumber: str,
        node_addr_map: Mapping[str, str],
        options: Mapping[str, str],
    ) -> None:
        """
        Change an existing link - node addresses and/or link options

        linknumber -- link to be changed
        node_addr_map -- key: node name, value: node address for the link
        link_options -- link options
        """
        self._need_stopped_cluster = True
        # change addresses
        if node_addr_map:
            for nodelist_section in self.config.get_sections("nodelist"):
                for node_section in nodelist_section.get_sections("node"):
                    node_name = self._get_node_data(node_section).get("name")
                    if node_name is not None and node_name in node_addr_map:
                        node_section.set_attribute(
                            f"ring{linknumber}_addr", node_addr_map[node_name]
                        )
        # make sure we do not change the linknumber
        options_without_linknumber = dict(options)
        if "linknumber" in options_without_linknumber:
            del options_without_linknumber["linknumber"]
        # change options
        if options_without_linknumber:
            target_interface_section_list = [
                interface_section
                for totem_section in self.config.get_sections("totem")
                for interface_section in totem_section.get_sections("interface")
                if (
                    linknumber
                    ==
                    # if no linknumber is set, corosync treats it as 0
                    interface_section.get_attribute_value("linknumber", "0")
                )
            ]
            self._set_link_options(
                options_without_linknumber,
                interface_section_list=target_interface_section_list,
                linknumber=linknumber,
            )
        self.__remove_empty_sections(self.config)

    def get_links_options(self) -> dict[str, dict[str, str]]:
        """
        Get all links' options in a dict: key=linknumber value=dict of options
        """
        transport = self.get_transport()
        allowed_options = (
            constants.LINK_OPTIONS_UDP
            if transport in constants.TRANSPORTS_UDP
            else constants.LINK_OPTIONS_KNET_COROSYNC
        )
        raw_options: dict[str, dict[str, str]] = {}
        for totem_section in self.config.get_sections("totem"):
            for interface_section in totem_section.get_sections("interface"):
                # if no linknumber is set, corosync treats it as 0
                linknumber = interface_section.get_attribute_value(
                    "linknumber", "0"
                )
                if linknumber not in raw_options:
                    raw_options[linknumber] = {}
                for name, value in interface_section.get_attributes():
                    if name in allowed_options:
                        raw_options[linknumber][name] = value
                # make sure the linknumber is present for knet
                if transport in constants.TRANSPORTS_KNET:
                    raw_options[linknumber]["linknumber"] = linknumber
        return {
            linknumber: self.__translate_link_options(options, False)
            for linknumber, options in raw_options.items()
        }

    def get_transport(self) -> str:
        transport = self._get_option_value("totem", "transport")
        return transport if transport else constants.TRANSPORT_DEFAULT

    def get_ip_version(self) -> str:
        ip_version = self._get_option_value("totem", "ip_version")
        if ip_version:
            return ip_version
        if self.get_transport() == "udp":
            return constants.IP_VERSION_4
        return constants.IP_VERSION_64

    @overload
    def _get_option_value(
        self, section: str, option: str, default: str = ""
    ) -> str:
        pass

    @overload
    def _get_option_value(
        self, section: str, option: str, default: Optional[str] = None
    ) -> Optional[str]:
        pass

    def _get_option_value(
        self, section: str, option: str, default: Optional[str] = None
    ) -> Optional[str]:
        for sec in self.config.get_sections(section):
            default = sec.get_attribute_value(option, default)
        return default

    def _is_changed(
        self, section: str, option_name: str, new_value: Optional[str]
    ) -> bool:
        if new_value is None:
            return False
        old_value = self._get_option_value(section, option_name)
        # old_value is not present or empty and new_value is empty
        if not old_value and not new_value:
            return False
        return old_value != new_value

    def set_transport_options(
        self,
        transport_options: Mapping[str, str],
        compression_options: Mapping[str, str],
        crypto_options: Mapping[str, str],
    ) -> None:
        """
        Set transport options for transport type currently used

        generic_options -- generic transport options
        compression_options -- compression options
        crypto_options -- crypto options
        """
        if any(
            self._is_changed("totem", opt, transport_options.get(opt))
            for opt in constants.TRANSPORT_RUNTIME_CHANGE_BANNED_OPTIONS
        ):
            self._need_stopped_cluster = True
        transport_type = self.get_transport()
        if transport_type in constants.TRANSPORTS_KNET:
            self._set_transport_knet_options(
                transport_options, compression_options, crypto_options
            )
        elif transport_type in constants.TRANSPORTS_UDP:
            self._set_transport_udp_options(transport_options)

    def _set_transport_udp_options(self, options: Mapping[str, str]) -> None:
        """
        Set transport options for udp transports

        options -- transport options
        """
        totem_section_list = self.__ensure_section(self.config, "totem")
        self.__set_section_options(totem_section_list, options)
        self.__remove_empty_sections(self.config)

    def _set_transport_knet_options(
        self,
        generic_options: Mapping[str, str],
        compression_options: Mapping[str, str],
        crypto_options: Mapping[str, str],
    ) -> None:
        """
        Set transport options for knet transport

        generic_options -- generic transport options
        compression_options -- compression options
        crypto_options -- crypto options
        """
        totem_section_list = self.__ensure_section(self.config, "totem")
        self.__set_section_options(totem_section_list, generic_options)
        self.__set_section_options(
            totem_section_list,
            _add_prefix_to_dict_keys(
                _KNET_COMPRESSION_OPTIONS_PREFIX, compression_options
            ),
        )
        self.__set_section_options(
            totem_section_list,
            _add_prefix_to_dict_keys(
                _KNET_CRYPTO_OPTIONS_PREFIX, crypto_options
            ),
        )
        self.__remove_empty_sections(self.config)

    def _filter_options(
        self,
        section_name: str,
        allowed_options: StringCollection,
        prefix: str = "",
    ) -> dict[str, str]:
        options = {}
        for section in self.config.get_sections(section_name):
            for name, value in section.get_attributes():
                if (
                    name.startswith(prefix)
                    and name[len(prefix) :] in allowed_options
                ):
                    options[name[len(prefix) :]] = value
        return options

    def get_transport_options(self) -> dict[str, str]:
        """
        Get configurable generic transport options
        """
        transport_type = self.get_transport()
        if transport_type in constants.TRANSPORTS_KNET:
            return self._filter_options(
                "totem", constants.TRANSPORT_KNET_GENERIC_OPTIONS
            )
        if transport_type in constants.TRANSPORTS_UDP:
            return self._filter_options(
                "totem", constants.TRANSPORT_UDP_GENERIC_OPTIONS
            )
        return {}

    def get_compression_options(self) -> dict[str, str]:
        """
        Get configurable compression options
        """
        return self._filter_options(
            "totem",
            constants.TRANSPORT_KNET_COMPRESSION_OPTIONS,
            _KNET_COMPRESSION_OPTIONS_PREFIX,
        )

    def get_crypto_options(self) -> dict[str, str]:
        """
        Get configurable crypto options
        """
        return self._filter_options(
            "totem",
            constants.TRANSPORT_KNET_CRYPTO_OPTIONS,
            _KNET_CRYPTO_OPTIONS_PREFIX,
        )

    def set_totem_options(self, options: Mapping[str, str]) -> None:
        """
        Set options in the "totem" section

        options -- totem options
        """
        totem_section_list = self.__ensure_section(self.config, "totem")
        self.__set_section_options(totem_section_list, options)
        self.__remove_empty_sections(self.config)
        # The totem section contains quite a lot of options. Pcs reduces the
        # number by moving some of them virtually into other "sections". The
        # move is only visible for pcs users (in CLI, web UI), those moved
        # options are still written to the totem section. The options which pcs
        # keeps in the totem section for users do not currently need the
        # cluster to be stopped when updating them.
        # Note: all options in totem section supported by pcs are runtime
        # configurable.

    def get_totem_options(self) -> dict[str, str]:
        """
        Get configurable totem options
        """
        return self._filter_options("totem", constants.TOTEM_OPTIONS)

    def set_quorum_options(self, options: Mapping[str, str]) -> None:
        """
        Set options in the "quorum" section

        options -- quorum options
        """
        quorum_section_list = self.__ensure_section(self.config, "quorum")
        self.__set_section_options(quorum_section_list, options)
        self.__update_two_node()
        self.__remove_empty_sections(self.config)
        self._need_stopped_cluster = True

    def get_quorum_options(self) -> dict[str, str]:
        """
        Get configurable options from the "quorum" section
        """
        return self._filter_options("quorum", constants.QUORUM_OPTIONS)

    def is_enabled_auto_tie_breaker(self) -> bool:
        """
        Returns True if auto tie braker option is enabled, False otherwise.
        """
        return self._get_option_value("quorum", "auto_tie_breaker", "0") == "1"

    def get_quorum_device_model(self) -> Optional[str]:
        """
        Get quorum device model from quorum.device section
        """
        models_found = []
        for quorum in self.config.get_sections("quorum"):
            for device in quorum.get_sections("device"):
                model_list = device.get_attributes("model")
                if model_list:
                    models_found.append(model_list[-1][1])
        return models_found[-1] if models_found else None

    def get_quorum_device_settings(
        self,
    ) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
        """
        Get model, generic and heuristics options from quorum.device section
        """
        model = self.get_quorum_device_model()
        if model is None:
            return {}, {}, {}

        model_options: dict[str, dict[str, str]] = {}
        generic_options: dict[str, str] = {}
        heuristics_options: dict[str, str] = {}
        for quorum in self.config.get_sections("quorum"):
            for device in quorum.get_sections("device"):
                generic_options.update(
                    {
                        name: value
                        for name, value in device.get_attributes()
                        if name != "model"
                    }
                )
                for subsection in device.get_sections():
                    if subsection.name == "heuristics":
                        heuristics_options.update(subsection.get_attributes())
                        continue
                    if subsection.name not in model_options:
                        model_options[subsection.name] = {}
                    model_options[subsection.name].update(
                        subsection.get_attributes()
                    )
        return (
            model_options.get(model, {}),
            generic_options,
            heuristics_options,
        )

    def is_quorum_device_heuristics_enabled_with_no_exec(self) -> bool:
        if not self.get_quorum_device_model():
            return False
        heuristics_options = self.get_quorum_device_settings()[2]
        regexp = constants.QUORUM_DEVICE_HEURISTICS_EXEC_NAME_RE
        exec_found = False
        for name, value in heuristics_options.items():
            if value and regexp.match(name):
                exec_found = True
                break
        return not exec_found and heuristics_options.get("mode") in (
            "on",
            "sync",
        )

    def add_quorum_device(
        self,
        model: str,
        model_options: Mapping[str, str],
        generic_options: Mapping[str, str],
        heuristics_options: Mapping[str, str],
    ) -> None:
        # pylint: disable=too-many-locals
        """
        Add quorum device configuration

        model -- quorum device model
        model_options -- model specific options
        generic_options -- generic quorum device options
        heuristics_options -- heuristics options
        """
        if self.get_quorum_device_model():
            raise LibraryError(
                ReportItem.error(reports.messages.QdeviceAlreadyDefined())
            )

        # configuration cleanup
        remove_need_stopped_cluster = {
            name: ""
            for name in constants.QUORUM_OPTIONS_INCOMPATIBLE_WITH_QDEVICE
        }
        # remove old device settings
        quorum_section_list = self.__ensure_section(self.config, "quorum")
        for quorum in quorum_section_list:
            for device in quorum.get_sections("device"):
                quorum.del_section(device)
            for name, value in quorum.get_attributes():
                if name in remove_need_stopped_cluster and value not in [
                    "",
                    "0",
                ]:
                    self._need_stopped_cluster = True
        # remove conflicting quorum options
        attrs_to_remove = {
            "allow_downscale": "",
            "two_node": "",
        }
        attrs_to_remove.update(remove_need_stopped_cluster)
        self.__set_section_options(quorum_section_list, attrs_to_remove)
        # remove nodes' votes
        for nodelist in self.config.get_sections("nodelist"):
            for node_section in nodelist.get_sections("node"):
                node_section.del_attributes_by_name("quorum_votes")

        # add new configuration
        quorum = quorum_section_list[-1]
        new_device = Section("device")
        quorum.add_section(new_device)
        self.__set_section_options([new_device], generic_options)
        new_device.set_attribute("model", model)
        new_model = Section(model)
        self.__set_section_options([new_model], model_options)
        new_device.add_section(new_model)
        new_heuristics = Section("heuristics")
        self.__set_section_options([new_heuristics], heuristics_options)
        new_device.add_section(new_heuristics)

        self.__update_qdevice_votes()
        self.__update_two_node()
        self.__remove_empty_sections(self.config)

    def update_quorum_device(
        self,
        model_options: Mapping[str, str],
        generic_options: Mapping[str, str],
        heuristics_options: Mapping[str, str],
    ) -> None:
        """
        Update existing quorum device configuration

        model_options -- model specific options
        generic_options -- generic quorum device options
        heuristics_options -- heuristics options
        """
        model = self.get_quorum_device_model()
        if not model:
            raise LibraryError(
                ReportItem.error(reports.messages.QdeviceNotDefined())
            )

        # set new configuration
        device_sections = []
        model_sections = []
        heuristics_sections = []

        for quorum in self.config.get_sections("quorum"):
            device_sections.extend(quorum.get_sections("device"))
            for device in quorum.get_sections("device"):
                model_sections.extend(device.get_sections(model))
                heuristics_sections.extend(device.get_sections("heuristics"))
        # we know device sections exist, otherwise the function would exit at
        # get_quorum_device_model line above
        if not model_sections:
            new_model = Section(model)
            device_sections[-1].add_section(new_model)
            model_sections.append(new_model)
        if not heuristics_sections:
            new_heuristics = Section("heuristics")
            device_sections[-1].add_section(new_heuristics)
            heuristics_sections.append(new_heuristics)

        self.__set_section_options(device_sections, generic_options)
        self.__set_section_options(model_sections, model_options)
        self.__set_section_options(heuristics_sections, heuristics_options)

        self.__update_qdevice_votes()
        self.__update_two_node()
        self.__remove_empty_sections(self.config)
        self._need_qdevice_reload = True

    def remove_quorum_device_heuristics(self) -> None:
        """
        Remove quorum device heuristics configuration
        """
        if not self.get_quorum_device_model():
            raise LibraryError(
                ReportItem.error(reports.messages.QdeviceNotDefined())
            )
        for quorum in self.config.get_sections("quorum"):
            for device in quorum.get_sections("device"):
                for heuristics in device.get_sections("heuristics"):
                    device.del_section(heuristics)
        self.__remove_empty_sections(self.config)
        self._need_qdevice_reload = True

    def remove_quorum_device(self) -> None:
        """
        Remove all quorum device configuration
        """
        if not self.get_quorum_device_model():
            raise LibraryError(
                ReportItem.error(reports.messages.QdeviceNotDefined())
            )
        for quorum in self.config.get_sections("quorum"):
            for device in quorum.get_sections("device"):
                quorum.del_section(device)
        self.__update_two_node()
        self.__remove_empty_sections(self.config)

    def __update_two_node(self) -> None:
        # get relevant status
        has_quorum_device = self.get_quorum_device_model() is not None
        has_two_nodes = len(self.get_nodes()) == 2
        auto_tie_breaker = self.is_enabled_auto_tie_breaker()
        # update two_node
        if has_two_nodes and not auto_tie_breaker and not has_quorum_device:
            quorum_section_list = self.__ensure_section(self.config, "quorum")
            self.__set_section_options(quorum_section_list, {"two_node": "1"})
        else:
            for quorum in self.config.get_sections("quorum"):
                quorum.del_attributes_by_name("two_node")

    def __update_qdevice_votes(self) -> None:
        # ffsplit won't start if votes is missing or not set to 1
        # for other algorithms it's required not to put votes at all
        model = None
        algorithm = None
        device_sections = []
        for quorum in self.config.get_sections("quorum"):
            for device in quorum.get_sections("device"):
                device_sections.append(device)
                model = device.get_attribute_value("model", model)
        for device in device_sections:
            for model_section in device.get_sections(model):
                algorithm = model_section.get_attribute_value(
                    "algorithm", algorithm
                )
        if model == "net":
            if algorithm == "ffsplit":
                self.__set_section_options(device_sections, {"votes": "1"})
            else:
                self.__set_section_options(device_sections, {"votes": ""})

    @staticmethod
    def __set_section_options(
        section_list: Sequence[Section],
        options: Mapping[str, str],
    ) -> None:
        for section in section_list[:-1]:
            for name in options:
                section.del_attributes_by_name(name)
        for name, value in sorted(options.items()):
            if value == "":
                section_list[-1].del_attributes_by_name(name)
            else:
                section_list[-1].set_attribute(name, value)

    @staticmethod
    def __ensure_section(
        parent_section: Section, section_name: str
    ) -> list[Section]:
        section_list = parent_section.get_sections(section_name)
        if not section_list:
            new_section = Section(section_name)
            parent_section.add_section(new_section)
            section_list.append(new_section)
        return section_list

    def __remove_empty_sections(self, parent_section: Section) -> None:
        for section in parent_section.get_sections():
            self.__remove_empty_sections(section)
            if section.empty or (
                section.name == "interface"
                and list(section.get_attributes_dict().keys()) == ["linknumber"]
            ):
                parent_section.del_section(section)

    @staticmethod
    def __translate_link_options(
        options: Mapping[str, str], input_to_corosync: bool = True
    ) -> dict[str, str]:
        pairs = constants.LINK_OPTIONS_KNET_TRANSLATION
        if input_to_corosync:
            translate_map = {pair[0]: pair[1] for pair in pairs}
        else:
            translate_map = {pair[1]: pair[0] for pair in pairs}
        result = {
            translate_map.get(name, name): value
            for name, value in options.items()
        }

        if "broadcast" in result:
            if input_to_corosync:
                # If broadcast == 1, transform it to broadcast == yes. If this
                # is called from an update where broadcast is being disabled,
                # remove broadcast from corosync.conf. Else do not put the
                # option to the config at all. From man corosync.conf, there is
                # only one allowed value: "yes".
                if result["broadcast"] in ("1", 1):
                    result["broadcast"] = "yes"
                elif result["broadcast"] in ("0", 0, ""):
                    result["broadcast"] = ""
                else:
                    del result["broadcast"]
            # When displaying config to users, do the opposite
            # transformation: only "yes" is allowed.
            elif result["broadcast"] == "yes":
                result["broadcast"] = "1"
            else:
                del result["broadcast"]

        return result


def _add_prefix_to_dict_keys(
    prefix: str, data: Mapping[str, T]
) -> dict[str, T]:
    return {f"{prefix}{key}": value for key, value in data.items()}
