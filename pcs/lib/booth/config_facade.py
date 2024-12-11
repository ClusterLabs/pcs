from typing import Optional

from pcs import settings
from pcs.lib.booth.config_parser import ConfigItem
from pcs.lib.booth.constants import AUTHFILE_FIX_OPTION
from pcs.lib.interface.config import FacadeInterface


class ConfigFacade(FacadeInterface):
    @classmethod
    def create(cls, site_list, arbitrator_list):
        """
        Create a minimal config

        iterable site_list -- list of booth sites' addresses
        iterable arbitrator_list -- list of arbitrators' addresses
        """
        return cls(
            [ConfigItem("site", site) for site in site_list]
            + [ConfigItem("arbitrator", arbit) for arbit in arbitrator_list]
        )

    ### peers

    def get_arbitrators(self):
        return self.__pick_values_by_key("arbitrator")

    def get_sites(self):
        return self.__pick_values_by_key("site")

    ### tickets

    def add_ticket(self, ticket_name, ticket_options):
        """
        Add a booth ticket to the booth config

        string ticket_name -- the name of the ticket
        dict ticket_options -- ticket options
        """
        self._config.append(
            ConfigItem(
                "ticket",
                ticket_name,
                [
                    ConfigItem(key, value)
                    for key, value in sorted(ticket_options.items())
                ],
            )
        )

    def has_ticket(self, ticket_name):
        """
        Return True if the ticket exists, False otherwise

        string ticket_name -- the name of the ticket
        """
        for key, value, _ in self._config:
            if key == "ticket" and value == ticket_name:
                return True
        return False

    def remove_ticket(self, ticket_name):
        """
        Remove an existing booth ticket from the booth config

        string ticket_name -- the name of the ticket
        """
        self._config = [
            config_item
            for config_item in self._config
            if config_item.key != "ticket" or config_item.value != ticket_name
        ]

    ### authfile

    def set_authfile(self, auth_file):
        """
        Set the path to a booth authfile to the booth config

        string auth_file -- the path to a booth authfile
        """
        if settings.booth_enable_authfile_set_enabled:
            self.set_option(AUTHFILE_FIX_OPTION, "yes")
        self.set_option("authfile", auth_file)

    def get_authfile(self) -> Optional[str]:
        """
        Get the path to a booth authfile set in the booth config or None
        """
        return self.get_option("authfile")

    ### tools

    def set_option(self, key: str, value: str) -> None:
        self._config = self.__filter_out_by_key(key)
        if value:
            self._config.insert(0, ConfigItem(key, value))

    def get_option(self, option: str) -> Optional[str]:
        for key, value, _ in reversed(self._config):
            if key == option:
                return value
        return None

    def __pick_values_by_key(self, key):
        return [item.value for item in self._config if item.key == key]

    def __filter_out_by_key(self, key):
        return [item for item in self._config if item.key != key]
