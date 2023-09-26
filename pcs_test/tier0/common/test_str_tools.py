from unittest import TestCase

from pcs.common import str_tools as tools


class JoinMultilinesTest(TestCase):
    def test_empty_input(self):
        self.assertEqual("", tools.join_multilines([]))

    def test_two_strings(self):
        self.assertEqual("a\nb", tools.join_multilines(["a", "b"]))

    def test_strip(self):
        self.assertEqual("a\nb", tools.join_multilines(["  a\n", "  b\n"]))

    def test_skip_empty(self):
        self.assertEqual(
            "a\nb", tools.join_multilines(["  a\n", "   \n", "  b\n"])
        )

    def test_multiline(self):
        self.assertEqual(
            "a\nA\nb\nB", tools.join_multilines(["a\nA\n", "b\nB\n"])
        )


class IndentTest(TestCase):
    def test_indent_list_of_lines(self):
        self.assertEqual(
            tools.indent(["first", "second"]), ["  first", "  second"]
        )


class FormatOptionalTest(TestCase):
    def test_info_key_is_falsy(self):
        self.assertEqual("", tools.format_optional("", "{0}: "))

    def test_info_key_is_not_falsy(self):
        self.assertEqual("A: ", tools.format_optional("A", "{0}: "))

    def test_default_value(self):
        self.assertEqual(
            "DEFAULT", tools.format_optional("", "{0}: ", "DEFAULT")
        )

    def test_integer_zero_is_not_falsy(self):
        self.assertEqual("0: ", tools.format_optional(0, "{0}: "))


class IsMultipleTest(TestCase):
    # pylint: disable=protected-access
    def test_unsupported(self):
        def empty_func():
            pass

        self.assertFalse(tools._is_multiple(empty_func()))

    def test_empty_string(self):
        self.assertFalse(tools._is_multiple(""))

    def test_string(self):
        self.assertFalse(tools._is_multiple("some string"))

    def test_list_empty(self):
        self.assertTrue(tools._is_multiple([]))

    def test_list_single(self):
        self.assertFalse(tools._is_multiple(["the only list item"]))

    def test_list_multiple(self):
        self.assertTrue(tools._is_multiple(["item1", "item2"]))

    def test_dict_empty(self):
        self.assertTrue(tools._is_multiple({}))

    def test_dict_single(self):
        self.assertFalse(tools._is_multiple({"the only index": "something"}))

    def test_dict_multiple(self):
        self.assertTrue(tools._is_multiple({1: "item1", 2: "item2"}))

    def test_set_empty(self):
        self.assertTrue(tools._is_multiple(set()))

    def test_set_single(self):
        self.assertFalse(tools._is_multiple({"the only set item"}))

    def test_set_multiple(self):
        self.assertTrue(tools._is_multiple({"item1", "item2"}))

    def test_integer_zero(self):
        self.assertTrue(tools._is_multiple(0))

    def test_integer_one(self):
        self.assertFalse(tools._is_multiple(1))

    def test_integer_negative_one(self):
        self.assertFalse(tools._is_multiple(-1))

    def test_integer_more(self):
        self.assertTrue(tools._is_multiple(3))


class AddSTest(TestCase):
    # pylint: disable=protected-access
    def test_add_s(self):
        self.assertEqual(tools._add_s("fedora"), "fedoras")

    def test_add_es_s(self):
        self.assertEqual(tools._add_s("bus"), "buses")

    def test_add_es_x(self):
        self.assertEqual(tools._add_s("box"), "boxes")

    def test_add_es_o(self):
        self.assertEqual(tools._add_s("zero"), "zeroes")

    def test_add_es_ss(self):
        self.assertEqual(tools._add_s("address"), "addresses")

    def test_add_es_sh(self):
        self.assertEqual(tools._add_s("wish"), "wishes")

    def test_add_es_ch(self):
        self.assertEqual(tools._add_s("church"), "churches")


class GetPluralTest(TestCase):
    def test_common_plural(self):
        self.assertEqual("are", tools.get_plural("is"))

    def test_add_s(self):
        self.assertEqual("pieces", tools.get_plural("piece"))


class FormatPluralTest(TestCase):
    def test_is_sg(self):
        self.assertEqual("is", tools.format_plural(1, "is"))

    def test_is_pl(self):
        self.assertEqual("are", tools.format_plural(2, "is"))

    def test_do_sg(self):
        self.assertEqual("does", tools.format_plural("he", "does"))

    def test_do_pl(self):
        self.assertEqual("do", tools.format_plural(["he", "she"], "does"))

    def test_have_sg(self):
        self.assertEqual("has", tools.format_plural("he", "has"))

    def test_have_pl(self):
        self.assertEqual("have", tools.format_plural(["he", "she"], "has"))

    def test_plural_sg(self):
        self.assertEqual(
            "singular", tools.format_plural(1, "singular", "plural")
        )

    def test_plural_pl(self):
        self.assertEqual(
            "plural", tools.format_plural(10, "singular", "plural")
        )

    def test_regular_sg(self):
        self.assertEqual("greeting", tools.format_plural(1, "greeting"))

    def test_regular_pl(self):
        self.assertEqual("greetings", tools.format_plural(10, "greeting"))


class FormatList(TestCase):
    def test_empty_list(self):
        self.assertEqual(tools.format_list([]), "")

    def test_one_item(self):
        self.assertEqual(tools.format_list(["item"]), "'item'")

    def test_multiple_items(self):
        self.assertEqual(
            tools.format_list(["item2", "item0", "item1"]),
            "'item0', 'item1', 'item2'",
        )

    def test_custom_separator(self):
        self.assertEqual(
            tools.format_list(["item2", "item0", "item1"], separator=" and "),
            "'item0' and 'item1' and 'item2'",
        )


class FormatListCustomLastSeparatort(TestCase):
    def test_empty_list(self):
        self.assertEqual(
            tools.format_list_custom_last_separator([], " and "), ""
        )

    def test_one_item(self):
        self.assertEqual(
            tools.format_list_custom_last_separator(["item"], " and "), "'item'"
        )

    def test_two_items(self):
        self.assertEqual(
            tools.format_list_custom_last_separator(
                ["item1", "item2"], " and "
            ),
            "'item1' and 'item2'",
        )

    def test_multiple_items(self):
        self.assertEqual(
            tools.format_list_custom_last_separator(
                ["item2", "item0", "item1", "item3"], " and "
            ),
            "'item0', 'item1', 'item2' and 'item3'",
        )

    def test_custom_separator(self):
        self.assertEqual(
            tools.format_list_custom_last_separator(
                ["item2", "item0", "item1", "item3"], " or ", separator=" and "
            ),
            "'item0' and 'item1' and 'item2' or 'item3'",
        )


class FormatNameValueList(TestCase):
    def test_empty(self):
        self.assertEqual([], tools.format_name_value_list([]))

    def test_many(self):
        self.assertEqual(
            ["name1=value1", '"name=2"="value 2"', '"name 3"="value=3"'],
            tools.format_name_value_list(
                [
                    ("name1", "value1"),
                    ("name=2", "value 2"),
                    ("name 3", "value=3"),
                ]
            ),
        )


class FormatNameValueIdList(TestCase):
    def test_empty(self):
        self.assertEqual([], tools.format_name_value_id_list([]))

    def test_many(self):
        self.assertEqual(
            [
                "name1=value1 (id: id1)",
                '"name=2"="value 2" (id: id: 2)',
                '"name 3"="value=3" (id: id 3)',
            ],
            tools.format_name_value_id_list(
                [
                    ("name1", "value1", "id1"),
                    ("name=2", "value 2", "id: 2"),
                    ("name 3", "value=3", "id 3"),
                ]
            ),
        )


class FormatNameValueDefaultList(TestCase):
    def test_empty(self):
        self.assertEqual([], tools.format_name_value_default_list([]))

    def test_many(self):
        self.assertEqual(
            [
                '"name 3"="value=3"',
                '"name=2"="value 2" (default)',
                "name1=value1",
            ],
            tools.format_name_value_default_list(
                [
                    ("name 3", "value=3", False),
                    ("name=2", "value 2", True),
                    ("name1", "value1", False),
                ]
            ),
        )


class Quote(TestCase):
    def test_no_quote(self):
        self.assertEqual("string", tools.quote("string", " "))
        self.assertEqual("string", tools.quote("string", " ="))

    def test_quote(self):
        self.assertEqual('"str ing"', tools.quote("str ing", " ="))
        self.assertEqual('"str=ing"', tools.quote("str=ing", " ="))

    def test_alternative_quote(self):
        self.assertEqual("""'st"r i"ng'""", tools.quote('st"r i"ng', " "))

    def test_escape(self):
        self.assertEqual('''"st\\"r i'ng"''', tools.quote("st\"r i'ng", " "))


class Transform(TestCase):
    def test_transform(self):
        self.assertEqual(
            tools.transform(
                ["A", "0", "C", "x", "A", "B", "a"], {"A": "a", "C": "1"}
            ),
            ["a", "0", "1", "x", "a", "B", "a"],
        )
