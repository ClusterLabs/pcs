class ParserErrorException(Exception):
    pass

class ParserInterface():
    @staticmethod
    def parse(raw_file_data):
        raise NotImplementedError()

    @staticmethod
    def exception_to_report_list(
        exception, file_type_code, file_path, force_code, is_forced_or_warning
    ):
        raise NotImplementedError()


class ExporterInterface():
    @staticmethod
    def export(config_structure):
        """
        Export config structure to raw file data (bytes)

        mixed config_structure -- parsed config file
        """
        raise NotImplementedError()


class FacadeInterface():
    # Facades should also implement a 'create' classmethod which creates a new
    # facade with a minimalistic config in it. This method for sure has
    # different interface in each class (depending on which config's facade it
    # is). The create method is not used by the files framework (there is no
    # need and also due to mentioned interface differences). Therefore the
    # create method is not defined here in the interface.
    def __init__(self, parsed_config):
        """
        Create a facade around a parsed config file

        parsed_config -- parsed config file
        """
        self._config = parsed_config

    @property
    def config(self):
        """
        Export a parsed config file
        """
        return self._config
