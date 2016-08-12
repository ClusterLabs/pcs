from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.common import report_codes
from pcs.lib import reports
from pcs.lib.errors import ReportItemSeverity, LibraryError
from pcs.lib.corosync import config_parser
from pcs.lib.node import NodeAddresses, NodeAddressesList

class ConfigFacade(object):
    """
    Provides high level access to a corosync config file
    """

    QUORUM_OPTIONS = (
        "auto_tie_breaker",
        "last_man_standing",
        "last_man_standing_window",
        "wait_for_all",
    )
    QUORUM_OPTIONS_INCOMPATIBLE_WITH_QDEVICE = (
        "auto_tie_breaker",
        "last_man_standing",
        "last_man_standing_window",
    )


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

    def set_quorum_options(self, report_processor, options):
        """
        Set options in quorum section
        options quorum options dict
        """
        report_processor.process_list(
            self.__validate_quorum_options(options)
        )
        quorum_section_list = self.__ensure_section(self.config, "quorum")
        self.__set_section_options(quorum_section_list, options)
        self.__update_two_node()
        self.__remove_empty_sections(self.config)
        self._need_stopped_cluster = True

    def get_quorum_options(self):
        """
        Get configurable options from quorum section
        """
        options = {}
        for section in self.config.get_sections("quorum"):
            for name, value in section.get_attributes():
                if name in self.__class__.QUORUM_OPTIONS:
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

    def __validate_quorum_options(self, options):
        report_items = []
        has_qdevice = self.has_quorum_device()
        qdevice_incompatible_options = []
        for name, value in sorted(options.items()):
            allowed_names = self.__class__.QUORUM_OPTIONS
            if name not in allowed_names:
                report_items.append(
                    reports.invalid_option(name, allowed_names, "quorum")
                )
                continue

            if value == "":
                continue

            if (
                has_qdevice
                and
                name in self.__class__.QUORUM_OPTIONS_INCOMPATIBLE_WITH_QDEVICE
            ):
                qdevice_incompatible_options.append(name)

            if name == "last_man_standing_window":
                if not value.isdigit():
                    report_items.append(reports.invalid_option_value(
                        name, value, "positive integer"
                    ))

            else:
                allowed_values = ("0", "1")
                if value not in allowed_values:
                    report_items.append(reports.invalid_option_value(
                        name, value, allowed_values
                    ))

        if qdevice_incompatible_options:
            report_items.append(
                reports.corosync_options_incompatible_with_qdevice(
                    qdevice_incompatible_options
                )
            )

        return report_items

    def has_quorum_device(self):
        """
        Check if quorum device is present in the config
        """
        for quorum in self.config.get_sections("quorum"):
            for device in quorum.get_sections("device"):
                if device.get_attributes("model"):
                    return True
        return False

    def get_quorum_device_settings(self):
        """
        Get configurable options from quorum.device section
        """
        model = None
        model_options = {}
        generic_options = {}
        for quorum in self.config.get_sections("quorum"):
            for device in quorum.get_sections("device"):
                for name, value in device.get_attributes():
                    if name == "model":
                        model = value
                    else:
                        generic_options[name] = value
                for subsection in device.get_sections():
                    if subsection.name not in model_options:
                        model_options[subsection.name] = {}
                    model_options[subsection.name].update(
                        subsection.get_attributes()
                    )
        return model, model_options.get(model, {}), generic_options

    def add_quorum_device(
        self, report_processor, model, model_options, generic_options,
        force_model=False, force_options=False,
    ):
        """
        Add quorum device configuration
        model quorum device model
        model_options model specific options dict
        generic_options generic quorum device options dict
        force_model continue even if the model is not valid
        force_options continue even if options are not valid
        """
        # validation
        if self.has_quorum_device():
            raise LibraryError(reports.qdevice_already_defined())
        report_processor.process_list(
            self.__validate_quorum_device_model(model, force_model)
            +
            self.__validate_quorum_device_model_options(
                model,
                model_options,
                need_required=True,
                force=force_options
            )
            +
            self.__validate_quorum_device_generic_options(
                generic_options,
                force=force_options
            )
        )

        # configuration cleanup
        remove_need_stopped_cluster = dict([
            (name, "")
            for name in self.__class__.QUORUM_OPTIONS_INCOMPATIBLE_WITH_QDEVICE
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
        self.__update_qdevice_votes()
        self.__update_two_node()
        self.__remove_empty_sections(self.config)

    def update_quorum_device(
        self, report_processor, model_options, generic_options,
        force_options=False
    ):
        """
        Update existing quorum device configuration
        model_options model specific options dict
        generic_options generic quorum device options dict
        force_options continue even if options are not valid
        """
        # validation
        if not self.has_quorum_device():
            raise LibraryError(reports.qdevice_not_defined())
        model = None
        for quorum in self.config.get_sections("quorum"):
            for device in quorum.get_sections("device"):
                for dummy_name, value in device.get_attributes("model"):
                    model = value
        report_processor.process_list(
            self.__validate_quorum_device_model_options(
                model,
                model_options,
                need_required=False,
                force=force_options
            )
            +
            self.__validate_quorum_device_generic_options(
                generic_options,
                force=force_options
            )
        )
        # set new configuration
        device_sections = []
        model_sections = []
        for quorum in self.config.get_sections("quorum"):
            device_sections.extend(quorum.get_sections("device"))
            for device in quorum.get_sections("device"):
                model_sections.extend(device.get_sections(model))
        self.__set_section_options(device_sections, generic_options)
        self.__set_section_options(model_sections, model_options)
        self.__update_qdevice_votes()
        self.__update_two_node()
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

    def __validate_quorum_device_model(self, model, force_model=False):
        report_items = []

        allowed_values = (
            "net",
        )
        if model not in allowed_values:
            report_items.append(reports.invalid_option_value(
                "model",
                model,
                allowed_values,
                ReportItemSeverity.WARNING if force_model
                    else ReportItemSeverity.ERROR,
                None if force_model else report_codes.FORCE_QDEVICE_MODEL
            ))

        return report_items

    def __validate_quorum_device_model_options(
        self, model, model_options, need_required, force=False
    ):
        if model == "net":
            return self.__validate_quorum_device_model_net_options(
                model_options,
                need_required,
                force
            )
        return []

    def __validate_quorum_device_model_net_options(
        self, model_options, need_required, force=False
    ):
        required_options = frozenset(["host", "algorithm"])
        optional_options = frozenset([
            "connect_timeout",
            "force_ip_version",
            "port",
            "tie_breaker",
        ])
        allowed_options = required_options | optional_options
        model_options_names = frozenset(model_options.keys())
        report_items = []
        severity = (
            ReportItemSeverity.WARNING if force else ReportItemSeverity.ERROR
        )
        forceable = None if force else report_codes.FORCE_OPTIONS

        if need_required:
            for missing in sorted(required_options - model_options_names):
                report_items.append(reports.required_option_is_missing(missing))

        for name, value in sorted(model_options.items()):
            if name not in allowed_options:
                report_items.append(reports.invalid_option(
                    name,
                    allowed_options,
                    "quorum device model",
                    severity,
                    forceable
                ))
                continue

            if value == "":
                # do not allow to remove required options
                if name in required_options:
                    report_items.append(
                        reports.required_option_is_missing(name)
                    )
                else:
                    continue

            if name == "algorithm":
                allowed_values = ("ffsplit", "lms")
                if value not in allowed_values:
                    report_items.append(reports.invalid_option_value(
                        name, value, allowed_values, severity, forceable
                    ))

            if name == "connect_timeout":
                minimum, maximum = 1000, 2*60*1000
                if not (value.isdigit() and minimum <= int(value) <= maximum):
                    min_max = "{min}-{max}".format(min=minimum, max=maximum)
                    report_items.append(reports.invalid_option_value(
                        name, value, min_max, severity, forceable
                    ))

            if name == "force_ip_version":
                allowed_values = ("0", "4", "6")
                if value not in allowed_values:
                    report_items.append(reports.invalid_option_value(
                        name, value, allowed_values, severity, forceable
                    ))

            if name == "port":
                minimum, maximum = 1, 65535
                if not (value.isdigit() and minimum <= int(value) <= maximum):
                    min_max = "{min}-{max}".format(min=minimum, max=maximum)
                    report_items.append(reports.invalid_option_value(
                        name, value, min_max, severity, forceable
                    ))

            if name == "tie_breaker":
                node_ids = [node.id for node in self.get_nodes()]
                allowed_nonid = ["lowest", "highest"]
                if value not in allowed_nonid + node_ids:
                    allowed_values = allowed_nonid + ["valid node id"]
                    report_items.append(reports.invalid_option_value(
                        name, value, allowed_values, severity, forceable
                    ))

        return report_items

    def __validate_quorum_device_generic_options(
        self, generic_options, force=False
    ):
        optional_options = frozenset([
            "sync_timeout",
            "timeout",
        ])
        allowed_options = optional_options
        report_items = []
        severity = (
            ReportItemSeverity.WARNING if force else ReportItemSeverity.ERROR
        )
        forceable = None if force else report_codes.FORCE_OPTIONS

        for name, value in sorted(generic_options.items()):
            if name not in allowed_options:
                # model is never allowed in generic options, it is passed
                # in its own argument
                report_items.append(reports.invalid_option(
                    name,
                    allowed_options,
                    "quorum device",
                    severity if name != "model" else ReportItemSeverity.ERROR,
                    forceable if name != "model" else None
                ))
                continue

            if value == "":
                continue

            if not value.isdigit():
                report_items.append(reports.invalid_option_value(
                    name, value, "positive integer", severity, forceable
                ))

        return report_items

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
