class ParserInterface():
    def __init__(self, raw_file_data, file_type_code, file_path):
        """
        Get a parser for a raw config file data

        bytes raw_file_data -- raw config file data
        string file_type_code -- item from pcs.common.file_type_codes
        string file_path -- path to the parsed file
        """
        self._raw_file_data = raw_file_data
        self._file_type_code = file_type_code
        self._file_path = file_path
        self._report_list = []
        self._parse_error = False
        self._parser_ran = False
        self._parsed = None

    def get_parsed(self):
        if not self._parser_ran:
            self._run_parser()
        return self._parsed

    def get_reports(self):
        if not self._parser_ran:
            self._run_parser()
        return self._report_list

    def was_error(self):
        if not self._parser_ran:
            self._run_parser()
        return self._parse_error

    def _run_parser(self):
        self._parser_ran = True
        self._main_parse()

    def _main_parse(self):
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
