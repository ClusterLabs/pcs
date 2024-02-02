from textwrap import dedent
from unittest import (
    TestCase,
    mock,
)

from pcs.cli.reports.preprocessor import (
    get_duplicate_constraint_exists_preprocessor,
)
from pcs.common import reports
from pcs.common.pacemaker.constraint import CibConstraintsDto
from pcs.common.pacemaker.constraint.location import (
    CibConstraintLocationAttributesDto,
    CibConstraintLocationDto,
)


class Preprocessor(TestCase):
    @mock.patch("pcs.cli.reports.preprocessor.print_to_stderr")
    def test_cib_cache(self, mock_print_stderr):
        cib_dto = CibConstraintsDto(
            [
                CibConstraintLocationDto(
                    "R1",
                    None,
                    None,
                    CibConstraintLocationAttributesDto(
                        "location1", "INFINITY", "node1", [], [], None
                    ),
                ),
                CibConstraintLocationDto(
                    "R2",
                    None,
                    None,
                    CibConstraintLocationAttributesDto(
                        "location2", "INFINITY", "node2", [], [], None
                    ),
                ),
            ]
        )
        mock_get_config = mock.Mock()
        mock_get_config.return_value = cib_dto
        mock_lib = mock.Mock(spec_set=["constraint"])
        mock_lib.constraint = mock.Mock(spec_set=["get_config"])
        mock_lib.constraint.get_config = mock_get_config

        preprocessor = get_duplicate_constraint_exists_preprocessor(mock_lib)
        preprocessor(
            reports.ReportItem.error(
                reports.messages.DuplicateConstraintsExist(["location1"])
            )
        )
        preprocessor(
            reports.ReportItem.error(
                reports.messages.DuplicateConstraintsExist(["location2"])
            )
        )

        stderr = dedent(
            """\
            Duplicate constraints:
              resource 'R1' prefers node 'node1' with score INFINITY (id: location1)
            Duplicate constraints:
              resource 'R2' prefers node 'node2' with score INFINITY (id: location2)
            """
        )
        stderr_calls = [mock.call(item) for item in stderr.splitlines()]
        mock_print_stderr.assert_has_calls(stderr_calls)
        self.assertEqual(mock_print_stderr.call_count, len(stderr_calls))
        mock_get_config.assert_called_once_with(evaluate_rules=False)
