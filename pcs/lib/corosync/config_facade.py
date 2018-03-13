from pcs.lib import reports
from pcs.lib.corosync import config_parser, constants
from pcs.lib.errors import LibraryError
from pcs.lib.node import NodeAddresses, NodeAddressesList

class ConfigFacade(object):
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
        except config_parser.MissingClosingBraceException:
            raise LibraryError(
                reports.corosync_config_parser_missing_closing_brace()
            )
        except config_parser.UnexpectedClosingBraceException:
            raise LibraryError(
                reports.corosync_config_parser_unexpected_closing_brace()
            )
        except config_parser.CorosyncConfParserException:
            raise LibraryError(
                reports.corosync_config_parser_other_error()
            )

    @classmethod
    def create(cls, cluster_name, node_list, transport):
        """
        Create a minimal config

        string cluster_name -- a name of a cluster
        list node_list -- list of dict: name, addrs
        string transport -- corosync transport
        """
        root = config_parser.Section("")
        # TODO actually create all required sections
        return cls(root)

    def __init__(self, parsed_config):
        """
        Create a facade around a parsed corosync config file
        parsed_config parsed corosync config
        """
        self._config = parsed_config
        # set to True if changes cannot be applied on running cluster
        self._need_stopped_cluster = False
        # set to True if qdevice reload is required to apply changes
        self._need_qdevice_reload = False

    @property
    def config(self):
        return self._config

    @property
    def need_stopped_cluster(self):
        return self._need_stopped_cluster

    @property
    def need_qdevice_reload(self):
        return self._need_qdevice_reload

    def get_cluster_name(self):
        cluster_name = ""
        for totem in self.config.get_sections("totem"):
            for attrs in totem.get_attributes("cluster_name"):
                cluster_name = attrs[1]
        return cluster_name

    def get_nodes(self):
        """
        Get all defined nodes
        """
        result = NodeAddressesList()
        for nodelist in self.config.get_sections("nodelist"):
            for node in nodelist.get_sections("node"):
                node_data = {
                    "ring0_addr": None,
                    "ring1_addr": None,
                    "name": None,
                    "nodeid": None,
                }
                for attr_name, attr_value in node.get_attributes():
                    if attr_name in node_data:
                        node_data[attr_name] = attr_value
                result.append(NodeAddresses(
                    node_data["ring0_addr"],
                    node_data["ring1_addr"],
                    node_data["name"],
                    node_data["nodeid"]
                ))
        return result

    def add_link(self, options):
        """
        Add a new link

        dict options -- link options
        """

    def set_transport_udp_options(self, options):
        """
        Set transport options for udp transports

        dict options -- transport options
        """

    def set_transport_knet_options(
        self, generic_options, compression_options, crypto_options
    ):
        """
        Set transport options for knet transport

        dict generic_options -- generic transport options
        dict compression_options -- compression options
        dict crypto_options -- crypto options
        """

    def set_totem_options(self, options):
        """
        Set options in the "totem" section

        dict options -- totem options
        """

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

    def get_quorum_options(self):
        """
        Get configurable options from the "quorum" section
        """
        options = {}
        for section in self.config.get_sections("quorum"):
            for name, value in section.get_attributes():
                if name in constants.QUORUM_OPTIONS:
                    options[name] = value
        return options

    def is_enabled_auto_tie_breaker(self):
        """
        Returns True if auto tie braker option is enabled, False otherwise.
        """
        auto_tie_breaker = "0"
        for quorum in self.config.get_sections("quorum"):
            for attr in quorum.get_attributes("auto_tie_breaker"):
                auto_tie_breaker = attr[1]
        return auto_tie_breaker == "1"

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
        return (
            not exec_found
            and
            heuristics_options.get("mode") in ("on", "sync")
        )

    def add_quorum_device(
        self, model, model_options, generic_options, heuristics_options
    ):
        """
        Add quorum device configuration

        string model -- quorum device model
        dict model_options -- model specific options
        dict generic_options -- generic quorum device options
        dict heuristics_options -- heuristics options
        """
        if self.has_quorum_device():
            raise LibraryError(reports.qdevice_already_defined())

        # configuration cleanup
        remove_need_stopped_cluster = dict([
            (name, "")
            for name in constants.QUORUM_OPTIONS_INCOMPATIBLE_WITH_QDEVICE
        ])
        # remove old device settings
        quorum_section_list = self.__ensure_section(self.config, "quorum")
        for quorum in quorum_section_list:
            for device in quorum.get_sections("device"):
                quorum.del_section(device)
            for name, value in quorum.get_attributes():
                if (
                    name in remove_need_stopped_cluster
                    and
                    value not in ["", "0"]
                ):
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
            for node in nodelist.get_sections("node"):
                node.del_attributes_by_name("quorum_votes")

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
            raise LibraryError(reports.qdevice_not_defined())
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
            raise LibraryError(reports.qdevice_not_defined())
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
            raise LibraryError(reports.qdevice_not_defined())
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
                for dummy_name, value in device.get_attributes("model"):
                    model = value
        for device in device_sections:
            for model_section in device.get_sections(model):
                for dummy_name, value in model_section.get_attributes(
                    "algorithm"
                ):
                    algorithm = value
        if model == "net":
            if algorithm == "ffsplit":
                self.__set_section_options(device_sections, {"votes": "1"})
            else:
                self.__set_section_options(device_sections, {"votes": ""})

    def __set_section_options(self, section_list, options):
        for section in section_list[:-1]:
            for name in options:
                section.del_attributes_by_name(name)
        for name, value in sorted(options.items()):
            if value == "":
                section_list[-1].del_attributes_by_name(name)
            else:
                section_list[-1].set_attribute(name, value)

    def __ensure_section(self, parent_section, section_name):
        section_list = parent_section.get_sections(section_name)
        if not section_list:
            new_section = config_parser.Section(section_name)
            parent_section.add_section(new_section)
            section_list.append(new_section)
        return section_list

    def __remove_empty_sections(self, parent_section):
        for section in parent_section.get_sections():
            self.__remove_empty_sections(section)
            if section.empty:
                parent_section.del_section(section)
