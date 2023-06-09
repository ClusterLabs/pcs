from textwrap import dedent
from unittest import TestCase

from pcs.cli.cluster_property import output as cluster_property
from pcs.cli.cluster_property.output import PropertyConfigurationFacade
from pcs.common.pacemaker.cluster_property import ClusterPropertyMetadataDto
from pcs.common.pacemaker.nvset import (
    CibNvpairDto,
    CibNvsetDto,
    ListCibNvsetDto,
)
from pcs.common.resource_agent.dto import ResourceAgentParameterDto

FIXTURE_TWO_PROPERTY_SETS = [
    CibNvsetDto(
        id="id1",
        options={"score": "150"},
        rule=None,
        nvpairs=[
            CibNvpairDto(id="", name="readonly1", value="ro_val1"),
            CibNvpairDto(id="", name="readonly2", value="ro_val2"),
            CibNvpairDto(id="", name="property2", value="val2"),
            CibNvpairDto(id="", name="property1", value="val1"),
        ],
    ),
    CibNvsetDto(
        id="id2",
        options={"score": "100"},
        rule=None,
        nvpairs=[
            CibNvpairDto(id="", name="readonly3", value="ro_val3"),
            CibNvpairDto(id="", name="property3", value="val3"),
        ],
    ),
]

FIXTURE_READONLY_PROPERTIES_LIST = ["readonly1", "readonly2"]

FIXTURE_TEXT_OUTPUT_FIRST_SET = dedent(
    """\
    Cluster Properties: id1 score=150
      property1=val1
      property2=val2
      readonly1=ro_val1
      readonly2=ro_val2
    """
)

FIXTURE_LEGACY_TEXT_OUTPUT_FIRST_SET = dedent(
    """\
    Cluster Properties:
     property1: val1
     property2: val2
     readonly1: ro_val1
     readonly2: ro_val2
    """
)


def fixture_property_metadata(
    name="property-name",
    shortdesc=None,
    longdesc=None,
    type="string",
    default=None,
    enum_values=None,
    advanced=False,
):
    # pylint: disable=redefined-builtin
    return ResourceAgentParameterDto(
        name=name,
        shortdesc=shortdesc,
        longdesc=longdesc,
        type=type,
        default=default,
        enum_values=enum_values,
        required=False,
        advanced=advanced,
        deprecated=False,
        deprecated_by=[],
        deprecated_desc=None,
        unique_group=None,
        reloadable=False,
    )


FIXTURE_PROPERTY_METADATA_LIST = [
    fixture_property_metadata(name="property1", default="default1"),
    fixture_property_metadata(name="property2", default="default2"),
    fixture_property_metadata(
        name="property3", default="default3", advanced=True
    ),
    fixture_property_metadata(
        name="property4", default="default4", advanced=True
    ),
]

FIXTURE_PROPERTIES_FACADE = PropertyConfigurationFacade(
    properties=[
        CibNvsetDto(
            id="id1",
            options={},
            rule=None,
            nvpairs=[
                CibNvpairDto(id="", name="readonly1", value="ro_val1"),
                CibNvpairDto(id="", name="readonly2", value="ro_val2"),
                CibNvpairDto(id="", name="property2", value="val2"),
                CibNvpairDto(id="", name="property1", value="default1"),
            ],
        )
    ],
    properties_metadata=FIXTURE_PROPERTY_METADATA_LIST,
    readonly_properties=FIXTURE_READONLY_PROPERTIES_LIST,
)


class TestPropertyConfigurationFacadeCreate(TestCase):
    def test_from_properties_dtos(self):
        facade = PropertyConfigurationFacade.from_properties_dtos(
            properties_dto=ListCibNvsetDto(nvsets=FIXTURE_TWO_PROPERTY_SETS),
            properties_metadata_dto=ClusterPropertyMetadataDto(
                properties_metadata=FIXTURE_PROPERTY_METADATA_LIST,
                readonly_properties=FIXTURE_READONLY_PROPERTIES_LIST,
            ),
        )
        self.assertEqual(facade.properties, FIXTURE_TWO_PROPERTY_SETS)
        self.assertEqual(
            facade.properties_metadata, FIXTURE_PROPERTY_METADATA_LIST
        )
        self.assertEqual(
            facade.readonly_properties, FIXTURE_READONLY_PROPERTIES_LIST
        )

    def test_from_properties_config(self):
        facade = PropertyConfigurationFacade.from_properties_config(
            properties_dto=ListCibNvsetDto(nvsets=FIXTURE_TWO_PROPERTY_SETS)
        )
        self.assertEqual(facade.properties, FIXTURE_TWO_PROPERTY_SETS)
        self.assertEqual(facade.properties_metadata, [])
        self.assertEqual(facade.readonly_properties, [])

    def test_from_properties_metadata(self):
        facade = PropertyConfigurationFacade.from_properties_metadata(
            properties_metadata_dto=ClusterPropertyMetadataDto(
                properties_metadata=FIXTURE_PROPERTY_METADATA_LIST,
                readonly_properties=FIXTURE_READONLY_PROPERTIES_LIST,
            ),
        )
        self.assertEqual(facade.properties, [])
        self.assertEqual(
            facade.properties_metadata, FIXTURE_PROPERTY_METADATA_LIST
        )
        self.assertEqual(
            facade.readonly_properties, FIXTURE_READONLY_PROPERTIES_LIST
        )


class TestPropertyConfigurationFacadeGetPropertyValue(TestCase):
    def setUp(self):
        self.facade = PropertyConfigurationFacade(
            properties=FIXTURE_TWO_PROPERTY_SETS,
            properties_metadata=[],
            readonly_properties=[],
        )

    def test_property_value_from_first_set(self):
        self.assertEqual(self.facade.get_property_value("property1"), "val1")

    def test_property_value_from_second_set(self):
        self.assertEqual(self.facade.get_property_value("property3"), None)

    def test_property_value_not_in_set(self):
        self.assertEqual(self.facade.get_property_value("not-there"), None)

    def test_custom_default(self):
        self.assertEqual(
            self.facade.get_property_value(
                "not-there", custom_default="custom"
            ),
            "custom",
        )


class TestPropertyConfigurationFacadeGetPropertyValueOrDefault(TestCase):
    def setUp(self):
        self.facade = PropertyConfigurationFacade(
            properties=FIXTURE_TWO_PROPERTY_SETS,
            properties_metadata=FIXTURE_PROPERTY_METADATA_LIST,
            readonly_properties=FIXTURE_READONLY_PROPERTIES_LIST,
        )

    def test_property_value_from_first_set(self):
        self.assertEqual(
            self.facade.get_property_value_or_default("property1"), "val1"
        )

    def test_property_value_not_in_set(self):
        self.assertEqual(
            self.facade.get_property_value_or_default("property3"), "default3"
        )

    def test_custom_default_with_existing_default(self):
        self.assertEqual(
            self.facade.get_property_value_or_default(
                "property3", custom_default="custom"
            ),
            "default3",
        )

    def test_custom_default_with_not_existing_default(self):
        self.assertEqual(
            self.facade.get_property_value_or_default(
                "not-there", custom_default="custom"
            ),
            "custom",
        )


class TestPropertyConfigurationFacadeGetDefaults(TestCase):
    def setUp(self):
        self.facade = PropertyConfigurationFacade(
            properties=[],
            properties_metadata=FIXTURE_PROPERTY_METADATA_LIST,
            readonly_properties=FIXTURE_READONLY_PROPERTIES_LIST,
        )

    def test_defaults_not_advanced(self):
        result_dict = {"property1": "default1", "property2": "default2"}
        self.assertEqual(self.facade.get_defaults(), result_dict)

    def test_defaults_advanced(self):
        result_dict = {
            "property1": "default1",
            "property2": "default2",
            "property3": "default3",
            "property4": "default4",
        }
        self.assertEqual(
            self.facade.get_defaults(include_advanced=True), result_dict
        )

    def test_specified(self):
        result_dict = {"property1": "default1", "property4": "default4"}
        self.assertEqual(
            self.facade.get_defaults(
                property_names=["property4", "property1", "nodefault1"]
            ),
            result_dict,
        )

    def test_properties_without_defaults(self):
        result_dict = {}
        self.assertEqual(
            self.facade.get_defaults(
                property_names=["nodefault1", "nodefault2"]
            ),
            result_dict,
        )


class TestPropertyConfigurationFacadeGetPropertiesMetadata(TestCase):
    def setUp(self):
        self.facade = PropertyConfigurationFacade(
            properties=[],
            properties_metadata=FIXTURE_PROPERTY_METADATA_LIST,
            readonly_properties=[],
        )

    def test_metadata_without_advanced(self):
        metadata = FIXTURE_PROPERTY_METADATA_LIST[0:2]
        self.assertEqual(self.facade.get_properties_metadata(), metadata)

    def test_metadata_with_advanced(self):
        metadata = FIXTURE_PROPERTY_METADATA_LIST
        self.assertEqual(
            self.facade.get_properties_metadata(include_advanced=True), metadata
        )

    def test_metadata_specified(self):
        metadata = (
            FIXTURE_PROPERTY_METADATA_LIST[0:1]
            + FIXTURE_PROPERTY_METADATA_LIST[-1:]
        )
        self.assertEqual(
            self.facade.get_properties_metadata(
                property_names=["property4", "property1"]
            ),
            metadata,
        )


class TestPropertyConfigurationFacadeGetNameValueDefaultList(TestCase):
    def setUp(self):
        self.facade = PropertyConfigurationFacade(
            properties=FIXTURE_TWO_PROPERTY_SETS,
            properties_metadata=FIXTURE_PROPERTY_METADATA_LIST,
            readonly_properties=FIXTURE_READONLY_PROPERTIES_LIST,
        )

    def test_get_name_value_default_list(self):
        tuple_list = [
            ("readonly1", "ro_val1", False),
            ("readonly2", "ro_val2", False),
            ("property2", "val2", False),
            ("property1", "val1", False),
            ("property3", "default3", True),
            ("property4", "default4", True),
        ]
        self.assertEqual(self.facade.get_name_value_default_list(), tuple_list)


class TestPropertiesToText(TestCase):
    def assert_lines(self, facade, output):
        self.assertEqual(
            "\n".join(cluster_property.properties_to_text(facade)) + "\n",
            output,
        )

    def test_no_cluster_properties(self):
        facade = PropertyConfigurationFacade(
            properties=[], properties_metadata=[], readonly_properties=[]
        )
        output = "Cluster Properties:\n"
        self.assert_lines(facade, output)

    def test_empty_cluster_property_set(self):
        facade = PropertyConfigurationFacade(
            properties=[
                CibNvsetDto(id="id1", options={}, rule=None, nvpairs=[])
            ],
            properties_metadata=[],
            readonly_properties=[],
        )
        output = dedent(
            """\
            Cluster Properties: id1
            """
        )
        self.assert_lines(facade, output)

    def test_one_cluster_property_set(self):
        facade = PropertyConfigurationFacade(
            properties=FIXTURE_TWO_PROPERTY_SETS[0:1],
            properties_metadata=[],
            readonly_properties=[],
        )
        output = FIXTURE_TEXT_OUTPUT_FIRST_SET
        self.assert_lines(facade, output)

    def test_more_cluster_property_sets_first_is_displayed(self):
        facade = PropertyConfigurationFacade(
            properties=FIXTURE_TWO_PROPERTY_SETS,
            properties_metadata=[],
            readonly_properties=[],
        )
        output = FIXTURE_TEXT_OUTPUT_FIRST_SET
        self.assert_lines(facade, output)


class TestPropertiesToTextWithDefaultMark(TestCase):
    def assert_lines(self, facade, output, property_names=None):
        self.assertEqual(
            "\n".join(
                cluster_property.properties_to_text_with_default_mark(
                    facade, property_names=property_names
                )
            )
            + "\n",
            output,
        )

    def test_no_cluster_properties_and_no_defaults(self):
        facade = PropertyConfigurationFacade(
            properties=[], properties_metadata=[], readonly_properties=[]
        )
        output = dedent(
            """\
            Cluster Properties:
            """
        )
        self.assert_lines(facade, output)

    def test_no_cluster_properties_and_defaults_only(self):
        facade = PropertyConfigurationFacade(
            properties=[],
            properties_metadata=FIXTURE_PROPERTY_METADATA_LIST,
            readonly_properties=[],
        )
        output = dedent(
            """\
            Cluster Properties:
              property1=default1 (default)
              property2=default2 (default)
              property3=default3 (default)
              property4=default4 (default)
            """
        )
        self.assert_lines(facade, output)

    def test_configured_properties_and_properties_with_defaults(self):
        facade = PropertyConfigurationFacade(
            properties=[
                CibNvsetDto(
                    id="id1",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(id="", name="readonly1", value="ro_val1"),
                        CibNvpairDto(id="", name="readonly2", value="ro_val2"),
                        CibNvpairDto(id="", name="property2", value="val2"),
                        CibNvpairDto(id="", name="property1", value="default1"),
                    ],
                )
            ],
            properties_metadata=FIXTURE_PROPERTY_METADATA_LIST,
            readonly_properties=FIXTURE_READONLY_PROPERTIES_LIST,
        )
        output = dedent(
            """\
            Cluster Properties: id1
              property1=default1
              property2=val2
              property3=default3 (default)
              property4=default4 (default)
              readonly1=ro_val1
              readonly2=ro_val2
            """
        )
        self.assert_lines(facade, output)

    def test_specified_properties(self):
        facade = PropertyConfigurationFacade(
            properties=[
                CibNvsetDto(
                    id="id1",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(id="", name="readonly1", value="ro_val1"),
                        CibNvpairDto(id="", name="readonly2", value="ro_val2"),
                        CibNvpairDto(id="", name="property2", value="val2"),
                        CibNvpairDto(id="", name="property1", value="default1"),
                    ],
                )
            ],
            properties_metadata=FIXTURE_PROPERTY_METADATA_LIST,
            readonly_properties=FIXTURE_READONLY_PROPERTIES_LIST,
        )
        output = dedent(
            """\
            Cluster Properties: id1
              property2=val2
              property4=default4 (default)
              readonly2=ro_val2
            """
        )
        self.assert_lines(
            facade,
            output,
            property_names=["property2", "readonly2", "property4", "other"],
        )


class TestPropertiesToCmd(TestCase):
    def assert_lines(self, facade, output):
        self.assertEqual(
            " \\\n".join(cluster_property.properties_to_cmd(facade)) + "\n",
            output,
        )

    def test_no_cluster_properties(self):
        facade = PropertyConfigurationFacade(
            properties=[], properties_metadata=[], readonly_properties=[]
        )
        output = "\n"
        self.assert_lines(facade, output)

    def test_only_readonly_properties(self):
        facade = PropertyConfigurationFacade(
            properties=[
                CibNvsetDto(
                    id="id1",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(id="", name="readonly1", value="ro_val1"),
                        CibNvpairDto(id="", name="readonly2", value="ro_val2"),
                    ],
                )
            ],
            properties_metadata=[],
            readonly_properties=["readonly1", "readonly2"],
        )
        output = "\n"
        self.assert_lines(facade, output)

    def test_properties_cmd_without_readonly_properties(self):
        facade = PropertyConfigurationFacade(
            properties=[
                CibNvsetDto(
                    id="id1",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(id="", name="readonly1", value="ro_val1"),
                        CibNvpairDto(id="", name="readonly2", value="ro_val2"),
                        CibNvpairDto(id="", name="property2", value="val2"),
                        CibNvpairDto(id="", name="property1", value="val1"),
                    ],
                )
            ],
            properties_metadata=[],
            readonly_properties=["readonly1", "readonly2"],
        )
        output = dedent(
            """\
            pcs property set --force -- \\
              property2=val2 \\
              property1=val1
            """
        )
        self.assert_lines(facade, output)

    def test_only_first_set_is_supported_for_cmd_output(self):
        facade = PropertyConfigurationFacade(
            properties=FIXTURE_TWO_PROPERTY_SETS,
            properties_metadata=[],
            readonly_properties=["readonly1", "readonly2"],
        )
        output = dedent(
            """\
            pcs property set --force -- \\
              property2=val2 \\
              property1=val1
            """
        )
        self.assert_lines(facade, output)


class TestPropertiesDefaultsToText(TestCase):
    def assert_lines(self, defaults_dict, lines):
        self.assertEqual(
            "\n".join(
                cluster_property.properties_defaults_to_text(defaults_dict)
            )
            + "\n",
            lines,
        )

    def test_no_defaults(self):
        defaults = {}
        output = "\n"
        self.assert_lines(defaults, output)

    def test_some_defaults(self):
        defaults = {"def1": "val1", "def2": "val2", "def3": "val3"}
        output = dedent(
            """\
            def1=val1
            def2=val2
            def3=val3
            """
        )
        self.assert_lines(defaults, output)


class TestClusterPropertyMetadataToText(TestCase):
    def assert_lines(self, metadata, lines):
        self.assertEqual(
            "\n".join(
                cluster_property.cluster_property_metadata_to_text(metadata)
            )
            + "\n",
            lines,
        )

    def test_multiple_properties_metadata(self):
        metadata = [
            fixture_property_metadata(
                name="property-a",
                shortdesc="desc",
                type="percentage",
                default="80%",
                advanced=True,
            ),
            fixture_property_metadata(
                name="property-b",
                type="some type",
                enum_values=["a", "b"],
                default="a",
            ),
        ]
        output = dedent(
            """\
            property-a (advanced use only)
              Description: desc
              Type: percentage
              Default: 80%
            property-b
              Description: No description available
              Allowed values: 'a', 'b'
              Default: a
            """
        )
        self.assert_lines(metadata, output)

    def test_empty_metadata(self):
        metadata = []
        output = "\n"
        self.assert_lines(metadata, output)

    def test_no_longdesc_and_shortdesc_defined(self):
        metadata = [fixture_property_metadata()]
        output = dedent(
            """\
            property-name
              Description: No description available
              Type: string
            """
        )
        self.assert_lines(metadata, output)

    def test_longdesc_and_shortdesc_defined(self):
        metadata = [
            fixture_property_metadata(
                shortdesc="'\nshort\ndesc\n'", longdesc="'\nlong\ndesc\n'"
            )
        ]
        output = dedent(
            """\
            property-name
              Description: ' long desc '
              Type: string
            """
        )
        self.assert_lines(metadata, output)

    def test_shortdesc_only(self):
        metadata = [fixture_property_metadata(shortdesc="'\nshort\ndesc\n'")]
        output = dedent(
            """\
            property-name
              Description: ' short desc '
              Type: string
            """
        )
        self.assert_lines(metadata, output)

    def test_enum_values(self):
        metadata = [
            fixture_property_metadata(
                type="select", enum_values=["a", "b", "c"]
            )
        ]
        output = dedent(
            """\
            property-name
              Description: No description available
              Allowed values: 'a', 'b', 'c'
            """
        )
        self.assert_lines(metadata, output)

    def test_default_value(self):
        metadata = [fixture_property_metadata(default="default_value")]
        output = dedent(
            """\
            property-name
              Description: No description available
              Type: string
              Default: default_value
            """
        )
        self.assert_lines(metadata, output)

    def test_advanced_value(self):
        metadata = [fixture_property_metadata(advanced=True)]
        output = dedent(
            """\
            property-name (advanced use only)
              Description: No description available
              Type: string
            """
        )
        self.assert_lines(metadata, output)


class TestPropertiesToTextLegacy(TestCase):
    def assert_lines(
        self,
        facade,
        output,
        property_names=None,
        defaults_only=False,
        include_defaults=False,
    ):
        self.assertEqual(
            "\n".join(
                cluster_property.properties_to_text_legacy(
                    facade, property_names, defaults_only, include_defaults
                )
            )
            + "\n",
            output,
        )

    def test_no_cluster_properties(self):
        facade = PropertyConfigurationFacade(
            properties=[], properties_metadata=[], readonly_properties=[]
        )
        output = "Cluster Properties:\n"
        self.assert_lines(facade, output)

    def test_empty_cluster_property_set(self):
        facade = PropertyConfigurationFacade(
            properties=[
                CibNvsetDto(id="id1", options={}, rule=None, nvpairs=[])
            ],
            properties_metadata=[],
            readonly_properties=[],
        )
        output = dedent(
            """\
            Cluster Properties:
            """
        )
        self.assert_lines(facade, output)

    def test_one_cluster_property_set(self):
        facade = PropertyConfigurationFacade(
            properties=FIXTURE_TWO_PROPERTY_SETS[0:1],
            properties_metadata=[],
            readonly_properties=[],
        )
        output = FIXTURE_LEGACY_TEXT_OUTPUT_FIRST_SET
        self.assert_lines(facade, output)

    def test_more_cluster_property_sets_first_is_displayed(self):
        facade = PropertyConfigurationFacade(
            properties=FIXTURE_TWO_PROPERTY_SETS,
            properties_metadata=[],
            readonly_properties=[],
        )
        output = FIXTURE_LEGACY_TEXT_OUTPUT_FIRST_SET
        self.assert_lines(facade, output)

    def test_specified_properties(self):
        facade = FIXTURE_PROPERTIES_FACADE
        output = dedent(
            """\
            Cluster Properties:
             property2: val2
             property4: default4
             readonly2: ro_val2
            """
        )
        self.assert_lines(
            facade,
            output,
            property_names=["property2", "readonly2", "property4", "other"],
        )

    def test_defaults(self):
        facade = FIXTURE_PROPERTIES_FACADE
        output = dedent(
            """\
            Cluster Properties:
             property1: default1
             property2: default2
             property3: default3
             property4: default4
            """
        )
        self.assert_lines(facade, output, defaults_only=True)

    def test_all(self):
        facade = FIXTURE_PROPERTIES_FACADE
        output = dedent(
            """\
            Cluster Properties:
             property1: default1
             property2: val2
             property3: default3
             property4: default4
             readonly1: ro_val1
             readonly2: ro_val2
            """
        )
        self.assert_lines(facade, output, include_defaults=True)

    def test_assertion_error(self):
        with self.assertRaises(AssertionError) as cm:
            cluster_property.properties_to_text_legacy(
                FIXTURE_PROPERTIES_FACADE,
                property_names=["property_name1"],
                include_defaults=True,
            )
        self.assertEqual(
            str(cm.exception), "Mutually exclusive parameters were used."
        )
