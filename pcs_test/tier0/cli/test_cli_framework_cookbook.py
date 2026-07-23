"""
This file serves as a cookbook for other devs to have an inspiration on how to
write tests using CLI test framework.
"""

from textwrap import dedent
from unittest import TestCase

from pcs.common.pacemaker.tag import CibTagDto, CibTagListDto
from pcs.common.reports import ReportItem
from pcs.common.reports.messages import (
    IdNotFound,
    InvalidIdIsEmpty,
    TagCannotContainItself,
)
from pcs.lib.errors import LibraryError

from pcs_test.tools import cli_test_framework as ctf


class TagCreate(TestCase):
    usage = ctf.prepare_stderr_usage("tag", "create")

    def test_no_args(self):
        ctf.run("tag create", exit_code=1, stderr=self.usage)

    def test_not_enough_args(self):
        ctf.run(
            "tag create arg1",
            exit_code=1,
            stderr=self.usage,
        )

    def test_minimum_args(self):
        ctf.run(
            "tag create arg1 arg2",
            lib_calls=[ctf.LibCallSpec("tag.create", ("arg1", ["arg2"]))],
        )

    def test_different_arg_calls_1(self):
        ctf.run(
            "tag create arg1 arg2",
            lib_calls=[
                ctf.LibCallSpec(
                    "tag.create", ("arg1",), {"idref_list": ["arg2"]}
                )
            ],
        )

    def test_different_arg_calls_2(self):
        ctf.run(
            "tag create arg1 arg2",
            lib_calls=[
                ctf.LibCallSpec(
                    "tag.create", (), {"tag_id": "arg1", "idref_list": ["arg2"]}
                )
            ],
        )

    def test_empty_args(self):
        reports = [
            ReportItem.error(InvalidIdIsEmpty("id")),
            ReportItem.error(TagCannotContainItself()),
            ReportItem.error(
                IdNotFound(
                    "",
                    ["bundle", "clone", "group", "resource"],
                )
            ),
        ]

        # here I used function prepare_stderr_reports to generate the expected
        # stderr output based on the reports given in lib_calls
        expected_stderr = ctf.prepare_stderr_reports(
            reports, additional_error=True
        )

        ctf.run(
            ["tag", "create", "", ""],
            lib_calls=[
                ctf.LibCallSpec(
                    "tag.create",
                    ("", [""]),
                    reports=reports,
                    raises=LibraryError(),
                )
            ],
            exit_code=1,
            stderr=expected_stderr,
        )

    def test_multiple_args(self):
        ctf.run(
            "tag create tagid id1 id2",
            lib_calls=[
                ctf.LibCallSpec("tag.create", ("tagid", ["id1", "id2"]))
            ],
        )

    def test_implicit_lib_list_call(self):
        ctf.run(
            "tag create tagid id1 id2",
            [ctf.LibCallSpec("tag.create", ("tagid", ["id1", "id2"]))],
        )

    def test_implicit_lib_call(self):
        ctf.run(
            "tag create tagid id1 id2",
            ctf.LibCallSpec("tag.create", ("tagid", ["id1", "id2"])),
        )

    def test_unsupported_option(self):
        ctf.run(
            "tag create --wait tag1 id1",
            exit_code=1,
            stderr=(
                "Error: Specified option '--wait' is not supported in this"
                " command\n"
            ),
            supported_flags=["-f"],
        )


class TagRemove(TestCase):
    usage = ctf.prepare_stderr_usage("tag", "remove")

    def test_no_args(self):
        ctf.run("tag remove", exit_code=1, stderr=self.usage)

    def test_minimum_args(self):
        ctf.run(
            "tag remove arg1",
            lib_calls=[ctf.LibCallSpec("tag.remove", (["arg1"],))],
        )

    def test_more_args(self):
        ctf.run(
            "tag remove arg1 arg2",
            lib_calls=[ctf.LibCallSpec("tag.remove", (["arg1", "arg2"],))],
        )


class TagConfig(TestCase):
    def test_no_args_no_tags(self):
        ctf.run(
            "tag config",
            lib_calls=[
                ctf.LibCallSpec(
                    "tag.get_config_dto",
                    ([],),
                    output=CibTagListDto([]),
                ),
            ],
        )

    def test_no_args_all_tags(self):
        ctf.run(
            "tag config",
            lib_calls=[
                ctf.LibCallSpec(
                    "tag.get_config_dto",
                    ([],),
                    output=CibTagListDto(
                        [
                            CibTagDto("tag1", ["i1", "i2", "i3"]),
                            CibTagDto("tag2", ["j1", "j2", "j3"]),
                        ]
                    ),
                ),
            ],
            stdout=dedent("""\
                    tag1
                      i1
                      i2
                      i3
                    tag2
                      j1
                      j2
                      j3
                    """),
        )

    def test_specified_tag(self):
        ctf.run(
            "tag config tag2",
            lib_calls=[
                ctf.LibCallSpec(
                    "tag.get_config_dto",
                    (["tag2"],),
                    output=CibTagListDto(
                        [CibTagDto("tag2", ["j1", "j2", "j3"])]
                    ),
                ),
            ],
            stdout=dedent("""\
                    tag2
                      j1
                      j2
                      j3
                    """),
        )

    def test_library_error_no_output(self):
        ctf.run(
            "tag config",
            lib_calls=[
                ctf.LibCallSpec(
                    "tag.get_config_dto",
                    ([],),
                    raises=LibraryError(),
                ),
            ],
            stdout="",
            stderr=(
                "Error: Errors have occurred, therefore pcs is unable"
                " to continue\n"
            ),
            exit_code=1,
        )

    def test_library_error_with_output(self):
        ctf.run(
            "tag config",
            lib_calls=[
                ctf.LibCallSpec(
                    "tag.get_config_dto",
                    ([],),
                    raises=LibraryError(),
                ),
            ],
            stderr=(
                "Error: Errors have occurred, therefore pcs is unable"
                " to continue\n"
            ),
            exit_code=1,
        )


class TagUpdate(TestCase):
    _hint = "Hint: Specify at least one id for 'add' or 'remove' arguments.\n"
    usage = ctf.prepare_stderr_usage("tag", "update")

    def test_no_args(self):
        ctf.run(
            "tag update",
            exit_code=1,
            stderr=self.usage,
        )

    def test_no_add_remove_keywords(self):
        ctf.run(
            "tag update tag_id",
            exit_code=1,
            stderr=self._hint + self.usage,
        )

    def test_add_without_ids(self):
        ctf.run(
            "tag update tag_id add",
            exit_code=1,
            stderr=self._hint + self.usage,
        )

    def test_remove_without_ids(self):
        ctf.run(
            "tag update tag_id remove",
            exit_code=1,
            stderr=self._hint + self.usage,
        )

    def test_add_remove_without_ids(self):
        ctf.run(
            "tag update tag_id add remove",
            exit_code=1,
            stderr=self._hint + self.usage,
        )

    def test_both_after_and_before(self):
        ctf.run(
            "tag update tag_id add id1 --after A --before B",
            exit_code=1,
            stderr=("Error: Cannot specify both --before and --after\n"),
            supported_flags=["-f", "--after", "--before"],
        )

    def test_only_add(self):
        ctf.run(
            "tag update tag_id add id1",
            lib_calls=[
                ctf.LibCallSpec(
                    "tag.update",
                    ("tag_id", ["id1"], []),
                    kwargs={
                        "adjacent_idref": None,
                        "put_after_adjacent": True,
                    },
                ),
            ],
        )

    def test_only_remove(self):
        ctf.run(
            "tag update tag_id remove id1",
            lib_calls=[
                ctf.LibCallSpec(
                    "tag.update",
                    ("tag_id", [], ["id1"]),
                    kwargs={
                        "adjacent_idref": None,
                        "put_after_adjacent": True,
                    },
                ),
            ],
        )

    def test_both_add_remove(self):
        ctf.run(
            "tag update tag_id remove i j add k l",
            lib_calls=[
                ctf.LibCallSpec(
                    "tag.update",
                    ("tag_id", ["k", "l"], ["i", "j"]),
                    kwargs={
                        "adjacent_idref": None,
                        "put_after_adjacent": True,
                    },
                ),
            ],
        )

    def test_only_add_after(self):
        ctf.run(
            "tag update tag_id add id1 --after A",
            lib_calls=[
                ctf.LibCallSpec(
                    "tag.update",
                    ("tag_id", ["id1"], []),
                    kwargs={
                        "adjacent_idref": "A",
                        "put_after_adjacent": True,
                    },
                ),
            ],
            supported_flags=["-f", "--after", "--before"],
        )

    def test_only_add_before(self):
        ctf.run(
            "tag update tag_id add id1 --before B",
            lib_calls=[
                ctf.LibCallSpec(
                    "tag.update",
                    ("tag_id", ["id1"], []),
                    kwargs={
                        "adjacent_idref": "B",
                        "put_after_adjacent": False,
                    },
                ),
            ],
            supported_flags=["-f", "--after", "--before"],
        )

    def test_add_after_and_remove(self):
        ctf.run(
            "tag update tag_id add id1 id2 remove id3 id4 --after A",
            lib_calls=[
                ctf.LibCallSpec(
                    "tag.update",
                    ("tag_id", ["id1", "id2"], ["id3", "id4"]),
                    kwargs={
                        "adjacent_idref": "A",
                        "put_after_adjacent": True,
                    },
                ),
            ],
            supported_flags=["-f", "--after", "--before"],
        )

    def test_add_before_and_remove(self):
        ctf.run(
            "tag update tag_id add id1 id2 remove id3 id4 --before B",
            lib_calls=[
                ctf.LibCallSpec(
                    "tag.update",
                    ("tag_id", ["id1", "id2"], ["id3", "id4"]),
                    kwargs={
                        "adjacent_idref": "B",
                        "put_after_adjacent": False,
                    },
                ),
            ],
            supported_flags=["-f", "--after", "--before"],
        )


class ClusterNodeClear(TestCase):
    def test_without_force(self):
        ctf.run(
            "cluster node clear node1",
            lib_calls=[
                ctf.LibCallSpec(
                    "cluster.node_clear",
                    ("node1",),
                    kwargs={"allow_clear_cluster_node": False},
                ),
            ],
        )

    def test_force(self):
        ctf.run(
            "cluster node clear --force node1",
            lib_calls=[
                ctf.LibCallSpec(
                    "cluster.node_clear",
                    ("node1",),
                    kwargs={"allow_clear_cluster_node": True},
                ),
            ],
        )


class ClusterReloadCorosyncConf(TestCase):
    def test_no_flags_supported(self):
        ctf.run(
            "cluster reload corosync",
            lib_calls=[ctf.LibCallSpec("cluster.reload_corosync_conf", ())],
            stderr="Corosync reloaded\n",
            supported_flags=[],
        )


# The classes below are not cookbook examples - they are self-tests of the
# framework itself. The cookbook above exercises the happy paths; these verify
# the framework's checking machinery actually fails when it should.


class FrameworkUnexpectedCall(TestCase):
    def test_call_when_none_expected(self):
        with self.assertRaisesRegex(
            AssertionError, "Unexpected library call: tag.create"
        ):
            ctf.run("tag create arg1 arg2", lib_calls=[])


class FrameworkMissingCall(TestCase):
    def test_expected_call_not_made(self):
        with self.assertRaisesRegex(
            AssertionError, "expected library call.* were not made"
        ):
            ctf.run(
                "tag create arg1 arg2",
                lib_calls=[
                    ctf.LibCallSpec("tag.create", ("arg1", ["arg2"])),
                    ctf.LibCallSpec("tag.remove", (["arg1"],)),
                ],
            )


class FrameworkWrongMethod(TestCase):
    def test_method_name_mismatch(self):
        with self.assertRaisesRegex(
            AssertionError, "expected 'tag.remove' but got 'tag.create'"
        ):
            ctf.run(
                "tag create arg1 arg2",
                lib_calls=[ctf.LibCallSpec("tag.remove", (["arg1"],))],
            )


class FrameworkArgsMismatch(TestCase):
    def test_wrong_args(self):
        with self.assertRaisesRegex(AssertionError, "args mismatch"):
            ctf.run(
                "tag create arg1 arg2",
                lib_calls=[
                    ctf.LibCallSpec("tag.create", ("different", ["values"]))
                ],
            )


class FrameworkSignatureMismatch(TestCase):
    def test_too_many_args_in_spec(self):
        with self.assertRaisesRegex(
            AssertionError, "does not match the command signature"
        ):
            ctf.run(
                "tag create arg1 arg2",
                lib_calls=[
                    ctf.LibCallSpec("tag.create", ("a", ["b"], "extra"))
                ],
            )


class FrameworkOutputChecks(TestCase):
    def test_exit_code_mismatch(self):
        with self.assertRaisesRegex(AssertionError, "Exit code mismatch"):
            ctf.run(
                "tag create arg1 arg2",
                lib_calls=[ctf.LibCallSpec("tag.create", ("arg1", ["arg2"]))],
                exit_code=1,
            )

    def test_stdout_mismatch(self):
        with self.assertRaisesRegex(AssertionError, "stdout mismatch"):
            ctf.run(
                "tag create arg1 arg2",
                lib_calls=[ctf.LibCallSpec("tag.create", ("arg1", ["arg2"]))],
                stdout="unexpected output\n",
            )

    def test_stderr_mismatch(self):
        with self.assertRaisesRegex(AssertionError, "stderr mismatch"):
            ctf.run(
                "tag create arg1 arg2",
                lib_calls=[ctf.LibCallSpec("tag.create", ("arg1", ["arg2"]))],
                stderr="unexpected error\n",
            )


class FrameworkSupportedFlags(TestCase):
    def test_flags_mismatch(self):
        with self.assertRaisesRegex(AssertionError, "supported flags mismatch"):
            ctf.run(
                "tag create arg1 arg2",
                lib_calls=[ctf.LibCallSpec("tag.create", ("arg1", ["arg2"]))],
                supported_flags=["--not-a-real-flag"],
            )


class FrameworkPrepareStderr(TestCase):
    def test_empty(self):
        self.assertEqual(ctf.prepare_stderr_reports(), "")

    def test_additional_error_only(self):
        self.assertEqual(
            ctf.prepare_stderr_reports(additional_error=True),
            "Error: Errors have occurred, "
            "therefore pcs is unable to continue\n",
        )

    def test_includes_force_text_from_real_renderer(self):
        # The expected stderr must be produced by the same renderer the
        # framework uses for the actual stderr, including force hints.
        reports = [
            ReportItem.error(TagCannotContainItself(), force_code="FORCE")
        ]
        self.assertEqual(
            ctf.prepare_stderr_reports(reports),
            "Error: Tag cannot contain itself, use --force to override\n",
        )
