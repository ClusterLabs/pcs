from typing import (
    Optional,
    Sequence,
)
from unittest import (
    TestCase,
    mock,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import Argv
from pcs.cli.query import resource
from pcs.common.const import PCMK_STATUS_ROLE_STARTED
from pcs.common.resource_status import (
    MoreChildrenQuantifierType,
    ResourceState,
    ResourceType,
    can_be_promotable,
    can_be_unique,
)
from pcs.common.status_dto import (
    BundleReplicaStatusDto,
    BundleStatusDto,
    CloneStatusDto,
    GroupStatusDto,
    PrimitiveStatusDto,
    ResourcesStatusDto,
)

from pcs_test.tools.misc import dict_to_modifiers


def fixture_primitive_dto(
    resource_id: str,
    instance_id: Optional[str],
    resource_agent: str = "ocf:pacemaker:Dummy",
    node_names: Sequence[str] = ("node1",),
) -> PrimitiveStatusDto:
    return PrimitiveStatusDto(
        resource_id,
        instance_id,
        resource_agent,
        role=PCMK_STATUS_ROLE_STARTED,
        target_role=None,
        active=True,
        orphaned=False,
        blocked=False,
        maintenance=False,
        description=None,
        failed=False,
        managed=True,
        failure_ignored=False,
        node_names=list(node_names),
        pending=None,
        locked_to=None,
    )


def fixture_group_dto(
    resource_id: str,
    instance_id: Optional[str],
    members: list[PrimitiveStatusDto],
) -> GroupStatusDto:
    return GroupStatusDto(
        resource_id, instance_id, False, None, True, False, members
    )


class QueryBaseMixin:
    def setUp(self):
        self.lib = mock.Mock(spec_set=["status"])
        self.lib.status = mock.Mock(spec_set=["resources_status"])
        self.lib_command: mock.Mock = self.lib.status.resources_status

    def test_no_argv(self, mock_print: mock.Mock):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def nonexistent_should_fail(
        self, mock_print: mock.Mock, additional_args: Argv
    ):
        self.lib_command.return_value = ResourcesStatusDto([])
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["nonexistent"] + additional_args)
        self.assertEqual(
            cm.exception.message, "Resource 'nonexistent' does not exist"
        )
        self.lib_command.assert_called_once_with()
        mock_print.assert_not_called()


@mock.patch("pcs.cli.query.resource.print")
class TestQueryResourceExists(QueryBaseMixin, TestCase):
    def _call_cmd(self, argv, modifiers=None) -> None:
        modifiers = modifiers or {}
        resource.exists(self.lib, argv, dict_to_modifiers(modifiers))

    def test_too_many_args(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["foo", "bar"])
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def test_true(self, mock_print):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("primitive", None)]
        )
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["primitive"])
        self.assertEqual(cm.exception.code, 0)
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with(True)

    def test_false(self, mock_print):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("primitive", None)]
        )
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["nonexistent"])
        self.assertEqual(cm.exception.code, 2)
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with(False)

    def test_quiet(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("primitive", None)]
        )
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["primitive"], {"quiet": True})
        self.assertEqual(cm.exception.code, 0)
        self.lib_command.assert_called_once_with()
        mock_print.assert_not_called()


@mock.patch("pcs.cli.query.resource.print")
class TestQueryIsType(QueryBaseMixin, TestCase):
    def _call_cmd(self, argv, modifiers=None) -> None:
        modifiers = modifiers or {}
        resource.is_type(self.lib, argv, dict_to_modifiers(modifiers))

    def test_too_many_args(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["foo", "primitive", "abc"])
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def test_no_type(self, mock_print: mock.Mock):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource_id"])
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def test_bad_type(self, mock_print: mock.Mock):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource_id", "primit"])
        self.assertEqual(
            cm.exception.message,
            (
                "'primit' is not a valid resource type value, use 'bundle', "
                "'clone', 'group', 'primitive'"
            ),
        )
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def test_true(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("resource", None)]
        )
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource", "primitive"])
        self.assertEqual(cm.exception.code, 0)
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with(True)

    def test_false(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("resource", None)]
        )
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource", "group"])
        self.assertEqual(cm.exception.code, 2)
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with(False)

    def test_nonexistent(self, mock_print: mock.Mock):
        self.nonexistent_should_fail(mock_print, ["primitive"])

    def test_promotable_bad_type(self, mock_print: mock.Mock):
        for resource_type in ["primitive", "group", "bundle"]:
            with self.subTest(value=resource_type):
                with self.assertRaises(CmdLineInputError) as cm:
                    self._call_cmd(["resource", resource_type, "promotable"])
                self.assertEqual(
                    cm.exception.message,
                    f"type '{resource_type}' cannot be promotable",
                )
                self.lib_command.assert_not_called()
                mock_print.assert_not_called()

    def test_unique_bad_type(self, mock_print: mock.Mock):
        for resource_type in ["primitive", "group"]:
            with self.subTest(value=resource_type):
                with self.assertRaises(CmdLineInputError) as cm:
                    self._call_cmd(["resource", resource_type, "unique"])
                self.assertEqual(
                    cm.exception.message,
                    f"type '{resource_type}' cannot be unique",
                )
                self.lib_command.assert_not_called()
                mock_print.assert_not_called()

    @mock.patch("pcs.common.resource_status.ResourcesStatusFacade.is_unique")
    @mock.patch("pcs.common.resource_status.ResourcesStatusFacade.get_type")
    def test_unique(
        self,
        mock_get_type: mock.Mock,
        mock_is_unique: mock.Mock,
        mock_print: mock.Mock,
    ):
        for unique in [False, True]:
            self.lib_command.reset_mock()
            mock_get_type.reset_mock()
            mock_is_unique.reset_mock()
            mock_print.reset_mock()

            self.lib_command.return_value = ResourcesStatusDto(
                [fixture_primitive_dto("resource", None)]
            )
            mock_get_type.return_value = ResourceType.CLONE
            mock_is_unique.return_value = unique
            with self.subTest(value=unique):
                with self.assertRaises(SystemExit) as cm:
                    self._call_cmd(["resource", "clone", "unique"])
                self.assertEqual(cm.exception.code, 0 if unique else 2)
                self.lib_command.assert_called_once_with()
                mock_get_type.assert_called_once_with("resource", None)
                mock_is_unique.assert_called_once_with("resource", None)
                mock_print.assert_called_once_with(unique)

    @mock.patch(
        "pcs.common.resource_status.ResourcesStatusFacade.is_promotable"
    )
    @mock.patch("pcs.common.resource_status.ResourcesStatusFacade.get_type")
    def test_promotable(
        self,
        mock_get_type: mock.Mock,
        mock_is_promotable: mock.Mock,
        mock_print: mock.Mock,
    ):
        for promotable in [False, True]:
            self.lib_command.reset_mock()
            mock_get_type.reset_mock()
            mock_is_promotable.reset_mock()
            mock_print.reset_mock()

            self.lib_command.return_value = ResourcesStatusDto(
                [fixture_primitive_dto("resource", None)]
            )
            mock_get_type.return_value = ResourceType.CLONE
            mock_is_promotable.return_value = promotable
            with self.subTest(value=promotable):
                with self.assertRaises(SystemExit) as cm:
                    self._call_cmd(["resource", "clone", "promotable"])
                self.assertEqual(cm.exception.code, 0 if promotable else 2)
                self.lib_command.assert_called_once_with()
                mock_get_type.assert_called_once_with("resource", None)
                mock_is_promotable.assert_called_once_with("resource", None)
                mock_print.assert_called_once_with(promotable)

    @mock.patch("pcs.common.resource_status.ResourcesStatusFacade.is_unique")
    @mock.patch(
        "pcs.common.resource_status.ResourcesStatusFacade.is_promotable"
    )
    @mock.patch("pcs.common.resource_status.ResourcesStatusFacade.get_type")
    def test_unique_promotable(
        self,
        mock_get_type: mock.Mock,
        mock_is_promotable: mock.Mock,
        mock_is_unique: mock.Mock,
        mock_print: mock.Mock,
    ):
        for unique in [False, True]:
            for promotable in [False, True]:
                self.lib_command.reset_mock()
                mock_get_type.reset_mock()
                mock_is_unique.reset_mock()
                mock_is_promotable.reset_mock()
                mock_print.reset_mock()

                self.lib_command.return_value = ResourcesStatusDto([])
                mock_get_type.return_value = ResourceType.CLONE
                mock_is_unique.return_value = unique
                mock_is_promotable.return_value = promotable
                with self.subTest(
                    value=f"unique:{unique} promotable:{promotable}"
                ):
                    with self.assertRaises(SystemExit) as cm:
                        self._call_cmd(
                            ["resource", "clone", "unique", "promotable"]
                        )

                    self.assertEqual(
                        cm.exception.code, 0 if unique and promotable else 2
                    )
                    self.lib_command.assert_called_once_with()
                    mock_get_type.assert_called_once_with("resource", None)
                    mock_is_unique.assert_called_once_with("resource", None)

                    if unique:
                        # will be called only if previous checks were true
                        mock_is_promotable.assert_called_once_with(
                            "resource", None
                        )
                    else:
                        mock_is_promotable.assert_not_called()

                    mock_print.assert_called_once_with(unique and promotable)

    def test_quiet(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("resource", None)]
        )
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource", "primitive"], {"quiet": True})
        self.lib_command.assert_called_once_with()
        self.assertEqual(cm.exception.code, 0)
        mock_print.assert_not_called()


@mock.patch("pcs.cli.query.resource.print")
class TestQueryGetType(QueryBaseMixin, TestCase):
    def _call_cmd(self, argv, modifiers=None) -> None:
        modifiers = modifiers or {}
        resource.get_type(self.lib, argv, dict_to_modifiers(modifiers))

    def test_too_many_args(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["foo", "bar"])
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def test_nonexistent(self, mock_print: mock.Mock):
        self.nonexistent_should_fail(mock_print, [])

    def test_primitive(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("resource", None)]
        )
        self._call_cmd(["resource"])
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with("primitive")

    @mock.patch("pcs.common.resource_status.ResourcesStatusFacade.is_unique")
    @mock.patch(
        "pcs.common.resource_status.ResourcesStatusFacade.is_promotable"
    )
    @mock.patch("pcs.common.resource_status.ResourcesStatusFacade.get_type")
    def test_all_types(
        self,
        mock_get_type: mock.Mock,
        mock_is_promotable: mock.Mock,
        mock_is_unique: mock.Mock,
        mock_print: mock.Mock,
    ):
        for resource_type in ResourceType:
            self.lib_command.reset_mock()
            mock_get_type.reset_mock()
            mock_is_promotable.reset_mock()
            mock_is_unique.reset_mock()
            mock_print.reset_mock()

            self.lib_command.return_value = ResourcesStatusDto(
                [fixture_primitive_dto("resource", None)]
            )
            mock_get_type.return_value = resource_type
            mock_is_unique.return_value = False
            mock_is_promotable.return_value = False
            with self.subTest(value=resource_type.name.lower()):
                self._call_cmd(["resource"])

                self.lib_command.assert_called_once_with()
                mock_get_type.assert_called_once_with("resource", None)
                if can_be_unique(resource_type):
                    mock_is_unique.assert_called_once_with("resource", None)
                else:
                    mock_is_unique.assert_not_called()
                if can_be_promotable(resource_type):
                    mock_is_promotable.assert_called_once_with("resource", None)
                else:
                    mock_is_promotable.assert_not_called()
                mock_print.assert_called_once_with(resource_type.name.lower())

    @mock.patch("pcs.common.resource_status.ResourcesStatusFacade.is_unique")
    @mock.patch(
        "pcs.common.resource_status.ResourcesStatusFacade.is_promotable"
    )
    @mock.patch("pcs.common.resource_status.ResourcesStatusFacade.get_type")
    def test_promotable_unique(
        self,
        mock_get_type: mock.Mock,
        mock_is_promotable: mock.Mock,
        mock_is_unique: mock.Mock,
        mock_print: mock.Mock,
    ):
        for promotable in [False, True]:
            for unique in [False, True]:
                expected_return_value = "clone"
                if unique:
                    expected_return_value += " unique"
                if promotable:
                    expected_return_value += " promotable"

                self.lib_command.reset_mock()
                mock_get_type.reset_mock()
                mock_is_unique.reset_mock()
                mock_is_promotable.reset_mock()
                mock_print.reset_mock()

                self.lib_command.return_value = ResourcesStatusDto([])
                mock_is_unique.return_value = unique
                mock_is_promotable.return_value = promotable
                mock_get_type.return_value = ResourceType.CLONE

                with self.subTest(value=expected_return_value):
                    self._call_cmd(["resource"])

                    self.lib_command.assert_called_once_with()
                    mock_get_type.assert_called_once_with("resource", None)
                    mock_is_unique.assert_called_once_with("resource", None)
                    mock_is_promotable.assert_called_once_with("resource", None)
                    mock_print.assert_called_once_with(expected_return_value)


@mock.patch("pcs.cli.query.resource.print")
class TestQueryIsStonith(QueryBaseMixin, TestCase):
    def _call_cmd(self, argv, modifiers=None) -> None:
        modifiers = modifiers or {}
        resource.is_stonith(self.lib, argv, dict_to_modifiers(modifiers))

    def test_too_many_args(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["foo", "bar"])
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def test_nonexistent(self, mock_print: mock.Mock):
        self.nonexistent_should_fail(mock_print, [])

    def test_true(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [
                fixture_primitive_dto(
                    "resource", None, resource_agent="stonith:fence_xvm"
                )
            ]
        )
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource"])
        self.assertEqual(cm.exception.code, 0)
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with(True)

    def test_false(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("resource", None)]
        )
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource"])
        self.assertEqual(cm.exception.code, 2)
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with(False)

    def test_quiet(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [
                fixture_primitive_dto(
                    "resource", None, resource_agent="stonith:fence_xvm"
                )
            ]
        )
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource"], {"quiet": True})
        self.assertEqual(cm.exception.code, 0)
        self.lib_command.assert_called_once_with()
        mock_print.assert_not_called()


@mock.patch("pcs.cli.query.resource.print")
class TestQueryGetMembers(QueryBaseMixin, TestCase):
    def _call_cmd(self, argv, modifiers=None) -> None:
        modifiers = modifiers or {}
        resource.get_members(self.lib, argv, dict_to_modifiers(modifiers))

    def test_too_many_args(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["foo", "bar"])
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def test_nonexistent(self, mock_print: mock.Mock):
        self.nonexistent_should_fail(mock_print, [])

    def test_bad_resource_type(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("resource", None)]
        )
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource"])
        self.assertEqual(
            cm.exception.message,
            (
                "Resource 'resource' has unexpected type 'primitive'. This "
                "command works only for resources of type 'bundle', 'clone', "
                "'group'"
            ),
        )
        self.lib_command.assert_called_once_with()
        mock_print.assert_not_called()

    def test_no_member(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_group_dto("resource", None, [])]
        )
        self._call_cmd(["resource"])
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with("")

    def test_single_member(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [
                fixture_group_dto(
                    "resource", None, [fixture_primitive_dto("a", None)]
                )
            ]
        )
        self._call_cmd(["resource"])
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with("a")

    def test_multiple_members(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [
                fixture_group_dto(
                    "resource",
                    None,
                    [
                        fixture_primitive_dto("a", None),
                        fixture_primitive_dto("c", None),
                        fixture_primitive_dto("b", None),
                    ],
                )
            ]
        )
        self._call_cmd(["resource"])
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with("a\nc\nb")


@mock.patch("pcs.cli.query.resource.print")
class TestQueryGetNodes(QueryBaseMixin, TestCase):
    def _call_cmd(self, argv, modifiers=None) -> None:
        modifiers = modifiers or {}
        resource.get_nodes(self.lib, argv, dict_to_modifiers(modifiers))

    def test_nonexistent(self, mock_print: mock.Mock):
        self.nonexistent_should_fail(mock_print, [])

    def test_too_many_args(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["foo", "bar"])
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def test_no_node(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("resource", None, node_names=[])]
        )
        self._call_cmd(["resource"])
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with("")

    def test_one_node(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("resource", None)]
        )
        self._call_cmd(["resource"])
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with("node1")

    def test_multiple_nodes(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [
                fixture_primitive_dto(
                    "resource", None, node_names=["node1", "node42", "node2"]
                )
            ]
        )
        self._call_cmd(["resource"])
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with("node1\nnode2\nnode42")


@mock.patch("pcs.cli.query.resource.print")
class TestQueryIsState(QueryBaseMixin, TestCase):
    def _call_cmd(self, argv, modifiers=None) -> None:
        modifiers = modifiers or {}
        resource.is_state(self.lib, argv, dict_to_modifiers(modifiers))

    def test_nonexistent(self, mock_print: mock.Mock):
        self.nonexistent_should_fail(mock_print, ["started"])

    def test_simple_true(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("resource", None)]
        )
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource", "started"])
        self.assertEqual(cm.exception.code, 0)
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with(True)

    def test_simple_false(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("resource", None)]
        )
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource", "stopped"])
        self.assertEqual(cm.exception.code, 2)
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with(False)

    def test_bad_state(self, mock_print: mock.Mock):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource", "start"])
        self.assertEqual(
            cm.exception.message,
            (
                "'start' is not a valid state value, use 'active', 'blocked', "
                "'demoting', 'disabled', 'enabled', 'failed', 'failure_ignored'"
                ", 'locked_to', 'maintenance', 'managed', 'migrating', "
                "'monitoring', 'orphaned', 'pending', 'promoted', 'promoting', "
                "'started', 'starting', 'stopped', 'stopping', 'unmanaged', "
                "'unpromoted'"
            ),
        )
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def test_quiet(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("resource", None)]
        )
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource", "started"], {"quiet": True})
        self.assertEqual(cm.exception.code, 0)
        self.lib_command.assert_called_once_with()
        mock_print.assert_not_called()

    @mock.patch("pcs.common.resource_status.ResourcesStatusFacade.is_state")
    def test_all_states(self, mock_is_state: mock.Mock, mock_print: mock.Mock):
        state_list = [state.name.lower() for state in ResourceState]
        for state in state_list:
            self.lib_command.reset_mock()
            mock_is_state.reset_mock()
            mock_print.reset_mock()

            # provide empty status dto so we dont have to mock the whole facade
            self.lib_command.return_value = ResourcesStatusDto([])
            mock_is_state.return_value = True

            with self.subTest(value=state):
                with self.assertRaises(SystemExit) as cm:
                    self._call_cmd(["resource", state])

                self.assertEqual(cm.exception.code, 0)
                self.lib_command.assert_called_once_with()
                mock_is_state.assert_called_once_with(
                    "resource",
                    None,
                    ResourceState[state.upper()],
                    None,
                    None,
                    None,
                )
                mock_print.assert_called_once_with(True)

    def test_on_node_missing_node(self, mock_print: mock.Mock):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource", "started", "on-node"])
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def test_on_node_too_much_nodes(self, mock_print: mock.Mock):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource", "started", "on-node", "node1", "node2"])
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    @mock.patch("pcs.common.resource_status.ResourcesStatusFacade.is_state")
    def test_on_node(self, mock_is_state: mock.Mock, mock_print: mock.Mock):
        # provide empty status dto so we dont have to mock the whole facade
        self.lib_command.return_value = ResourcesStatusDto([])
        mock_is_state.return_value = True
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource", "started", "on-node", "node1"])
        self.assertEqual(cm.exception.code, 0)

        self.lib_command.assert_called_once_with()
        mock_is_state.assert_called_once_with(
            "resource", None, ResourceState.STARTED, "node1", None, None
        )
        mock_print.assert_called_once_with(True)

    def test_members_quantifier_missing(self, mock_print: mock.Mock):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource", "started", "members"])
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def test_members_quantifier_bad_value(self, mock_print: mock.Mock):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource", "started", "members", "foo"])
        self.assertEqual(
            cm.exception.message,
            "'foo' is not a valid members value, use 'all', 'any', 'none'",
        )
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def test_instances_quantifier_bad_value(self, mock_print: mock.Mock):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource", "started", "instances", "foo"])
        self.assertEqual(
            cm.exception.message,
            "'foo' is not a valid instances value, use 'all', 'any', 'none'",
        )
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    @mock.patch("pcs.common.resource_status.ResourcesStatusFacade.is_state")
    def test_all_quantifiers(
        self, mock_is_state: mock.Mock, mock_print: mock.Mock
    ):
        quantifier_list = [
            quantifier.name.lower() for quantifier in MoreChildrenQuantifierType
        ]

        for member_quantifier in quantifier_list:
            for instances_quantifier in quantifier_list:
                self.lib_command.reset_mock()
                mock_is_state.reset_mock()
                mock_print.reset_mock()

                # provide empty status dto so we dont have to mock the whole facade
                self.lib_command.return_value = ResourcesStatusDto([])
                mock_is_state.return_value = True

                with self.subTest(
                    value=f"members {member_quantifier} instances:{instances_quantifier}"
                ):
                    with self.assertRaises(SystemExit) as cm:
                        self._call_cmd(
                            [
                                "resource",
                                "started",
                                "members",
                                member_quantifier,
                                "instances",
                                instances_quantifier,
                            ]
                        )

                    self.assertEqual(cm.exception.code, 0)
                    self.lib_command.assert_called_once_with()
                    mock_is_state.assert_called_once_with(
                        "resource",
                        None,
                        ResourceState.STARTED,
                        None,
                        MoreChildrenQuantifierType[member_quantifier.upper()],
                        MoreChildrenQuantifierType[
                            instances_quantifier.upper()
                        ],
                    )
                    mock_print.assert_called_once_with(True)

    def test_bad_members_quantifier(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("resource", None)]
        )
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource", "started", "members", "all"])
        self.assertEqual(
            cm.exception.message,
            (
                "'members' quantifier can be used only on group resources or "
                "group instances of cloned groups"
            ),
        )
        self.lib_command.assert_called_once_with()
        mock_print.assert_not_called()

    def test_bad_instances_quantifier(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("resource", None)]
        )
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource", "started", "instances", "all"])
        self.assertEqual(
            cm.exception.message,
            (
                "'instances' quantifier can be used only on clone resources "
                "and their instances, or on bundle resources and their replicas"
            ),
        )
        self.lib_command.assert_called_once_with()
        mock_print.assert_not_called()

    @mock.patch("pcs.common.resource_status.ResourcesStatusFacade.is_state")
    def test_all_args(self, mock_is_state: mock.Mock, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto([])
        mock_is_state.return_value = True

        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(
                [
                    "resource:1",
                    "started",
                    "on-node",
                    "node1",
                    "members",
                    "all",
                    "instances",
                    "any",
                ]
            )

        self.assertEqual(cm.exception.code, 0)
        self.lib_command.assert_called_once_with()
        mock_is_state.assert_called_once_with(
            "resource",
            "1",
            ResourceState.STARTED,
            "node1",
            MoreChildrenQuantifierType.ALL,
            MoreChildrenQuantifierType.ANY,
        )
        mock_print.assert_called_once_with(True)

    @mock.patch("pcs.common.resource_status.ResourcesStatusFacade.is_state")
    def test_clone_and_bundle(
        self, mock_is_state: mock.Mock, mock_print: mock.Mock
    ):
        # provide empty status dto so we dont have to mock the whole facade
        self.lib_command.return_value = ResourcesStatusDto([])
        mock_is_state.side_effect = NotImplementedError("foo")
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource", "started"])

        self.assertEqual(cm.exception.message, "foo")
        self.lib_command.assert_called_once_with()
        mock_is_state.assert_called_once_with(
            "resource", None, ResourceState.STARTED, None, None, None
        )
        mock_print.assert_not_called()


class QueryInContainerBaseMixin(QueryBaseMixin):
    not_in_container_status = ResourcesStatusDto(
        [fixture_primitive_dto("resource", None)]
    )

    def test_nonexistent(self, mock_print: mock.Mock):
        self.nonexistent_should_fail(mock_print, [])

    def test_too_many_args(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource", "container", "foobar"])

        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def test_true_no_container_id(self, mock_print: mock.Mock):
        self.lib_command.return_value = self.in_container_status

        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource"])

        self.assertEqual(cm.exception.code, 0)
        self.lib_command.assert_called_once_with()
        calls = (mock.call(True), mock.call("container"))
        self.assertEqual(mock_print.call_count, len(calls))
        mock_print.assert_has_calls(calls)

    def test_false_no_container_id(self, mock_print: mock.Mock):
        self.lib_command.return_value = self.not_in_container_status

        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource"])

        self.assertEqual(cm.exception.code, 2)
        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with(False)

    def test_true_container_id(self, mock_print: mock.Mock):
        self.lib_command.return_value = self.in_container_status

        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource", "container"])

        self.assertEqual(cm.exception.code, 0)
        self.lib_command.assert_called_once_with()
        calls = (mock.call(True), mock.call("container"))
        self.assertEqual(mock_print.call_count, len(calls))
        mock_print.assert_has_calls(calls)

    def test_true_bad_container_id(self, mock_print: mock.Mock):
        self.lib_command.return_value = self.in_container_status

        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource", "not_the_same_container"])

        self.assertEqual(cm.exception.code, 2)
        self.lib_command.assert_called_once_with()
        calls = (mock.call(False), mock.call("container"))
        self.assertEqual(mock_print.call_count, len(calls))
        mock_print.assert_has_calls(calls)

    def test_true_quiet(self, mock_print: mock.Mock):
        self.lib_command.return_value = self.in_container_status

        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource"], {"quiet": True})

        self.assertEqual(cm.exception.code, 0)
        self.lib_command.assert_called_once_with()
        mock_print.assert_not_called()

    def test_false_quiet(self, mock_print: mock.Mock):
        self.lib_command.return_value = self.not_in_container_status

        with self.assertRaises(SystemExit) as cm:
            self._call_cmd(["resource"], {"quiet": True})

        self.assertEqual(cm.exception.code, 2)
        self.lib_command.assert_called_once_with()
        mock_print.assert_not_called()


@mock.patch("pcs.cli.query.resource.print")
class TestQueryIsInGroup(QueryInContainerBaseMixin, TestCase):
    in_container_status = ResourcesStatusDto(
        [
            fixture_group_dto(
                "container", None, [fixture_primitive_dto("resource", None)]
            )
        ]
    )

    def _call_cmd(self, argv, modifiers=None) -> None:
        modifiers = modifiers or {}
        resource.is_in_group(self.lib, argv, dict_to_modifiers(modifiers))

    def test_bad_type(self, mock_print: mock.Mock):
        self.lib_command.return_value = self.in_container_status

        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["container"])

        self.assertEqual(
            cm.exception.message,
            (
                "Resource 'container' has unexpected type 'group'. This command"
                " works only for resources of type 'primitive'"
            ),
        )
        self.lib_command.assert_called_once_with()
        mock_print.assert_not_called()


@mock.patch("pcs.cli.query.resource.print")
class TestQueryIsInClone(QueryInContainerBaseMixin, TestCase):
    in_container_status = ResourcesStatusDto(
        [
            CloneStatusDto(
                "container",
                False,
                False,
                False,
                None,
                True,
                False,
                False,
                False,
                None,
                [fixture_primitive_dto("resource", None)],
            )
        ]
    )

    def _call_cmd(self, argv, modifiers=None) -> None:
        modifiers = modifiers or {}
        resource.is_in_clone(self.lib, argv, dict_to_modifiers(modifiers))

    def test_bad_type(self, mock_print: mock.Mock):
        self.lib_command.return_value = self.in_container_status

        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["container"])

        self.assertEqual(
            cm.exception.message,
            (
                "Resource 'container' has unexpected type 'clone'. This "
                "command works only for resources of type 'group', 'primitive'"
            ),
        )
        self.lib_command.assert_called_once_with()
        mock_print.assert_not_called()


@mock.patch("pcs.cli.query.resource.print")
class TestQueryIsInBundle(QueryInContainerBaseMixin, TestCase):
    in_container_status = ResourcesStatusDto(
        [
            BundleStatusDto(
                "container",
                "podman",
                "",
                False,
                False,
                None,
                True,
                False,
                [
                    BundleReplicaStatusDto(
                        "0",
                        member=fixture_primitive_dto("resource", None),
                        remote=None,
                        container=fixture_primitive_dto("podman", None),
                        ip_address=None,
                    )
                ],
            )
        ]
    )

    def _call_cmd(self, argv, modifiers=None) -> None:
        modifiers = modifiers or {}
        resource.is_in_bundle(self.lib, argv, dict_to_modifiers(modifiers))

    def test_bad_type(self, mock_print: mock.Mock):
        self.lib_command.return_value = self.in_container_status

        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["container"])

        self.assertEqual(
            cm.exception.message,
            (
                "Resource 'container' has unexpected type 'bundle'. This "
                "command works only for resources of type 'primitive'"
            ),
        )
        self.lib_command.assert_called_once_with()
        mock_print.assert_not_called()


@mock.patch("pcs.cli.query.resource.print")
class TestQueryGetIndexInGroup(QueryBaseMixin, TestCase):
    def _call_cmd(self, argv, modifiers=None) -> None:
        modifiers = modifiers or {}
        resource.get_index_in_group(
            self.lib, argv, dict_to_modifiers(modifiers)
        )

    def test_nonexistent(self, mock_print: mock.Mock):
        self.nonexistent_should_fail(mock_print, [])

    def test_too_many_args(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource", "foobar"])
        self.assertIsNone(cm.exception.message)
        self.lib_command.assert_not_called()
        mock_print.assert_not_called()

    def test_in_group(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [
                fixture_group_dto(
                    "container", None, [fixture_primitive_dto("resource", None)]
                )
            ]
        )
        self._call_cmd(["resource"])

        self.lib_command.assert_called_once_with()
        mock_print.assert_called_once_with(0)

    def test_not_in_group(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_primitive_dto("resource", None)]
        )
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource"])
        self.assertEqual(
            cm.exception.message, "Resource 'resource' is not in a group"
        )
        self.lib_command.assert_called_once_with()
        mock_print.assert_not_called()

    def test_bad_type(self, mock_print: mock.Mock):
        self.lib_command.return_value = ResourcesStatusDto(
            [fixture_group_dto("resource", None, [])]
        )
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["resource"])
        self.assertEqual(
            cm.exception.message,
            (
                "Resource 'resource' has unexpected type 'group'. This command "
                "works only for resources of type 'primitive'"
            ),
        )
        self.lib_command.assert_called_once_with()
        mock_print.assert_not_called()
