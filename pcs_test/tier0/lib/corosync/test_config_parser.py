# pylint: disable=too-many-lines
from unittest import TestCase

from pcs.lib.corosync import config_parser

from pcs_test.tools.misc import outdent


class SectionTest(TestCase):
    def test_empty_section(self):
        section = config_parser.Section("mySection")
        self.assertEqual(section.parent, None)
        self.assertEqual(section.get_root(), section)
        self.assertEqual(section.name, "mySection")
        self.assertEqual(section.get_attributes(), [])
        self.assertEqual(section.get_sections(), [])
        self.assertTrue(section.empty)
        self.assertEqual(str(section), "")

    def test_is_section_empty(self):
        section = config_parser.Section("mySection")
        self.assertTrue(section.empty)

        section = config_parser.Section("mySection")
        section.add_attribute("name", "value")
        self.assertFalse(section.empty)

        section = config_parser.Section("mySection")
        section.add_section(config_parser.Section("subSection"))
        self.assertFalse(section.empty)

        section = config_parser.Section("mySection")
        section.add_attribute("name", "value")
        section.add_section(config_parser.Section("subSection"))
        self.assertFalse(section.empty)

    def test_attribute_add(self):
        section = config_parser.Section("mySection")

        section.add_attribute("name1", "value1")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
            ],
        )

        section.add_attribute("name2", "value2")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
                ("name2", "value2"),
            ],
        )

        section.add_attribute("name2", "value2")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
                ("name2", "value2"),
                ("name2", "value2"),
            ],
        )

    def test_attribute_get(self):
        section = config_parser.Section("mySection")
        section.add_attribute("name1", "value1")
        section.add_attribute("name2", "value2")
        section.add_attribute("name3", "value3")
        section.add_attribute("name2", "value2a")

        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
                ("name2", "value2"),
                ("name3", "value3"),
                ("name2", "value2a"),
            ],
        )
        self.assertEqual(
            section.get_attributes("name1"),
            [
                ("name1", "value1"),
            ],
        )
        self.assertEqual(
            section.get_attributes("name2"),
            [
                ("name2", "value2"),
                ("name2", "value2a"),
            ],
        )
        self.assertEqual(section.get_attributes("nameX"), [])

    def test_attribute_get_dict(self):
        section = config_parser.Section("mySection")
        self.assertEqual(section.get_attributes_dict(), {})

        section = config_parser.Section("mySection")
        section.add_attribute("name1", "value1")
        section.add_attribute("name2", "value2")
        section.add_attribute("name3", "value3")
        self.assertEqual(
            section.get_attributes_dict(),
            {
                "name1": "value1",
                "name2": "value2",
                "name3": "value3",
            },
        )

        section = config_parser.Section("mySection")
        section.add_attribute("name1", "value1")
        section.add_attribute("name2", "value2")
        section.add_attribute("name3", "value3")
        section.add_attribute("name1", "value1A")
        section.add_attribute("name3", "value3A")
        section.add_attribute("name1", "")
        self.assertEqual(
            section.get_attributes_dict(),
            {
                "name1": "",
                "name2": "value2",
                "name3": "value3A",
            },
        )

    def test_attribute_value(self):
        section = config_parser.Section("mySection")
        self.assertEqual(section.get_attribute_value("name"), None)

        section = config_parser.Section("mySection")
        section.add_attribute("name1", "value1")
        section.add_attribute("name2", "value2")
        self.assertEqual(section.get_attribute_value("name", "value"), "value")

        section = config_parser.Section("mySection")
        section.add_attribute("name", "value")
        section.add_attribute("name1", "value1")
        section.add_attribute("name", "valueA")
        section.add_attribute("name1", "value1A")
        self.assertEqual(section.get_attribute_value("name"), "valueA")

    def test_attribute_set(self):
        section = config_parser.Section("mySection")

        section.set_attribute("name1", "value1")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
            ],
        )

        section.set_attribute("name1", "value1")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
            ],
        )

        section.set_attribute("name1", "value1a")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1a"),
            ],
        )

        section.set_attribute("name2", "value2")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1a"),
                ("name2", "value2"),
            ],
        )

        section.set_attribute("name1", "value1")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
                ("name2", "value2"),
            ],
        )

        section.add_attribute("name3", "value3")
        section.add_attribute("name2", "value2")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
                ("name2", "value2"),
                ("name3", "value3"),
                ("name2", "value2"),
            ],
        )
        section.set_attribute("name2", "value2a")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
                ("name2", "value2a"),
                ("name3", "value3"),
            ],
        )

        section.add_attribute("name1", "value1")
        section.add_attribute("name1", "value1")
        section.set_attribute("name1", "value1")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
                ("name2", "value2a"),
                ("name3", "value3"),
            ],
        )

    def test_attribute_del_by_name(self):
        section = config_parser.Section("mySection")
        section.add_attribute("name1", "value1")
        section.add_attribute("name2", "value2")
        section.add_attribute("name3", "value3")
        section.add_attribute("name2", "value2")

        section.del_attributes_by_name("nameX")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
                ("name2", "value2"),
                ("name3", "value3"),
                ("name2", "value2"),
            ],
        )

        section.del_attributes_by_name("name2", "value2")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
                ("name3", "value3"),
            ],
        )

        section.add_attribute("name2", "value2")
        section.add_attribute("name2", "value2a")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
                ("name3", "value3"),
                ("name2", "value2"),
                ("name2", "value2a"),
            ],
        )
        section.del_attributes_by_name("name2", "value2")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
                ("name3", "value3"),
                ("name2", "value2a"),
            ],
        )

        section.add_attribute("name3", "value3a")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
                ("name3", "value3"),
                ("name2", "value2a"),
                ("name3", "value3a"),
            ],
        )
        section.del_attributes_by_name("name3")
        self.assertEqual(
            section.get_attributes(),
            [
                ("name1", "value1"),
                ("name2", "value2a"),
            ],
        )

    def test_section_add(self):
        root = config_parser.Section("root")
        child1 = config_parser.Section("child1")
        child1a = config_parser.Section("child1a")
        child2 = config_parser.Section("child2")

        root.add_section(child1)
        child1.add_section(child1a)
        root.add_section(child2)
        self.assertEqual(root.parent, None)
        self.assertEqual(child1.parent.name, "root")
        self.assertEqual(child1a.parent.name, "child1")
        self.assertEqual(child2.parent.name, "root")
        self.assertEqual(
            str(root),
            outdent(
                """\
            child1 {
                child1a {
                }
            }

            child2 {
            }
            """
            ),
        )

        child2.add_section(child1a)
        self.assertEqual(child1a.parent.name, "child2")
        self.assertEqual(
            str(root),
            outdent(
                """\
            child1 {
            }

            child2 {
                child1a {
                }
            }
            """
            ),
        )

        self.assertRaises(
            config_parser.CircularParentshipException,
            child1a.add_section,
            child1a,
        )
        self.assertRaises(
            config_parser.CircularParentshipException,
            child1a.add_section,
            child2,
        )
        self.assertRaises(
            config_parser.CircularParentshipException, child1a.add_section, root
        )

    def test_section_get(self):
        root = config_parser.Section("")
        child1 = config_parser.Section("child1")
        child2 = config_parser.Section("child2")
        childa1 = config_parser.Section("childA")
        childa2 = config_parser.Section("childA")
        childa3 = config_parser.Section("childA")
        childa4 = config_parser.Section("childA")
        childb1 = config_parser.Section("childB")
        childb2 = config_parser.Section("childB")
        childa1.add_attribute("id", "1")
        childa2.add_attribute("id", "2")
        childa3.add_attribute("id", "3")
        childa4.add_attribute("id", "4")
        childb1.add_attribute("id", "5")
        childb2.add_attribute("id", "6")
        root.add_section(child1)
        root.add_section(child2)
        child1.add_section(childa1)
        child1.add_section(childa2)
        child1.add_section(childb1)
        child2.add_section(childa3)
        child2.add_section(childb2)
        child2.add_section(childa4)
        self.assertEqual(
            str(root),
            outdent(
                """\
            child1 {
                childA {
                    id: 1
                }

                childA {
                    id: 2
                }

                childB {
                    id: 5
                }
            }

            child2 {
                childA {
                    id: 3
                }

                childB {
                    id: 6
                }

                childA {
                    id: 4
                }
            }
            """
            ),
        )

        self.assertEqual(
            "---\n".join([str(x) for x in root.get_sections()]),
            outdent(
                """\
                child1 {
                    childA {
                        id: 1
                    }

                    childA {
                        id: 2
                    }

                    childB {
                        id: 5
                    }
                }
                ---
                child2 {
                    childA {
                        id: 3
                    }

                    childB {
                        id: 6
                    }

                    childA {
                        id: 4
                    }
                }
                """
            ),
        )

        self.assertEqual(
            "---\n".join([str(x) for x in root.get_sections("child1")]),
            outdent(
                """\
                child1 {
                    childA {
                        id: 1
                    }

                    childA {
                        id: 2
                    }

                    childB {
                        id: 5
                    }
                }
                """
            ),
        )

        self.assertEqual(
            "---\n".join([str(x) for x in child1.get_sections("childA")]),
            outdent(
                """\
                childA {
                    id: 1
                }
                ---
                childA {
                    id: 2
                }
                """
            ),
        )

        self.assertEqual(
            "---\n".join([str(x) for x in child1.get_sections("child2")]), ""
        )

    def test_section_del(self):
        root = config_parser.Section("")
        child1 = config_parser.Section("child1")
        child2 = config_parser.Section("child2")
        childa1 = config_parser.Section("childA")
        childa2 = config_parser.Section("childA")
        childa3 = config_parser.Section("childA")
        childa4 = config_parser.Section("childA")
        childb1 = config_parser.Section("childB")
        childb2 = config_parser.Section("childB")
        childa1.add_attribute("id", "1")
        childa2.add_attribute("id", "2")
        childa3.add_attribute("id", "3")
        childa4.add_attribute("id", "4")
        childb1.add_attribute("id", "5")
        childb2.add_attribute("id", "6")
        root.add_section(child1)
        root.add_section(child2)
        child1.add_section(childa1)
        child1.add_section(childa2)
        child1.add_section(childb1)
        child2.add_section(childa3)
        child2.add_section(childb2)
        child2.add_section(childa4)
        self.assertEqual(
            str(root),
            outdent(
                """\
            child1 {
                childA {
                    id: 1
                }

                childA {
                    id: 2
                }

                childB {
                    id: 5
                }
            }

            child2 {
                childA {
                    id: 3
                }

                childB {
                    id: 6
                }

                childA {
                    id: 4
                }
            }
            """
            ),
        )

        child2.del_section(childb2)
        self.assertEqual(childb2.parent, None)
        self.assertEqual(
            str(root),
            outdent(
                """\
            child1 {
                childA {
                    id: 1
                }

                childA {
                    id: 2
                }

                childB {
                    id: 5
                }
            }

            child2 {
                childA {
                    id: 3
                }

                childA {
                    id: 4
                }
            }
            """
            ),
        )

        root.del_section(child2)
        self.assertEqual(child2.parent, None)
        self.assertEqual(
            str(root),
            outdent(
                """\
            child1 {
                childA {
                    id: 1
                }

                childA {
                    id: 2
                }

                childB {
                    id: 5
                }
            }
            """
            ),
        )

        self.assertRaises(ValueError, root.del_section, child2)

        self.assertEqual(childa1.parent.name, "child1")
        self.assertRaises(ValueError, child2.del_section, childa1)
        self.assertEqual(childa1.parent.name, "child1")

        child1.del_section(childb1)
        self.assertEqual(childb1.parent, None)
        self.assertEqual(
            str(root),
            outdent(
                """\
            child1 {
                childA {
                    id: 1
                }

                childA {
                    id: 2
                }
            }
            """
            ),
        )

        child1.del_section(childa1)
        self.assertEqual(childa1.parent, None)
        child1.del_section(childa2)
        self.assertEqual(childa2.parent, None)
        self.assertEqual(
            str(root),
            outdent(
                """\
            child1 {
            }
            """
            ),
        )

        root.del_section(child1)
        self.assertEqual(child1.parent, None)
        self.assertEqual(str(root), "")

    def test_get_root(self):
        root = config_parser.Section("root")
        child1 = config_parser.Section("child1")
        child1a = config_parser.Section("child1a")
        root.add_section(child1)
        child1.add_section(child1a)

        self.assertEqual(root.get_root().name, "root")
        self.assertEqual(child1.get_root().name, "root")
        self.assertEqual(child1a.get_root().name, "root")

    def test_str(self):
        root = config_parser.Section("root")
        self.assertEqual(str(root), "")

        root.add_attribute("name1", "value1")
        self.assertEqual(str(root), "name1: value1\n")

        root.add_attribute("name2", "value2")
        root.add_attribute("name2", "value2a")
        root.add_attribute("name3", "value3")
        self.assertEqual(
            str(root),
            outdent(
                """\
            name1: value1
            name2: value2
            name2: value2a
            name3: value3
            """
            ),
        )

        child1 = config_parser.Section("child1")
        root.add_section(child1)
        self.assertEqual(
            str(root),
            outdent(
                """\
            name1: value1
            name2: value2
            name2: value2a
            name3: value3

            child1 {
            }
            """
            ),
        )

        child1.add_attribute("name1.1", "value1.1")
        child1.add_attribute("name1.2", "value1.2")
        self.assertEqual(
            str(root),
            outdent(
                """\
            name1: value1
            name2: value2
            name2: value2a
            name3: value3

            child1 {
                name1.1: value1.1
                name1.2: value1.2
            }
            """
            ),
        )

        child2 = config_parser.Section("child2")
        child2.add_attribute("name2.1", "value2.1")
        root.add_section(child2)
        self.assertEqual(
            str(root),
            outdent(
                """\
            name1: value1
            name2: value2
            name2: value2a
            name3: value3

            child1 {
                name1.1: value1.1
                name1.2: value1.2
            }

            child2 {
                name2.1: value2.1
            }
            """
            ),
        )

        child2a = config_parser.Section("child2a")
        child2a.add_attribute("name2.a.1", "value2.a.1")
        child2.add_section(child2a)
        self.assertEqual(
            str(root),
            outdent(
                """\
            name1: value1
            name2: value2
            name2: value2a
            name3: value3

            child1 {
                name1.1: value1.1
                name1.2: value1.2
            }

            child2 {
                name2.1: value2.1

                child2a {
                    name2.a.1: value2.a.1
                }
            }
            """
            ),
        )

        child3 = config_parser.Section("child3")
        root.add_section(child3)
        child3.add_section(config_parser.Section("child3a"))
        child3.add_section(config_parser.Section("child3b"))
        self.assertEqual(
            str(root),
            outdent(
                """\
            name1: value1
            name2: value2
            name2: value2a
            name3: value3

            child1 {
                name1.1: value1.1
                name1.2: value1.2
            }

            child2 {
                name2.1: value2.1

                child2a {
                    name2.a.1: value2.a.1
                }
            }

            child3 {
                child3a {
                }

                child3b {
                }
            }
            """
            ),
        )


class ParserTest(TestCase):
    # pylint: disable=too-many-public-methods
    def test_empty(self):
        self.assertEqual(
            str(config_parser.Parser.parse("".encode("utf-8"))), ""
        )

    def test_attributes_one_attribute(self):
        string = outdent(
            """\
            name:value\
            """
        )
        parsed = outdent(
            """\
            name: value
            """
        )
        self.assertEqual(
            str(config_parser.Parser.parse(string.encode("utf-8"))), parsed
        )

    def test_attributes_two_attributes_same_name(self):
        string = outdent(
            """\
            name:value
            name:value
            """
        )
        parsed = outdent(
            """\
            name: value
            name: value
            """
        )
        self.assertEqual(
            str(config_parser.Parser.parse(string.encode("utf-8"))), parsed
        )

    def test_attributes_more_attributes_whitespace(self):
        string = outdent(
            """\
              name1:value1  
            name2  :value2
            name3:  value3
              name4  :  value4  
            """
        )
        parsed = outdent(
            """\
            name1: value1
            name2: value2
            name3: value3
            name4: value4
            """
        )
        self.assertEqual(
            str(config_parser.Parser.parse(string.encode("utf-8"))), parsed
        )

    def test_attributes_colon_in_value(self):
        string = outdent(
            """\
            name:foo:value
            """
        )
        parsed = outdent(
            """\
            name: foo:value
            """
        )
        root = config_parser.Parser.parse(string.encode("utf-8"))
        self.assertEqual(root.get_attributes(), [("name", "foo:value")])
        self.assertEqual(str(root), parsed)

    def test_attributes_empty_value(self):
        string = outdent(
            """\
            name :  
            """
        )
        parsed = outdent(
            """\
            name: 
            """
        )
        root = config_parser.Parser.parse(string.encode("utf-8"))
        self.assertEqual(root.get_attributes(), [("name", "")])
        self.assertEqual(str(root), parsed)

    def test_sections_empty_section(self):
        string = outdent(
            """\
            section1 {
            }\
            """
        )
        parsed = outdent(
            """\
            section1 {
            }
            """
        )
        self.assertEqual(
            str(config_parser.Parser.parse(string.encode("utf-8"))), parsed
        )

    def test_sections_empty_section_in_section_whitespace(self):
        string = outdent(
            """\
            section1 {
                section1a   {
              }
              section1b        {       
                 }    
            }
            """
        )
        parsed = outdent(
            """\
            section1 {
                section1a {
                }

                section1b {
                }
            }
            """
        )
        self.assertEqual(
            str(config_parser.Parser.parse(string.encode("utf-8"))), parsed
        )

    def test_sections_no_name_before_opening(self):
        string = outdent(
            """\
            section1 {
                {
                }
            }
            section2 {
               section2a {
               }
               section2b {
               }
            }
            """
        )
        self.assertRaises(
            config_parser.MissingSectionNameBeforeOpeningBraceException,
            config_parser.Parser.parse,
            string.encode("utf-8"),
        )

    def test_sections_junk_after_opening(self):
        string = outdent(
            """\
            section1 {
                section1a {junk
                }
            }
            section2 {
               section2a {
               }
               section2b {
               }
            }
            """
        )
        self.assertRaises(
            config_parser.ExtraCharactersAfterOpeningBraceException,
            config_parser.Parser.parse,
            string.encode("utf-8"),
        )

    def test_sections_comment_junk_after_opening(self):
        string = outdent(
            """\
            section1 {
                section1a { #junk
                }
            }
            section2 {
               section2a {
               }
               section2b {
               }
            }
            """
        )
        self.assertRaises(
            config_parser.ExtraCharactersAfterOpeningBraceException,
            config_parser.Parser.parse,
            string.encode("utf-8"),
        )

    def test_sections_junk_before_closing(self):
        string = outdent(
            """\
            section1 {
                section1a {
                junk}
            }
            section2 {
               section2a {
               }
               section2b {
               }
            }
            """
        )
        self.assertRaises(
            config_parser.ExtraCharactersBeforeOrAfterClosingBraceException,
            config_parser.Parser.parse,
            string.encode("utf-8"),
        )

    def test_sections_junk_after_closing(self):
        string = outdent(
            """\
            section1 {
                section1a {
                }junk
            }
            section2 {
               section2a {
               }
               section2b {
               }
            }
            """
        )
        self.assertRaises(
            config_parser.ExtraCharactersBeforeOrAfterClosingBraceException,
            config_parser.Parser.parse,
            string.encode("utf-8"),
        )

    def test_sections_comment_junk_after_closing(self):
        string = outdent(
            """\
            section1 {
                section1a {
                } #junk
            }
            section2 {
               section2a {
               }
               section2b {
               }
            }
            """
        )
        self.assertRaises(
            config_parser.ExtraCharactersBeforeOrAfterClosingBraceException,
            config_parser.Parser.parse,
            string.encode("utf-8"),
        )

    def test_sections_unexpected_closing_brace(self):
        string = outdent(
            """\
            }
            """
        )
        self.assertRaises(
            config_parser.UnexpectedClosingBraceException,
            config_parser.Parser.parse,
            string.encode("utf-8"),
        )

    def test_sections_unexpected_closing_brace_inner_section(self):
        string = outdent(
            """\
            section1 {
                section1a {
                }

                section1b {
                }
            }
            }
            """
        )
        self.assertRaises(
            config_parser.UnexpectedClosingBraceException,
            config_parser.Parser.parse,
            string.encode("utf-8"),
        )

    def test_sections_missing_closing_brace(self):
        string = outdent(
            """\
            section1 {
            """
        )
        self.assertRaises(
            config_parser.MissingClosingBraceException,
            config_parser.Parser.parse,
            string.encode("utf-8"),
        )

    def test_sections_missing_closing_brace_inner_section(self):
        string = outdent(
            """\
            section1 {
                section1a {

                section1b {
                }
            }
            """
        )
        self.assertRaises(
            config_parser.MissingClosingBraceException,
            config_parser.Parser.parse,
            string.encode("utf-8"),
        )

    def test_junk_line(self):
        string = outdent(
            """\
            name1: value1
            section1 {
                section1a {
                    name1a: value1a
                }
            junk line
                section1b {
                }
            }
            """
        )
        self.assertRaises(
            config_parser.LineIsNotSectionNorKeyValueException,
            config_parser.Parser.parse,
            string.encode("utf-8"),
        )

    def test_comments_attributes(self):
        string = outdent(
            """\
            # junk1
            name1: value1
              #junk2
            name2: value2#junk3
            name3: value3 #junk4
            name4 # junk5: value4
            #junk6 name5: value5
            #junk7
            """
        )
        parsed = outdent(
            """\
            name1: value1
            name2: value2#junk3
            name3: value3 #junk4
            name4 # junk5: value4
            """
        )
        self.assertEqual(
            str(config_parser.Parser.parse(string.encode("utf-8"))), parsed
        )

    def test_comments_sections_closing_brace(self):
        string = outdent(
            """\
            section {
            #}
            """
        )
        self.assertRaises(
            config_parser.MissingClosingBraceException,
            config_parser.Parser.parse,
            string.encode("utf-8"),
        )

    def test_comments_sections_opening_brace(self):
        string = outdent(
            """\
            #section {
            }
            """
        )
        self.assertRaises(
            config_parser.UnexpectedClosingBraceException,
            config_parser.Parser.parse,
            string.encode("utf-8"),
        )

    def test_full_1(self):
        string = outdent(
            """\
            # Please read the corosync.conf.5 manual page
            totem {
            	version: 2

            	# crypto_cipher and crypto_hash: Used for mutual node authentication.
            	# If you choose to enable this, then do remember to create a shared
            	# secret with "corosync-keygen".
            	# enabling crypto_cipher, requires also enabling of crypto_hash.
            	crypto_cipher: none
            	crypto_hash: none

            	# interface: define at least one interface to communicate
            	# over. If you define more than one interface stanza, you must
            	# also set rrp_mode.
            	interface {
                # Rings must be consecutively numbered, starting at 0.
            		ringnumber: 0
            		# This is normally the *network* address of the
            		# interface to bind to. This ensures that you can use
            		# identical instances of this configuration file
            		# across all your cluster nodes, without having to
            		# modify this option.
            		bindnetaddr: 192.168.1.0
            		# However, if you have multiple physical network
            		# interfaces configured for the same subnet, then the
            		# network address alone is not sufficient to identify
            		# the interface Corosync should bind to. In that case,
            		# configure the *host* address of the interface
            		# instead:
            		# bindnetaddr: 192.168.1.1
            		# When selecting a multicast address, consider RFC
            		# 2365 (which, among other things, specifies that
            		# 239.255.x.x addresses are left to the discretion of
            		# the network administrator). Do not reuse multicast
            		# addresses across multiple Corosync clusters sharing
            		# the same network.
            		mcastaddr: 239.255.1.1
            		# Corosync uses the port you specify here for UDP
            		# messaging, and also the immediately preceding
            		# port. Thus if you set this to 5405, Corosync sends
            		# messages over UDP ports 5405 and 5404.
            		mcastport: 5405
            		# Time-to-live for cluster communication packets. The
            		# number of hops (routers) that this ring will allow
            		# itself to pass. Note that multicast routing must be
            		# specifically enabled on most network routers.
            		ttl: 1
            	}
            }

            logging {
            	# Log the source file and line where messages are being
            	# generated. When in doubt, leave off. Potentially useful for
            	# debugging.
            	fileline: off
            	# Log to standard error. When in doubt, set to no. Useful when
            	# running in the foreground (when invoking "corosync -f")
            	to_stderr: no
            	# Log to a log file. When set to "no", the "logfile" option
            	# must not be set.
            	to_logfile: yes
                logfile: /var/log/cluster/corosync.log
            	# Log to the system log daemon. When in doubt, set to yes.
            	to_syslog: yes
            	# Log debug messages (very verbose). When in doubt, leave off.
            	debug: off
            	# Log messages with time stamps. When in doubt, set to on
            	# (unless you are only logging to syslog, where double
            	# timestamps can be annoying).
            	timestamp: on
            	logger_subsys {
            		subsys: QUORUM
            		debug: off
            	}
            }

            quorum {
            	# Enable and configure quorum subsystem (default: off)
            	# see also corosync.conf.5 and votequorum.5
            	#provider: corosync_votequorum
            }
            """
        )
        parsed = outdent(
            """\
            totem {
                version: 2
                crypto_cipher: none
                crypto_hash: none

                interface {
                    ringnumber: 0
                    bindnetaddr: 192.168.1.0
                    mcastaddr: 239.255.1.1
                    mcastport: 5405
                    ttl: 1
                }
            }

            logging {
                fileline: off
                to_stderr: no
                to_logfile: yes
                logfile: /var/log/cluster/corosync.log
                to_syslog: yes
                debug: off
                timestamp: on

                logger_subsys {
                    subsys: QUORUM
                    debug: off
                }
            }

            quorum {
            }
            """
        )
        self.assertEqual(
            str(config_parser.Parser.parse(string.encode("utf-8"))), parsed
        )

    def test_full_2(self):
        string = outdent(
            """\
            # Please read the corosync.conf.5 manual page
            totem {
            	version: 2

            	crypto_cipher: none
            	crypto_hash: none

            	interface {
            		ringnumber: 0
            		bindnetaddr: 10.16.35.0
            		mcastport: 5405
            		ttl: 1
            	}
            	transport: udpu
            }

            logging {
            	fileline: off
            	to_logfile: yes
            	to_syslog: yes
                logfile: /var/log/cluster/corosync.log
            	debug: off
            	timestamp: on
            	logger_subsys {
            		subsys: QUORUM
            		debug: off
            	}
            }

            nodelist {
            	node {
            		ring0_addr: 10.16.35.101
            		nodeid: 1
            	}

            	node {
            		ring0_addr: 10.16.35.102
            		nodeid: 2
            	}

            	node {
            		ring0_addr: 10.16.35.103
            	}

            	node {
            		ring0_addr: 10.16.35.104
            	}

            	node {
            		ring0_addr: 10.16.35.105
            	}
            }

            quorum {
            	# Enable and configure quorum subsystem (default: off)
            	# see also corosync.conf.5 and votequorum.5
            	#provider: corosync_votequorum
            }
            """
        )
        parsed = outdent(
            """\
            totem {
                version: 2
                crypto_cipher: none
                crypto_hash: none
                transport: udpu

                interface {
                    ringnumber: 0
                    bindnetaddr: 10.16.35.0
                    mcastport: 5405
                    ttl: 1
                }
            }

            logging {
                fileline: off
                to_logfile: yes
                to_syslog: yes
                logfile: /var/log/cluster/corosync.log
                debug: off
                timestamp: on

                logger_subsys {
                    subsys: QUORUM
                    debug: off
                }
            }

            nodelist {
                node {
                    ring0_addr: 10.16.35.101
                    nodeid: 1
                }

                node {
                    ring0_addr: 10.16.35.102
                    nodeid: 2
                }

                node {
                    ring0_addr: 10.16.35.103
                }

                node {
                    ring0_addr: 10.16.35.104
                }

                node {
                    ring0_addr: 10.16.35.105
                }
            }

            quorum {
            }
            """
        )
        self.assertEqual(
            str(config_parser.Parser.parse(string.encode("utf-8"))), parsed
        )


class VerifySection(TestCase):
    def test_empty_section(self):
        section = config_parser.Section("mySection")
        self.assertEqual(config_parser.verify_section(section), ([], [], []))

    def test_all_valid(self):
        text = outdent(
            """\
            name1: value1
            name2: value2

            child1 {
                name1_1: value1.1
                name1_2: value1.2

                child1A {
                    name1A1: value
                }
                child1B {
                    name1B1: value
                    name1B2: value
                }
            }

            child2 {
                child2 {
                    name: value
                }
            }
            """
        )
        section = config_parser.Parser.parse(text.encode("utf-8"))
        self.assertEqual(config_parser.verify_section(section), ([], [], []))

    def test_bad_section(self):
        section = config_parser.Section("my#section")
        self.assertEqual(
            config_parser.verify_section(section), (["my#section"], [], [])
        )

    def test_bad_attr_name(self):
        section = config_parser.Section("mySection")
        section.add_attribute("bad#name", "value1")
        section.add_attribute("good_name", "value2")
        self.assertEqual(
            config_parser.verify_section(section),
            ([], ["mySection.bad#name"], []),
        )

    def test_bad_attr_value(self):
        section = config_parser.Section("mySection")
        section.add_attribute("bad_value", "va{l}ue1")
        section.add_attribute("good_value", "value2")
        self.assertEqual(
            config_parser.verify_section(section),
            ([], [], [("mySection.bad_value", "va{l}ue1")]),
        )

    def test_complex(self):
        text = outdent(
            """\
            name1: value1
            name#2: value2

            child1 {
                name1_1: value1.1
                name1#2: value1.2

                child1A {
                    name1A1: value
                }
                child1B# {
                    name#1B1: value
                    name1B2: value
                }
            }

            child2 {
                child2# {
                    na#me: value
                }
            }
            """
        )
        section = config_parser.Parser.parse(text.encode("utf-8"))
        # this would be rejected by the parser
        section.add_attribute("name1_3", "va{l}ue")
        self.assertEqual(
            config_parser.verify_section(section),
            (
                ["child1.child1B#", "child2.child2#"],
                [
                    "name#2",
                    "child1.name1#2",
                    "child1.child1B#.name#1B1",
                    "child2.child2#.na#me",
                ],
                [("name1_3", "va{l}ue")],
            ),
        )
