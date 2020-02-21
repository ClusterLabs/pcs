from collections import namedtuple
from functools import partial
from unittest import TestCase

from pcs.cli.common.reports import (
    # CODE_BUILDER_MAP,
    build_message_from_report,
)
# from pcs.common.reports import codes as report_codes

ReportItemMock = namedtuple("ReportItemMock", "code info")

# TODO: Disabled during reports transition period
# class ReportsTranslated(TestCase):
#     force_codes = {
#         report_codes.FORCE,
#         report_codes.FORCE_ALERT_RECIPIENT_VALUE_NOT_UNIQUE,
#         report_codes.FORCE_ALREADY_IN_CLUSTER,
#         report_codes.FORCE_BOOTH_DESTROY,
#         report_codes.FORCE_BOOTH_REMOVE_FROM_CIB,
#         report_codes.FORCE_REMOVE_MULTIPLE_NODES,
#         report_codes.FORCE_CONSTRAINT_DUPLICATE,
#         report_codes.FORCE_CONSTRAINT_MULTIINSTANCE_RESOURCE,
#         report_codes.FORCE_FILE_OVERWRITE,
#         report_codes.FORCE_LOAD_NODES_FROM_CIB,
#         report_codes.FORCE_LOAD_THRESHOLD,
#         report_codes.FORCE_METADATA_ISSUE,
#         report_codes.FORCE_NODE_ADDRESSES_UNRESOLVABLE,
#         report_codes.FORCE_NODE_DOES_NOT_EXIST,
#         report_codes.FORCE_OPTIONS,
#         report_codes.FORCE_QDEVICE_MODEL,
#         report_codes.FORCE_QDEVICE_USED,
#         report_codes.FORCE_QUORUM_LOSS,
#         report_codes.FORCE_STONITH_RESOURCE_DOES_NOT_EXIST,
#         report_codes.FORCE_NOT_SUITABLE_COMMAND,
#         report_codes.FORCE_CLEAR_CLUSTER_NODE,
#         report_codes.FORCE_RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE,
#         report_codes.SKIP_OFFLINE_NODES,
#         report_codes.SKIP_FILE_DISTRIBUTION_ERRORS,
#         report_codes.SKIP_ACTION_ON_NODES_ERRORS,
#         report_codes.SKIP_UNREADABLE_CONFIG,
#     }
#
#     def test_all_reports_translated(self):
#         all_codes = frozenset((
#             getattr(report_codes, code_const)
#             for code_const in dir(report_codes)
#             if (
#                 not code_const.startswith("_") # skip python builtins
#                 and
#                 getattr(report_codes, code_const) not in self.force_codes
#             )
#         ))
#         untranslated = all_codes - frozenset(CODE_BUILDER_MAP.keys())
#         self.assertEqual(
#             untranslated,
#             frozenset(),
#             f"{len(untranslated)} report codes have no translation in CLI. "
#             "Add translations for the report codes. Add force codes to "
#             f"{self.__class__.__module__}.{self.__class__.__name__}."
#             "force_codes so they won't get reported here."
#         )


class BuildMessageFromReportTest(TestCase):
    def test_returns_default_message_when_code_not_in_map(self):
        info = {"first": "FIRST"}
        self.assertEqual(
            "Unknown report: SOME info: {0}force text".format(str(info)),
            build_message_from_report(
                {},
                ReportItemMock("SOME", info),
                "force text"
            )
        )

    def test_complete_force_text(self):
        self.assertEqual(
            "Message force text is inside",
            build_message_from_report(
                {
                    "SOME": lambda info, force_text:
                        "Message "+force_text+" is inside"
                    ,
                },
                ReportItemMock("SOME", {}),
                "force text"
            )
        )

    def test_deal_with_callable(self):
        self.assertEqual(
            "Info: MESSAGE",
            build_message_from_report(
                {
                    "SOME": lambda info: "Info: {message}".format(**info),
                },
                ReportItemMock("SOME", {"message": "MESSAGE"}),
            )
        )

    def test_append_force_when_needed_and_not_specified(self):
        self.assertEqual(
            "message force at the end",
            build_message_from_report(
                {"SOME": "message"},
                ReportItemMock("SOME", {}),
                " force at the end",
            )
        )

    def test_returns_default_message_when_conflict_key_appear(self):
        info = {"message": "MESSAGE"}
        self.assertEqual(
            "Unknown report: SOME info: {0}".format(str(info)),
            build_message_from_report(
                {
                    "SOME": lambda info: "Info: {message} {extra}".format(
                        message="ANY", **info
                    ),
                },
                ReportItemMock("SOME", info),
            )
        )

    def test_returns_default_message_when_key_disappear(self):
        self.assertEqual(
            "Unknown report: SOME info: {}"
            ,
            build_message_from_report(
                {
                    "SOME": lambda info: "Info: {message}".format(**info),
                },
                ReportItemMock("SOME", {}),
            )
        )

    def test_callable_is_partial_object(self):
        code_builder_map = {
            "SOME": partial(
                lambda title, info: "{title}: {message}".format(
                    title=title, **info
                ),
                "Info"
            )
        }
        self.assertEqual(
            "Info: MESSAGE",
            build_message_from_report(
                code_builder_map,
                ReportItemMock("SOME", {"message": "MESSAGE"})
            )
        )

    def test_callable_is_partial_object_with_force(self):
        code_builder_map = {
            "SOME": partial(
                lambda title, info, force_text:
                    "{title}: {message} {force_text}".format(
                        title=title, force_text=force_text, **info
                    ),
                "Info"
            )
        }
        self.assertEqual(
            "Info: MESSAGE force text",
            build_message_from_report(
                code_builder_map,
                ReportItemMock("SOME", {"message": "MESSAGE"}),
                "force text"
            )
        )
