from typing import (
    cast,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
)

from pcs import settings
from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.lib.corosync import config_parser, constants, node
from pcs.lib.errors import LibraryError
from pcs.lib.interface.config import FacadeInterface


_KNET_COMPRESSION_OPTIONS_PREFIX = "knet_compression_"
_KNET_CRYPTO_OPTIONS_PREFIX = "crypto_"


class ConfigFacade(FacadeInterface):
    # pylint: disable=too-many-public-methods
    """
    Provides high level access to a corosync config file
    """

    @classmethod
    def from_string(cls, config_string):
        """
        Parse corosync config and create a facade around it
        config_string corosync config text
        """
        try:
            return cls(config_parser.parse_string(config_string))
        except config_parser.CorosyncConfParserException as e:
            raise LibraryError(
                ReportItem.error(
                    config_parser.parser_exception_to_report_msg(e)
                )
            ) from e

    @classmethod
    def create(cls, cluster_name, node_list, transport):
        """
        Create a minimal config

        string cluster_name -- a name of a cluster
        list node_list -- list of dict: name, addrs
        string transport -- corosync transport
        """
        root = config_parser.Section("")
        totem_section = config_parser.Section("totem")
        nodelist_section = config_parser.Section("nodelist")
        quorum_section = config_parser.Section("quorum")
        logging_section = config_parser.Section("logging")
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
                    node_id, node_options, range(constants.LINKS_MAX)
                )
            )

        self = cls(root)
        # pylint: disable=protected-access
        self.__update_two_node()

        return self

    def __init__(self, parsed_config):
        """
        Create a facade around a parsed corosync config file
        parsed_config parsed corosync config
        """
        super().__init__(parsed_config)
        # set to True if changes cannot be applied on running cluster
        self._need_stopped_cluster = False
        # set to True if qdevice reload is required to apply changes
        self._need_qdevice_reload = False

    @property
    def need_stopped_cluster(self):
        return self._need_stopped_cluster

    @property
    def need_qdevice_reload(self):
        return self._need_qdevice_reload

    def get_cluster_name(self) -> str:
        return cast(str, self._get_option_value("totem", "cluster_name", ""))

    # To get a list of nodenames use pcs.lib.node.get_existing_nodes_names

    def get_nodes(self) -> List[node.CorosyncNode]:
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
                    node.CorosyncNode(
                        node_data.get("name"),
                        [
                            node.CorosyncNodeAddress(
                                node_data[f"ring{i}_addr"], str(i)
                            )
                            for i in range(constants.LINKS_MAX)
                            if node_data.get(f"ring{i}_addr")
                        ],
                        node_data.get("nodeid"),
                    )
                )
        return result

    def _get_used_nodeid_list(self):
        used_ids = []
        for nodelist in self.config.get_sections("nodelist"):
            for node_section in nodelist.get_sections("node"):
                used_ids.extend(
                    [
                        int(attr[1])
                        for attr in node_section.get_attributes("nodeid")
                    ]
                )
        return used_ids

    @staticmethod
    def _get_nodeid_generator(used_ids):
        used_ids = set(used_ids)
        current_id = 1
        while True:
            if current_id not in used_ids:
                yield current_id
                used_ids.add(current_id)
            current_id += 1

    @staticmethod
    def _get_node_data(node_section):
        return {
            attr_name: attr_value
            for attr_name, attr_value in node_section.get_attributes()
            if attr_name in constants.NODE_OPTIONS
        }

    def get_used_linknumber_list(self):
        for nodelist_section in self.config.get_sections("nodelist"):
            for node_section in nodelist_section.get_sections("node"):
                node_data = self._get_node_data(node_section)
                if not node_data:
                    continue
                return [
                    str(i)
                    for i in range(constants.LINKS_MAX)
                    if node_data.get(f"ring{i}_addr")
                ]

    @staticmethod
    def _create_node_section(node_id, node_options, link_ids):
        node_section = config_parser.Section("node")
        for link_id, link_addr in zip(link_ids, node_options["addrs"]):
            node_section.add_attribute("ring{}_addr".format(link_id), link_addr)
        node_section.add_attribute("name", node_options["name"])
        node_section.add_attribute("nodeid", node_id)
        return node_section

    def add_nodes(self, node_list):
        """
        Add nodes to a config with a nonempty nodelist

        list node_list -- list of dict: name, addrs
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

    def remove_nodes(self, node_name_list):
        """
        Remove nodes from a config

        iterable node_name_list -- names of nodes to remove
        """
        for nodelist_section in self.config.get_sections("nodelist"):
            for node_section in nodelist_section.get_sections("node"):
                node_data = self._get_node_data(node_section)
                if node_data.get("name") in node_name_list:
                    nodelist_section.del_section(node_section)
        self.__remove_empty_sections(self.config)
        self.__update_two_node()

    def create_link_list(self, link_list):
        """
        Add a link list to a config without one

        iterable link_list -- list of dicts with link_list options
        """
        available_link_numbers = list(range(constants.LINKS_KNET_MAX))
        linknumber_missing = []
        links = []

        for link in link_list:
            if "linknumber" in link:
                try:
                    available_link_numbers.remove(int(link["linknumber"]))
                except ValueError as e:
                    raise AssertionError(
                        "Invalid link number: {}".format(e)
                    ) from e
                links.append(dict(link))
            else:
                linknumber_missing.append(link)

        for link in linknumber_missing:
            link = dict(link)
            try:
                link["linknumber"] = str(available_link_numbers.pop(0))
            except IndexError as e:
                raise AssertionError(
                    "Link number no longer available: {}".format(e)
                ) from e
            links.append(link)

        for link in sorted(links, key=lambda item: item["linknumber"]):
            self._set_link_options(link)

    def add_link(self, node_addr_map, options):
        """
        Add a new link to nodelist and create an interface section with options

        dict node_addr_map -- key: node name, value: node address for the link
        dict link_options -- link options
        """
        # Get a linknumber
        if "linknumber" in options:
            linknumber = options["linknumber"]
        else:
            linknumber = None
            used_links = self.get_used_linknumber_list()
            available_links = range(constants.LINKS_KNET_MAX)
            for candidate in available_links:
                if str(candidate) not in used_links:
                    linknumber = candidate
                    break
            if linknumber is None:
                raise AssertionError("No link number available")
            options["linknumber"] = linknumber

        # Add addresses
        for nodelist_section in self.config.get_sections("nodelist"):
            for node_section in nodelist_section.get_sections("node"):
                node_name = self._get_node_data(node_section).get("name")
                if node_name in node_addr_map:
                    node_section.add_attribute(
                        f"ring{linknumber}_addr", node_addr_map[node_name]
                    )

        # Add link options.
        if options:
            self._set_link_options(options)

    def _set_link_options(
        self, options, interface_section_list=None, linknumber=None
    ):
        """
        Add a new or change an existing interface section with link options

        dict options -- link options
        list interface_section_list -- list of existing sections to be changed
        string linknumber -- linknumber to set to a newly created section
        """
        # If the only option is "linknumber" then there is no point in adding
        # the options at all. It would mean there are no options for the
        # particular link.
        if not [name for name in options if name != "linknumber"]:
            return

        options_to_set = self.__translate_link_options(options)
        if not interface_section_list:
            new_section = config_parser.Section("interface")
            if linknumber:
                new_section.set_attribute("linknumber", linknumber)
            totem_section = self.__ensure_section(self.config, "totem")[-1]
            totem_section.add_section(new_section)
            interface_section_list = [new_section]
        self.__set_section_options(interface_section_list, options_to_set)
        self.__remove_empty_sections(self.config)

    def remove_links(self, link_list):
        """
        Remove links from nodelist and relevant interface sections from totem

        iterable link_list -- list of linknumbers (strings) to be removed
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

    def update_link(self, linknumber, node_addr_map, options):
        """
        Change an existing link - node addresses and/or link options

        string linknumber -- link to be changed
        dict node_addr_map -- key: node name, value: node address for the link
        dict link_options -- link options
        """
        self._need_stopped_cluster = True
        # make sure we do not change the linknumber
        if "linknumber" in options:
            del options["linknumber"]
        # change addresses
        if node_addr_map:
            for nodelist_section in self.config.get_sections("nodelist"):
                for node_section in nodelist_section.get_sections("node"):
                    node_name = self._get_node_data(node_section).get("name")
                    if node_name in node_addr_map:
                        node_section.set_attribute(
                            f"ring{linknumber}_addr", node_addr_map[node_name]
                        )
        # change options
        if options:
            target_interface_section_list = []
            for totem_section in self.config.get_sections("totem"):
                for interface_section in totem_section.get_sections(
                    "interface"
                ):
                    if (
                        linknumber
                        ==
                        # if no linknumber is set, corosync treats it as 0
                        interface_section.get_attribute_value("linknumber", "0")
                    ):
                        target_interface_section_list.append(interface_section)
            self._set_link_options(
                options,
                interface_section_list=target_interface_section_list,
                linknumber=linknumber,
            )
        self.__remove_empty_sections(self.config)

    def get_links_options(self):
        """
        Get all links' options in a dict: key=linknumber value=dict of options
        """
        transport = self.get_transport()
        allowed_options = (
            constants.LINK_OPTIONS_UDP
            if transport in constants.TRANSPORTS_UDP
            else constants.LINK_OPTIONS_KNET_COROSYNC
        )
        raw_options = dict()
        for totem_section in self.config.get_sections("totem"):
            for interface_section in totem_section.get_sections("interface"):
                # if no linknumber is set, corosync treats it as 0
                linknumber = interface_section.get_attribute_value(
                    "linknumber", "0"
                )
                if linknumber not in raw_options:
                    raw_options[linknumber] = dict()
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

    def get_transport(self):
        transport = self._get_option_value("totem", "transport")
        return transport if transport else constants.TRANSPORT_DEFAULT

    def get_ip_version(self):
        ip_version = self._get_option_value("totem", "ip_version")
        if ip_version:
            return ip_version
        if self.get_transport() == "udp":
            return constants.IP_VERSION_4
        return constants.IP_VERSION_64

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

    # TODO: tests
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

    def _set_transport_udp_options(self, options):
        """
        Set transport options for udp transports

        dict options -- transport options
        """
        totem_section_list = self.__ensure_section(self.config, "totem")
        self.__set_section_options(totem_section_list, options)

    def _set_transport_knet_options(
        self, generic_options, compression_options, crypto_options
    ):
        """
        Set transport options for knet transport

        dict generic_options -- generic transport options
        dict compression_options -- compression options
        dict crypto_options -- crypto options
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
        allowed_options: Iterable[str],
        prefix: str = "",
    ) -> Dict[str, str]:
        options = {}
        for section in self.config.get_sections(section_name):
            for name, value in section.get_attributes():
                if (
                    name.startswith(prefix)
                    and name[len(prefix) :] in allowed_options
                ):
                    options[name[len(prefix) :]] = value
        return options

    # TODO: tests, generalize for transport options
    def get_transport_options(self) -> Dict[str, str]:
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

    # TODO: tests, generalize for transport options
    def get_compression_options(self) -> Dict[str, str]:
        """
        Get configurable compression options
        """
        return self._filter_options(
            "totem",
            constants.TRANSPORT_KNET_COMPRESSION_OPTIONS,
            _KNET_COMPRESSION_OPTIONS_PREFIX,
        )

    # TODO: tests, generalize for transport options
    def get_crypto_options(self) -> Dict[str, str]:
        """
        Get configurable crypto options
        """
        return self._filter_options(
            "totem",
            constants.TRANSPORT_KNET_CRYPTO_OPTIONS,
            _KNET_CRYPTO_OPTIONS_PREFIX,
        )

    def set_totem_options(self, options):
        """
        Set options in the "totem" section

        dict options -- totem options
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

    # TODO: tests, generalize for transport options
    def get_totem_options(self) -> Dict[str, str]:
        """
        Get configurable totem options
        """
        return self._filter_options("totem", constants.TOTEM_OPTIONS)

    def set_quorum_options(self, options):
        """
        Set options in the "quorum" section

        dict options -- quorum options
        """
        quorum_section_list = self.__ensure_section(self.config, "quorum")
        self.__set_section_options(quorum_section_list, options)
        self.__update_two_node()
        self.__remove_empty_sections(self.config)
        self._need_stopped_cluster = True

    def get_quorum_options(self) -> Dict[str, str]:
        """
        Get configurable options from the "quorum" section
        """
        return self._filter_options("quorum", constants.QUORUM_OPTIONS)

    def is_enabled_auto_tie_breaker(self):
        """
        Returns True if auto tie braker option is enabled, False otherwise.
        """
        return self._get_option_value("quorum", "auto_tie_breaker", "0") == "1"

    def has_quorum_device(self):
        """
        Check if quorum device is present in the config
        """
        for quorum in self.config.get_sections("quorum"):
            for device in quorum.get_sections("device"):
                if device.get_attributes("model"):
                    return True
        return False

    def get_quorum_device_model(self):
        """
        Get quorum device model from quorum.device section
        """
        return self.get_quorum_device_settings()[0]

    def get_quorum_device_settings(self):
        """
        Get configurable options from quorum.device section
        """
        model = None
        model_options = {}
        generic_options = {}
        heuristics_options = {}
        for quorum in self.config.get_sections("quorum"):
            for device in quorum.get_sections("device"):
                for name, value in device.get_attributes():
                    if name == "model":
                        model = value
                    else:
                        generic_options[name] = value
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
            model,
            model_options.get(model, {}),
            generic_options,
            heuristics_options,
        )

    def is_quorum_device_heuristics_enabled_with_no_exec(self):
        heuristics_options = self.get_quorum_device_settings()[3]
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
        self, model, model_options, generic_options, heuristics_options
    ):
        # pylint: disable=too-many-locals
        """
        Add quorum device configuration

        string model -- quorum device model
        dict model_options -- model specific options
        dict generic_options -- generic quorum device options
        dict heuristics_options -- heuristics options
        """
        if self.has_quorum_device():
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
        new_device = config_parser.Section("device")
        quorum.add_section(new_device)
        self.__set_section_options([new_device], generic_options)
        new_device.set_attribute("model", model)
        new_model = config_parser.Section(model)
        self.__set_section_options([new_model], model_options)
        new_device.add_section(new_model)
        new_heuristics = config_parser.Section("heuristics")
        self.__set_section_options([new_heuristics], heuristics_options)
        new_device.add_section(new_heuristics)

        self.__update_qdevice_votes()
        self.__update_two_node()
        self.__remove_empty_sections(self.config)

    def update_quorum_device(
        self, model_options, generic_options, heuristics_options
    ):
        """
        Update existing quorum device configuration

        dict model_options -- model specific options
        dict generic_options -- generic quorum device options
        dict heuristics_options -- heuristics options
        """
        if not self.has_quorum_device():
            raise LibraryError(
                ReportItem.error(reports.messages.QdeviceNotDefined())
            )
        model = self.get_quorum_device_model()

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
        # has_quorum_device line above
        if not model_sections:
            new_model = config_parser.Section(model)
            device_sections[-1].add_section(new_model)
            model_sections.append(new_model)
        if not heuristics_sections:
            new_heuristics = config_parser.Section("heuristics")
            device_sections[-1].add_section(new_heuristics)
            heuristics_sections.append(new_heuristics)

        self.__set_section_options(device_sections, generic_options)
        self.__set_section_options(model_sections, model_options)
        self.__set_section_options(heuristics_sections, heuristics_options)

        self.__update_qdevice_votes()
        self.__update_two_node()
        self.__remove_empty_sections(self.config)
        self._need_qdevice_reload = True

    def remove_quorum_device_heuristics(self):
        """
        Remove quorum device heuristics configuration
        """
        if not self.has_quorum_device():
            raise LibraryError(
                ReportItem.error(reports.messages.QdeviceNotDefined())
            )
        for quorum in self.config.get_sections("quorum"):
            for device in quorum.get_sections("device"):
                for heuristics in device.get_sections("heuristics"):
                    device.del_section(heuristics)
        self.__remove_empty_sections(self.config)
        self._need_qdevice_reload = True

    def remove_quorum_device(self):
        """
        Remove all quorum device configuration
        """
        if not self.has_quorum_device():
            raise LibraryError(
                ReportItem.error(reports.messages.QdeviceNotDefined())
            )
        for quorum in self.config.get_sections("quorum"):
            for device in quorum.get_sections("device"):
                quorum.del_section(device)
        self.__update_two_node()
        self.__remove_empty_sections(self.config)

    def __update_two_node(self):
        # get relevant status
        has_quorum_device = self.has_quorum_device()
        has_two_nodes = len(self.get_nodes()) == 2
        auto_tie_breaker = self.is_enabled_auto_tie_breaker()
        # update two_node
        if has_two_nodes and not auto_tie_breaker and not has_quorum_device:
            quorum_section_list = self.__ensure_section(self.config, "quorum")
            self.__set_section_options(quorum_section_list, {"two_node": "1"})
        else:
            for quorum in self.config.get_sections("quorum"):
                quorum.del_attributes_by_name("two_node")

    def __update_qdevice_votes(self):
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
    def __set_section_options(section_list, options):
        for section in section_list[:-1]:
            for name in options:
                section.del_attributes_by_name(name)
        for name, value in sorted(options.items()):
            if value == "":
                section_list[-1].del_attributes_by_name(name)
            else:
                section_list[-1].set_attribute(name, value)

    @staticmethod
    def __ensure_section(parent_section, section_name):
        section_list = parent_section.get_sections(section_name)
        if not section_list:
            new_section = config_parser.Section(section_name)
            parent_section.add_section(new_section)
            section_list.append(new_section)
        return section_list

    def __remove_empty_sections(self, parent_section):
        for section in parent_section.get_sections():
            self.__remove_empty_sections(section)
            if section.empty or (
                section.name == "interface"
                and list(section.get_attributes_dict().keys()) == ["linknumber"]
            ):
                parent_section.del_section(section)

    @staticmethod
    def __translate_link_options(options, input_to_corosync=True):
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
            else:
                # When displaying config to users, do the opposite
                # transformation: only "yes" is allowed.
                if result["broadcast"] == "yes":
                    result["broadcast"] = "1"
                else:
                    del result["broadcast"]

        return result


def _add_prefix_to_dict_keys(prefix, data):
    return {"{}{}".format(prefix, key): value for key, value in data.items()}
