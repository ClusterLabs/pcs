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
    @classmethod
    def create(cls):
        """
        Create a minimal config
        """
        raise NotImplementedError()

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
