from textwrap import dedent
from unittest import TestCase

from lxml import etree

from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    outdent,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner

empty_cib = rc("cib-empty.xml")
tags_cib = rc("cib-tags.xml")


class TestTagMixin(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//tags")[0]
        )
    )
):
    def setUp(self):
        # pylint: disable=invalid-name
        self.temp_cib = get_tmp_file("tier1_tag")
        write_file_to_tmpfile(tags_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        # pylint: disable=invalid-name
        self.temp_cib.close()

    @staticmethod
    def fixture_tags_xml(tag1=None, append=""):
        tag1_default = """
            <tag id="tag1">
                <obj_ref id="x1"/>
                <obj_ref id="x2"/>
                <obj_ref id="x3"/>
            </tag>
        """
        if tag1 is None:
            tag1 = tag1_default
        return f"""
            <tags>
                {tag1}
                <tag id="tag2">
                    <obj_ref id="y1"/>
                    <obj_ref id="x2"/>
                </tag>
                <tag id="tag3">
                    <obj_ref id="y2-clone"/>
                </tag>
                <tag id="tag-mixed-stonith-devices-and-resources">
                    <obj_ref id="fence-rh-2"/>
                    <obj_ref id="y1"/>
                    <obj_ref id="fence-rh-1"/>
                    <obj_ref id="x3"/>
                </tag>
                {append}
            </tags>
        """


class TagCreate(TestTagMixin, TestCase):
    def test_create_success(self):
        self.assert_effect(
            "tag create new x1 x2".split(),
            self.fixture_tags_xml(
                append=(
                    """
                    <tag id="new">
                        <obj_ref id="x1"/>
                        <obj_ref id="x2"/>
                    </tag>
                    """
                ),
            ),
        )

    def test_create_not_enough_arguments(self):
        self.assert_pcs_fail(
            "tag create".split(),
            stderr_start="\nUsage: pcs tag <command>",
        )
        self.assert_pcs_fail(
            "tag create tag".split(),
            stderr_start="\nUsage: pcs tag <command>",
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_create_invalid_tag_id(self):
        self.assert_pcs_fail(
            "tag create 1tag x1 x2".split(),
            (
                "Error: invalid id '1tag', '1' is not a valid first character "
                "for a id\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_create_nonexistent_ids(self):
        self.assert_pcs_fail(
            "tag create tag noid-01 noid-02".split(),
            (
                "Error: bundle/clone/group/resource 'noid-01' does not exist\n"
                "Error: bundle/clone/group/resource 'noid-02' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_create_duplicate_ids(self):
        self.assert_pcs_fail(
            "tag create tag x2 x2 x1 x1 x3".split(),
            (
                "Error: Ids to add must be unique, duplicate ids: 'x1', "
                "'x2'\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_create_tag_id_already_exists(self):
        self.assert_pcs_fail(
            "tag create x1 x2 x3".split(),
            (
                "Error: 'x1' already exists\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_create_tag_contains_itself(self):
        self.assert_pcs_fail(
            "tag create x1 x1".split(),
            (
                "Error: 'x1' already exists\n"
                "Error: Tag cannot contain itself\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_create_nonresource_ref_id(self):
        self.assert_pcs_fail(
            "tag create tag cx1 cx2".split(),
            (
                "Error: 'cx1' is not a bundle/clone/group/resource\n"
                "Error: 'cx2' is not a bundle/clone/group/resource\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())


class TagConfigListBase(TestTagMixin):
    command = None
    deprecation_msg = ""

    def test_config_empty(self):
        write_file_to_tmpfile(empty_cib, self.temp_cib)

        self.assert_pcs_success(
            ["tag"],
            stderr_full=" No tags defined\n",
        )

        self.assert_pcs_success(
            ["tag", self.command],
            stderr_full=(self.deprecation_msg + " No tags defined\n"),
        )

    def test_config_tag_does_not_exist(self):
        self.assert_pcs_fail(
            ["tag", self.command, "notag2", "notag1"],
            (
                self.deprecation_msg + "Error: tag 'notag2' does not exist\n"
                "Error: tag 'notag1' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_config_tags_defined(self):
        self.assert_pcs_success(
            ["tag", self.command],
            dedent(
                """\
                tag1
                  x1
                  x2
                  x3
                tag2
                  y1
                  x2
                tag3
                  y2-clone
                tag-mixed-stonith-devices-and-resources
                  fence-rh-2
                  y1
                  fence-rh-1
                  x3
                """
            ),
            stderr_full=self.deprecation_msg,
        )

    def test_config_specified_tags(self):
        self.assert_pcs_success(
            ["tag", self.command, "tag2", "tag1"],
            dedent(
                """\
                tag2
                  y1
                  x2
                tag1
                  x1
                  x2
                  x3
                """
            ),
            stderr_full=self.deprecation_msg,
        )


class TagConfig(
    TagConfigListBase,
    TestCase,
):
    command = "config"


class TagList(
    TagConfigListBase,
    TestCase,
):
    command = "list"
    deprecation_msg = (
        "Deprecation Warning: This command is deprecated and will be removed. "
        "Please use 'pcs tag config' instead.\n"
    )


class PcsConfigTagsTest(TestTagMixin, TestCase):
    config_template = dedent(
        """\
        Cluster Name: test99
        Corosync Nodes:
         rh7-1 rh7-2
        {pacemaker_nodes}{resources}{stonith_devices}{fencing_levels}{constraints}{tags}"""
    )
    empty_pacemaker_nodes = "Pacemaker Nodes:\n"
    empty_resources = ""
    empty_stonith_devices = ""
    empty_fencing_levels = ""
    empty_constraints = ""
    empty_tags = ""
    expected_pacemaker_nodes = outdent(
        """\
        Pacemaker Nodes:
         rh-1 rh-2
        """
    )
    expected_resources = outdent(
        """
        Resources:
          Resource: not-in-tags (class=ocf provider=pacemaker type=Dummy)
            Operations:
              monitor: not-in-tags-monitor-interval-10s
                interval=10s timeout=20s
          Resource: x1 (class=ocf provider=pacemaker type=Dummy)
            Operations:
              monitor: x1-monitor-interval-10s
                interval=10s timeout=20s
          Resource: x2 (class=ocf provider=pacemaker type=Dummy)
            Operations:
              monitor: x2-monitor-interval-10s
                interval=10s timeout=20s
          Resource: x3 (class=ocf provider=pacemaker type=Dummy)
            Operations:
              monitor: x3-monitor-interval-10s
                interval=10s timeout=20s
          Resource: y1 (class=ocf provider=pacemaker type=Dummy)
            Operations:
              monitor: y1-monitor-interval-10s
                interval=10s timeout=20s
          Clone: y2-clone
            Resource: y2 (class=ocf provider=pacemaker type=Dummy)
              Operations:
                monitor: y2-monitor-interval-10s
                  interval=10s timeout=20s
        """
    )
    expected_stonith_devices = outdent(
        """
        Stonith Devices:
          Resource: fence-rh-1 (class=stonith type=fence_xvm)
            Operations:
              monitor: fence-rh-1-monitor-interval-60s
                interval=60s
          Resource: fence-rh-2 (class=stonith type=fence_xvm)
            Operations:
              monitor: fence-rh-2-monitor-interval-60s
                interval=60s
          Resource: fence-kdump (class=stonith type=fence_kdump)
            Attributes: fence-kdump-instance_attributes
              pcmk_host_list="rh-1 rh-2"
            Operations:
              monitor: fence-kdump-monitor-interval-60s
                interval=60s
        """
    )
    expected_fencing_levels = outdent(
        """
        Fencing Levels:
          Target: rh-1
            Level 1 - fence-kdump
            Level 2 - fence-rh-1
          Target: rh-2
            Level 1 - fence-kdump
            Level 2 - fence-rh-2
        """
    )
    expected_tags = outdent(
        """
        Tags:
         tag1
           x1
           x2
           x3
         tag2
           y1
           x2
         tag3
           y2-clone
         tag-mixed-stonith-devices-and-resources
           fence-rh-2
           y1
           fence-rh-1
           x3
        """
    )
    expected_constraints = outdent(
        """
        Location Constraints:
          resource 'x1' prefers node 'rh7-1' with score INFINITY (id: cx1)
          resource 'x2' prefers node 'rh7-1' with score INFINITY (id: cx2)
        """
    )

    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = {
            "corosync_conf_file": rc("corosync.conf")
        }

    def fixture_expected_config(
        self,
        constraints=empty_constraints,
        pacemaker_nodes=empty_pacemaker_nodes,
        resources=empty_resources,
        stonith_devices=empty_stonith_devices,
        fencing_levels=empty_fencing_levels,
        tags=empty_tags,
    ):
        return self.config_template.format(
            constraints=constraints,
            pacemaker_nodes=pacemaker_nodes,
            resources=resources,
            stonith_devices=stonith_devices,
            fencing_levels=fencing_levels,
            tags=tags,
        )

    def test_config_no_tags(self):
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner.mock_settings = {
            "corosync_conf_file": rc("corosync.conf")
        }

        self.assert_pcs_success(["config"], self.fixture_expected_config())

    def test_config_tags_defined(self):
        self.assert_pcs_success(
            ["config"],
            self.fixture_expected_config(
                constraints=self.expected_constraints,
                pacemaker_nodes=self.expected_pacemaker_nodes,
                resources=self.expected_resources,
                stonith_devices=self.expected_stonith_devices,
                fencing_levels=self.expected_fencing_levels,
                tags=self.expected_tags,
            ),
        )


class TagRemoveDeleteBase(TestTagMixin):
    command = None

    def test_remove_not_enough_arguments(self):
        self.assert_pcs_fail(
            ["tag", self.command],
            stderr_start="\nUsage: pcs tag <command>",
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_remove_nonexistent_tags(self):
        self.assert_pcs_fail(
            ["tag", self.command, "tagY", "tagX"],
            (
                "Error: tag 'tagY' does not exist\n"
                "Error: tag 'tagX' does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_remove_one_tag(self):
        self.assert_effect(
            ["tag", self.command, "tag1"],
            self.fixture_tags_xml(tag1=""),
        )

    def test_remove_all_tags(self):
        self.assert_effect(
            [
                "tag",
                self.command,
                "tag1",
                "tag2",
                "tag3",
                "tag-mixed-stonith-devices-and-resources",
            ],
            """
            <tags/>
            """,
        )


class TagRemove(
    TagRemoveDeleteBase,
    TestCase,
):
    command = "remove"


class TagDelete(
    TagRemoveDeleteBase,
    TestCase,
):
    command = "delete"


class ResourceRemoveDeleteBase(TestTagMixin):
    command = None

    @staticmethod
    def fixture_error_message(resource, tags):
        return (
            "Error: Unable to remove resource '{resource}' because it is "
            "referenced in {tags}: {tag_list}\n".format(
                resource=resource,
                tags="tags" if len(tags) > 1 else "the tag",
                tag_list=", ".join(f"'{tag}'" for tag in tags),
            )
        )

    def test_resource_not_referenced_in_tags(self):
        self.assert_pcs_success(
            ["resource", self.command, "not-in-tags"],
            stderr_full="Deleting Resource - not-in-tags\n",
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_resource_referenced_in_a_single_tag(self):
        self.assert_pcs_fail(
            ["resource", self.command, "x1"],
            self.fixture_error_message("x1", ["tag1"]),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_resource_referenced_in_multiple_tags(self):
        self.assert_pcs_fail(
            ["resource", self.command, "x2"],
            self.fixture_error_message("x2", ["tag1", "tag2"]),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_related_clone_resource_in_tag(self):
        self.assert_pcs_fail(
            ["resource", self.command, "y2"],
            self.fixture_error_message("y2", ["tag3"]),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())


class ResourceRemove(
    ResourceRemoveDeleteBase,
    TestCase,
):
    command = "remove"


class ResourceDelete(
    ResourceRemoveDeleteBase,
    TestCase,
):
    command = "delete"


class TagUpdate(TestTagMixin, TestCase):
    def test_success_add_new_existing_before_and_remove(self):
        self.assert_effect(
            "tag update tag1 add y1 y2 x3 --before x2 remove x1".split(),
            self.fixture_tags_xml(
                tag1=(
                    """
                    <tag id="tag1">
                        <obj_ref id="y1"/>
                        <obj_ref id="y2"/>
                        <obj_ref id="x3"/>
                        <obj_ref id="x2"/>
                    </tag>
                    """
                ),
            ),
        )

    def test_success_add_new_existing_after_and_remove(self):
        self.assert_effect(
            "tag update tag1 add x3 y1 y2 --after x1 remove x2".split(),
            self.fixture_tags_xml(
                tag1=(
                    """
                    <tag id="tag1">
                        <obj_ref id="x1"/>
                        <obj_ref id="x3"/>
                        <obj_ref id="y1"/>
                        <obj_ref id="y2"/>
                    </tag>
                    """
                ),
            ),
        )

    def test_fail_not_enough_arguments(self):
        self.assert_pcs_fail(
            "tag update".split(),
            stderr_start="\nUsage: pcs tag <command>",
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_fail_tag_update_ids_not_specified(self):
        self.assert_pcs_fail(
            "tag update tag1".split(),
            stderr_start=(
                "Hint: Specify at least one id for 'add' or 'remove' arguments."
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_fail_tag_update_add_ids_not_specified(self):
        self.assert_pcs_fail(
            "tag update tag1 add".split(),
            stderr_start=(
                "Hint: Specify at least one id for 'add' or 'remove' arguments."
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_fail_tag_update_remove_ids_not_specified(self):
        self.assert_pcs_fail(
            "tag update tag1 remove".split(),
            stderr_start=(
                "Hint: Specify at least one id for 'add' or 'remove' arguments."
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_fail_tag_and_add_id_not_exist(self):
        self.assert_pcs_fail(
            "tag update nonexisting_tag add nonexisting_resource".split(),
            (
                "Error: tag 'nonexisting_tag' does not exist\n"
                "Error: bundle/clone/group/resource 'nonexisting_resource' "
                "does not exist\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_fail_add_id_exist_but_belongs_to_unexpected_type(self):
        self.assert_pcs_fail(
            "tag update tag1 add cx1".split(),
            (
                "Error: 'cx1' is not a bundle/clone/group/resource\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_fail_id_is_not_tag(self):
        self.assert_pcs_fail(
            "tag update y1 add y1".split(),
            (
                "Error: 'y1' is not a tag\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_fail_add_ids_already_in_tag(self):
        self.assert_pcs_fail(
            "tag update tag1 add x1 x2".split(),
            (
                "Error: Cannot add reference ids already in the tag 'tag1': "
                "'x1', 'x2'\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_fail_before_id_does_not_exist(self):
        self.assert_pcs_fail(
            "tag update tag1 add y1 --before no_id".split(),
            (
                "Error: There is no reference id 'no_id' in the tag 'tag1', "
                "cannot put reference ids next to it in the tag\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_fail_after_id_does_not_exist(self):
        self.assert_pcs_fail(
            "tag update tag1 add x1 --after no_id".split(),
            (
                "Error: There is no reference id 'no_id' in the tag 'tag1', "
                "cannot put reference ids next to it in the tag\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_fail_adding_removing_adjacent_id_duplicated(self):
        self.assert_pcs_fail(
            "tag update tag1 add x1 x1 x2 x2 --before x1 remove x1 x1 x2 x2".split(),
            (
                "Error: Ids cannot be added and removed at the same time: "
                "'x1', 'x2'\n"
                "Error: Ids to add must be unique, duplicate ids: 'x1', 'x2'\n"
                "Error: Ids to remove must be unique, duplicate ids: 'x1', 'x2'"
                "\n"
                "Error: Cannot put id 'x1' next to itself.\n"
                "Error: Cannot remove id 'x1' next to which ids are being added"
                "\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_fail_removed_ids_would_leave_tag_empty(self):
        self.assert_pcs_fail(
            "tag update tag1 remove x1 x2 x3".split(),
            (
                "Error: There would be no references left in the tag 'tag1', "
                "please remove the whole tag using the 'pcs tag remove tag1' "
                "command\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_fail_add_new_ids_and_remove_it_at_the_same_time(self):
        self.assert_pcs_fail(
            "tag update tag1 add y1 y2 remove y1 y2".split(),
            (
                "Error: Ids cannot be added and removed at the same time: 'y1',"
                " 'y2'\n"
                "Error: Tag 'tag1' does not contain ids: 'y1', 'y2'\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())

    def test_fail_remove_ids_not_in_tag(self):
        self.assert_pcs_fail(
            "tag update tag1 remove nonexistent2 nonexistent1".split(),
            (
                "Error: Tag 'tag1' does not contain ids: 'nonexistent1', "
                "'nonexistent2'\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(self.fixture_tags_xml())
