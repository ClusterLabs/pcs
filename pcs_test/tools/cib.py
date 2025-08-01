from pcs_test.tools.assertions import (
    AssertPcsMixin,
    assert_xml_equal,
)
from pcs_test.tools.misc import write_data_to_tmpfile


def xml_format(xml_string):
    line_list = xml_string.splitlines()
    reindented_lines = [line_list[0]]
    for line in line_list[1:]:
        leading_spaces = len(line) - len(line.lstrip()) - 4
        # current indent is 2 spaces desired is 4 spaces
        indent = " " * 2 * leading_spaces
        new_line = indent + line.strip()
        max_line_len = 80 - 12  # 12 is indent in this file ;)
        if new_line.endswith(">") and len(new_line) > max_line_len:
            last_space = new_line[:max_line_len].rfind(" ")
            if last_space:
                closing = "/>" if new_line.endswith("/>") else ">"
                split_line = [
                    new_line[:last_space],
                    indent + "   " + new_line[last_space : -1 * len(closing)],
                    indent + closing,
                ]
                reindented_lines.extend(split_line)
                continue
        # append not split line
        reindented_lines.append(new_line)

    return "\n".join(reindented_lines)


def get_assert_pcs_effect_mixin(get_cib_part):
    class AssertPcsEffectMixin(AssertPcsMixin):
        def assert_resources_xml_in_cib(
            self,
            expected_xml_resources,
            get_cib_part_func=None,
        ):
            self.temp_cib.seek(0)
            if get_cib_part_func is not None:
                xml = get_cib_part_func(self.temp_cib)
            else:
                xml = get_cib_part(self.temp_cib)
            try:
                assert_xml_equal(expected_xml_resources, xml.decode())
            except AssertionError as e:
                raise AssertionError(
                    "{0}\n\nCopy format ;)\n{1}".format(
                        e.args[0], xml_format(xml.decode())
                    )
                ) from e

        def assert_effect_single(
            self,
            command,
            expected_xml,
            *,
            stdout_full=None,
            stdout_start=None,
            stdout_regexp=None,
            stderr_full=None,
            stderr_start=None,
            stderr_regexp=None,
        ):
            # pylint: disable=too-many-arguments
            self.assert_pcs_success(
                command,
                stdout_full=stdout_full,
                stdout_start=stdout_start,
                stdout_regexp=stdout_regexp,
                stderr_full=stderr_full,
                stderr_start=stderr_start,
                stderr_regexp=stderr_regexp,
            )
            self.assert_resources_xml_in_cib(expected_xml)

        def assert_effect(
            self,
            alternative_cmds,
            expected_xml,
            *,
            stdout_full=None,
            stdout_start=None,
            stdout_regexp=None,
            stderr_full=None,
            stderr_start=None,
            stderr_regexp=None,
        ):
            # pylint: disable=too-many-arguments
            alternative_list = (
                alternative_cmds
                if isinstance(alternative_cmds[0], list)
                else [alternative_cmds]
            )
            self.temp_cib.seek(0)
            cib_content = self.temp_cib.read()
            self.temp_cib.seek(0)
            for alternative in alternative_list[:-1]:
                self.assert_effect_single(
                    alternative,
                    expected_xml,
                    stdout_full=stdout_full,
                    stdout_start=stdout_start,
                    stdout_regexp=stdout_regexp,
                    stderr_full=stderr_full,
                    stderr_start=stderr_start,
                    stderr_regexp=stderr_regexp,
                )
                write_data_to_tmpfile(cib_content, self.temp_cib)

            self.assert_effect_single(
                alternative_list[-1],
                expected_xml,
                stdout_full=stdout_full,
                stdout_start=stdout_start,
                stdout_regexp=stdout_regexp,
                stderr_full=stderr_full,
                stderr_start=stderr_start,
                stderr_regexp=stderr_regexp,
            )

    return AssertPcsEffectMixin
