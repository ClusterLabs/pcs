from unittest import (
    TestCase,
    mock,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.constraint_colocation import command as colocation_command
from pcs.common.pacemaker.constraint import (
    CibConstraintColocationAttributesDto,
    CibConstraintColocationDto,
    CibConstraintsDto,
)

from pcs_test.tools.misc import dict_to_modifiers

FIXTURE_COLOCATION_CONSTRAINTS_DTO = CibConstraintsDto(
    colocation=[
        CibConstraintColocationDto(
            resource_id="A",
            with_resource_id="B",
            node_attribute=None,
            resource_role=None,
            with_resource_role=None,
            resource_instance=None,
            with_resource_instance=None,
            attributes=CibConstraintColocationAttributesDto(
                constraint_id="colocation-A-B",
                score=None,
                influence=None,
                lifetime=[],
            ),
        ),
        CibConstraintColocationDto(
            resource_id="B",
            with_resource_id="A",
            node_attribute=None,
            resource_role=None,
            with_resource_role=None,
            resource_instance=None,
            with_resource_instance=None,
            attributes=CibConstraintColocationAttributesDto(
                constraint_id="colocation-B-A",
                score=None,
                influence=None,
                lifetime=[],
            ),
        ),
        CibConstraintColocationDto(
            resource_id="C",
            with_resource_id="D",
            node_attribute=None,
            resource_role=None,
            with_resource_role=None,
            resource_instance=None,
            with_resource_instance=None,
            attributes=CibConstraintColocationAttributesDto(
                constraint_id="colocation-C-D",
                score=None,
                influence=None,
                lifetime=[],
            ),
        ),
    ]
)


class TestRemoveColocationConstraint(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["constraint", "cib"])
        self.cib = mock.Mock(spec_set=["remove_elements"])
        self.constraint = mock.Mock(spec_set=["get_config"])
        self.constraint.get_config.return_value = (
            FIXTURE_COLOCATION_CONSTRAINTS_DTO
        )
        self.lib.cib = self.cib
        self.lib.constraint = self.constraint

    def _call_cmd(self, argv, modifiers=None):
        colocation_command.remove(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.constraint.get_config.assert_not_called()
        self.cib.remove_elements.assert_not_called()

    def test_not_enough_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["id1"])
        self.assertIsNone(cm.exception.message)
        self.constraint.get_config.assert_not_called()
        self.cib.remove_elements.assert_not_called()

    def test_too_many_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["id1", "id2", "id3"])
        self.assertIsNone(cm.exception.message)
        self.constraint.get_config.assert_not_called()
        self.cib.remove_elements.assert_not_called()

    def test_unsupported_modifier(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["id1", "id2"], {"force": True})
        self.assertEqual(
            cm.exception.message,
            "Specified option '--force' is not supported in this command",
        )
        self.constraint.get_config.assert_not_called()
        self.cib.remove_elements.assert_not_called()

    def test_colocation_constraint_not_found(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["A", "D"])
        self.assertEqual(
            cm.exception.message,
            (
                "Unable to find colocation constraint with source resource id "
                "'A' and target resource id 'D'"
            ),
        )
        self.constraint.get_config.assert_called_once_with(evaluate_rules=False)
        self.cib.remove_elements.assert_not_called()

    def test_colocation_constraint_found(self):
        colocation_constraints_ids = ["C", "D"]
        self._call_cmd(colocation_constraints_ids)
        self.constraint.get_config.assert_called_once_with(evaluate_rules=False)
        self.cib.remove_elements.assert_called_once_with(["colocation-C-D"])

    @mock.patch("pcs.cli.constraint_colocation.command.deprecation_warning")
    def test_remove_colocation_constraint_with_interchanged_ids(
        self, mock_warn
    ):
        colocation_constraints_ids = ["A", "B"]
        self._call_cmd(colocation_constraints_ids)
        self.constraint.get_config.assert_called_once_with(evaluate_rules=False)
        self.cib.remove_elements.assert_called_once_with(
            ["colocation-A-B", "colocation-B-A"]
        )
        mock_warn.assert_called_once_with(
            "Removing colocation constraint with interchanged source resource "
            "id and targert resource id. This behavior is deprecated and will "
            "be removed."
        )
