# pylint: disable=too-many-lines

from unittest import mock, TestCase

# TODO: move tests for these functions to proper location
from pcs.common.str_tools import(
    format_optional,
    format_plural,
    _is_multiple,
    _add_s
)
from pcs.cli.common.reports import CODE_BUILDER_MAP
from pcs.common.reports import ReportItem

class NameBuildTest(TestCase):
    """
    Base class for the testing of message building.
    """
    def assert_message_from_report(self, message, report, force_text=None):
        if not isinstance(report, ReportItem):
            raise AssertionError("report is not an instance of ReportItem")
        info = report.info if report.info else {}
        build = CODE_BUILDER_MAP[report.code]
        if force_text is not None:
            self.assertEqual(
                message,
                build(info, force_text)
            )
        else:
            self.assertEqual(
                message,
                build(info) if callable(build) else build
            )



class FormatOptionalTest(TestCase):
    def test_info_key_is_falsy(self):
        self.assertEqual("", format_optional("", "{0}: "))

    def test_info_key_is_not_falsy(self):
        self.assertEqual("A: ", format_optional("A", "{0}: "))

    def test_default_value(self):
        self.assertEqual("DEFAULT", format_optional("", "{0}: ", "DEFAULT"))

    def test_integer_zero_is_not_falsy(self):
        self.assertEqual("0: ", format_optional(0, "{0}: "))

class IsMultipleTest(TestCase):
    def test_unsupported(self):
        def empty_func():
            pass
        self.assertFalse(_is_multiple(empty_func()))

    def test_empty_string(self):
        self.assertFalse(_is_multiple(""))

    def test_string(self):
        self.assertFalse(_is_multiple("some string"))

    def test_list_empty(self):
        self.assertTrue(_is_multiple(list()))

    def test_list_single(self):
        self.assertFalse(_is_multiple(["the only list item"]))

    def test_list_multiple(self):
        self.assertTrue(_is_multiple(["item1", "item2"]))

    def test_dict_empty(self):
        self.assertTrue(_is_multiple(dict()))

    def test_dict_single(self):
        self.assertFalse(_is_multiple({"the only index": "something"}))

    def test_dict_multiple(self):
        self.assertTrue(_is_multiple({1: "item1", 2: "item2"}))

    def test_set_empty(self):
        self.assertTrue(_is_multiple(set()))

    def test_set_single(self):
        self.assertFalse(_is_multiple({"the only set item"}))

    def test_set_multiple(self):
        self.assertTrue(_is_multiple({"item1", "item2"}))

    def test_integer_zero(self):
        self.assertTrue(_is_multiple(0))

    def test_integer_one(self):
        self.assertFalse(_is_multiple(1))

    def test_integer_negative_one(self):
        self.assertFalse(_is_multiple(-1))

    def test_integer_more(self):
        self.assertTrue(_is_multiple(3))

class AddSTest(TestCase):
    def test_add_s(self):
        self.assertEqual(_add_s("fedora"), "fedoras")

    def test_add_es_s(self):
        self.assertEqual(_add_s("bus"), "buses")

    def test_add_es_x(self):
        self.assertEqual(_add_s("box"), "boxes")

    def test_add_es_o(self):
        self.assertEqual(_add_s("zero"), "zeroes")

    def test_add_es_ss(self):
        self.assertEqual(_add_s("address"), "addresses")

    def test_add_es_sh(self):
        self.assertEqual(_add_s("wish"), "wishes")

    def test_add_es_ch(self):
        self.assertEqual(_add_s("church"), "churches")

@mock.patch("pcs.common.str_tools._add_s")
@mock.patch("pcs.common.str_tools._is_multiple")
class FormatPluralTest(TestCase):
    def test_is_sg(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = False
        self.assertEqual(
            "is", format_plural(1, "is")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with(1)

    def test_is_pl(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = True
        self.assertEqual(
            "are", format_plural(2, "is")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with(2)

    def test_do_sg(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = False
        self.assertEqual(
            "does", format_plural("he", "does")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with("he")

    def test_do_pl(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = True
        self.assertEqual(
            "do", format_plural(["he", "she"], "does")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with(["he", "she"])

    def test_have_sg(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = False
        self.assertEqual(
            "has", format_plural("he", "has")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with("he")

    def test_have_pl(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = True
        self.assertEqual(
            "have", format_plural(["he", "she"], "has")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with(["he", "she"])

    def test_plural_sg(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = False
        self.assertEqual(
            "singular", format_plural(1, "singular", "plural")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with(1)

    def test_plural_pl(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = True
        self.assertEqual(
            "plural", format_plural(10, "singular", "plural")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with(10)

    def test_regular_sg(self, mock_is_multiple, mock_add_s):
        mock_is_multiple.return_value = False
        self.assertEqual(
            "greeting", format_plural(1, "greeting")
        )
        mock_add_s.assert_not_called()
        mock_is_multiple.assert_called_once_with(1)

    def test_regular_pl(self, mock_is_multiple, mock_add_s):
        mock_add_s.return_value = "greetings"
        mock_is_multiple.return_value = True
        self.assertEqual(
            "greetings", format_plural(10, "greeting")
        )
        mock_add_s.assert_called_once_with("greeting")
        mock_is_multiple.assert_called_once_with(10)
