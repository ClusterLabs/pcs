from textwrap import dedent
from unittest import TestCase

from pcs.common import reports
from pcs.lib.commands import cluster as lib

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

FIXTURE_ACLS = '<acls><acl_role id="role1"/></acls>'


def _constraints(*argv):
    return f"<constraints>{''.join(argv)}</constraints>"


def _corosync_conf_node(nodeid, name):
    return f"""
        node {{
            ring0_addr: {name}
            nodeid: {nodeid}
            name: {name}
        }}
    """


def _corosync_conf(*node_names):
    nodes = "\n".join(
        _corosync_conf_node(i, name) for i, name in enumerate(node_names, 1)
    )
    return f"""
        totem {{
            version: 2
            cluster_name: test
            transport: udpu
        }}

        nodelist {{
          {nodes}
        }}

        quorum {{
            provider: corosync_votequorum
        }}
    """


def _location(location_id, node_name):
    return f"""
        <rsc_location
          id="{location_id}"
          rsc="R"
          node="{node_name}"
          score="100"
        />
    """


def _location_rule(rule_id, node_name, attr="#uname"):
    lid = (
        rule_id[: len("-rule")] if rule_id.endswith("-rule") else f"l-{rule_id}"
    )

    return f"""
        <rsc_location id="{lid}" rsc="R">
          <rule id="{rule_id}" boolean-op="and" score="INFINITY">
            <expression
              id="{lid}-expr"
              attribute="{attr}"
              operation="eq"
              value="{node_name}"
            />
          </rule>
        </rsc_location>
    """


def _fencing_topology(*argv):
    return f"<fencing-topology>{''.join(argv)}</fencing-topology>"


def _fencing_level_node(level_id, node_name):
    return f"""
        <fencing-level
          id="{level_id}"
          index="1"
          target="{node_name}"
          devices="dev1"
        />
    """


def _fencing_level_attr(level_id, attr_name, attr_value):
    return f"""
        <fencing-level
          id="{level_id}"
          index="1"
          target-attribute="{attr_name}"
          target-value="{attr_value}"
          devices="dev1"
        />
    """


def _fencing_level_pattern(level_id, pattern):
    return f"""
        <fencing-level
          id="{level_id}"
          index="1"
          target-pattern="{pattern}"
          devices="dev1"
        />
    """


def _resources(*argv):
    return f"<resources>{''.join(argv)}</resources>"


def _stonith(device_id, host_list=None, host_map=None):
    nvpairs = []
    if host_list is not None:
        nvpairs.append(f"""
            <nvpair
              id="{device_id}-ia-hl"
              name="pcmk_host_list"
              value="{host_list}"
            />
        """)
    elif host_map is not None:
        nvpairs.append(f"""
            <nvpair
              id="{device_id}-ia-hm"
              name="pcmk_host_map"
              value="{host_map}"
            />
        """)
    if not nvpairs:
        return f'<primitive id="{device_id}" class="stonith" type="fence_xvm"/>'
    nvpairs_xml = "\n      ".join(nvpairs)
    return f"""
        <primitive id="{device_id}" class="stonith" type="fence_xvm">
          <instance_attributes id="{device_id}-ia">
            {nvpairs_xml}
          </instance_attributes>
        </primitive>
    """


class RenameNode(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.old_name = "old_name"
        self.new_name = "new_name"
        self.rule_id = "l1-rule"
        self.location_id = "loc1"
        self.config.env.set_corosync_conf_data(
            _corosync_conf(self.new_name, "other_node")
        )
        self.irrelevant_location = _location("loc2", "other-node")
        self.irrelevant_rule1 = _location_rule(
            "l2-rule", self.old_name, attr="#kind"
        )
        self.irrelevant_rule2 = _location_rule("l3-rule", "other-node")
        self.irrelevant_fl_node = _fencing_level_node("fl1", "other-node")
        self.irrelevant_fl_attr = _fencing_level_attr(
            "fl2", "#uname", "other-node"
        )
        self.irrelevant_stonith = _stonith(
            "fence-other", host_list=f"{self.old_name}-suffix,other_host"
        )
        self.irrelevant_stonith_map = _stonith(
            "fence-port", host_map=f"{self.old_name}-suffix:{self.old_name}"
        )

    def test_no_match_no_change(self):
        self.config.runner.cib.load(
            constraints=_constraints(
                self.irrelevant_location,
                self.irrelevant_rule1,
                self.irrelevant_rule2,
            ),
            fencing_topology=_fencing_topology(
                self.irrelevant_fl_node,
                self.irrelevant_fl_attr,
            ),
            resources=_resources(
                self.irrelevant_stonith,
                self.irrelevant_stonith_map,
            ),
        )
        lib.rename_node_cib(
            self.env_assist.get_env(), "nonexistent", self.new_name
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.CIB_NODE_RENAME_NO_CHANGE,
                ),
            ]
        )

    def test_only_relevant_parts_updated(self):
        irrelevant_fl_attr2 = _fencing_level_attr(
            "fl5", "other-attr", self.old_name
        )
        warning_producing_fl_pattern = _fencing_level_pattern("fl2", "old_.*")
        self.config.runner.cib.load(
            constraints=_constraints(
                _location(self.location_id, self.old_name),
                self.irrelevant_location,
                _location_rule(self.rule_id, self.old_name),
                self.irrelevant_rule1,
                self.irrelevant_rule2,
            ),
            fencing_topology=_fencing_topology(
                _fencing_level_node("fl1", self.old_name),
                _fencing_level_attr("fl2", "#uname", self.old_name),
                self.irrelevant_fl_node,
                self.irrelevant_fl_attr,
                irrelevant_fl_attr2,
                warning_producing_fl_pattern,
            ),
            resources=_resources(
                _stonith("F1", host_list=f"{self.old_name},other_host"),
                _stonith("F2", host_list=f"other_host,{self.old_name}"),
                _stonith("F3", host_map=f"{self.old_name}:1;other_host:2"),
                _stonith("F4", host_map=f"other_host:1;{self.old_name}:2"),
                self.irrelevant_stonith,
                self.irrelevant_stonith_map,
            ),
            acls=FIXTURE_ACLS,
        )
        self.config.env.push_cib(
            constraints=_constraints(
                _location(self.location_id, self.new_name),
                self.irrelevant_location,
                _location_rule(self.rule_id, self.new_name),
                self.irrelevant_rule1,
                self.irrelevant_rule2,
            ),
            fencing_topology=_fencing_topology(
                _fencing_level_node("fl1", self.new_name),
                _fencing_level_attr("fl2", "#uname", self.new_name),
                self.irrelevant_fl_node,
                self.irrelevant_fl_attr,
                irrelevant_fl_attr2,
                warning_producing_fl_pattern,
            ),
            resources=_resources(
                _stonith("F1", host_list=f"{self.new_name},other_host"),
                _stonith("F2", host_list=f"other_host,{self.new_name}"),
                _stonith("F3", host_map=f"{self.new_name}:1;other_host:2"),
                _stonith("F4", host_map=f"other_host:1;{self.new_name}:2"),
                self.irrelevant_stonith,
                self.irrelevant_stonith_map,
            ),
            acls=FIXTURE_ACLS,
        )
        lib.rename_node_cib(
            self.env_assist.get_env(), self.old_name, self.new_name
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.CIB_NODE_RENAME_ELEMENT_UPDATED,
                    element_type="Location constraint",
                    element_id=self.location_id,
                    attribute_desc="node",
                    old_value=self.old_name,
                    new_value=self.new_name,
                ),
                fixture.info(
                    reports.codes.CIB_NODE_RENAME_ELEMENT_UPDATED,
                    element_type="Rule",
                    element_id=self.rule_id,
                    attribute_desc="#uname expression",
                    old_value=self.old_name,
                    new_value=self.new_name,
                ),
                fixture.info(
                    reports.codes.CIB_NODE_RENAME_ELEMENT_UPDATED,
                    element_type="Fencing level",
                    element_id="fl1",
                    attribute_desc="target",
                    old_value=self.old_name,
                    new_value=self.new_name,
                ),
                fixture.info(
                    reports.codes.CIB_NODE_RENAME_ELEMENT_UPDATED,
                    element_type="Fencing level",
                    element_id="fl2",
                    attribute_desc="target",
                    old_value=self.old_name,
                    new_value=self.new_name,
                ),
                fixture.warn(
                    reports.codes.CIB_NODE_RENAME_FENCING_LEVEL_PATTERN_EXISTS,
                    level_id="fl2",
                    pattern="old_.*",
                ),
                fixture.info(
                    reports.codes.CIB_NODE_RENAME_ELEMENT_UPDATED,
                    element_type="Fence device",
                    element_id="F1",
                    attribute_desc="attribute 'pcmk_host_list'",
                    old_value=f"{self.old_name},other_host",
                    new_value=f"{self.new_name},other_host",
                ),
                fixture.info(
                    reports.codes.CIB_NODE_RENAME_ELEMENT_UPDATED,
                    element_type="Fence device",
                    element_id="F2",
                    attribute_desc="attribute 'pcmk_host_list'",
                    old_value=f"other_host,{self.old_name}",
                    new_value=f"other_host,{self.new_name}",
                ),
                fixture.info(
                    reports.codes.CIB_NODE_RENAME_ELEMENT_UPDATED,
                    element_type="Fence device",
                    element_id="F3",
                    attribute_desc="attribute 'pcmk_host_map'",
                    old_value=f"{self.old_name}:1;other_host:2",
                    new_value=f"{self.new_name}:1;other_host:2",
                ),
                fixture.info(
                    reports.codes.CIB_NODE_RENAME_ELEMENT_UPDATED,
                    element_type="Fence device",
                    element_id="F4",
                    attribute_desc="attribute 'pcmk_host_map'",
                    old_value=f"other_host:1;{self.old_name}:2",
                    new_value=f"other_host:1;{self.new_name}:2",
                ),
                fixture.warn(reports.codes.CIB_NODE_RENAME_ACLS_EXIST),
            ]
        )


class RenameNodeCorosyncCheckCornerCases(TestCase):
    def setUp(self):
        self.old_name = "old_name"
        self.new_name = "new_name"
        self.location_id = "loc1"
        self.env_assist, self.config = get_env_tools(self)

    def test_corosync_checks_fail(self):
        self.config.env.set_corosync_conf_data(
            _corosync_conf(self.old_name, "other_node")
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.rename_node_cib(
                self.env_assist.get_env(), self.old_name, self.new_name
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.CIB_NODE_RENAME_NEW_NODE_NOT_IN_COROSYNC,
                    force_code=reports.codes.FORCE,
                    new_name="new_name",
                ),
                fixture.error(
                    reports.codes.CIB_NODE_RENAME_OLD_NODE_IN_COROSYNC,
                    force_code=reports.codes.FORCE,
                    old_name="old_name",
                ),
            ]
        )

    def test_corosync_checks_fail_forced(self):
        self.config.env.set_corosync_conf_data(
            _corosync_conf(self.old_name, "other_node")
        )
        self.config.runner.cib.load(
            constraints=_constraints(
                _location(self.location_id, self.old_name)
            ),
        )
        self.config.env.push_cib(
            constraints=_constraints(
                _location(self.location_id, self.new_name)
            ),
        )
        lib.rename_node_cib(
            self.env_assist.get_env(),
            self.old_name,
            self.new_name,
            force_flags=[reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.CIB_NODE_RENAME_NEW_NODE_NOT_IN_COROSYNC,
                    new_name="new_name",
                ),
                fixture.warn(
                    reports.codes.CIB_NODE_RENAME_OLD_NODE_IN_COROSYNC,
                    old_name="old_name",
                ),
                fixture.info(
                    reports.codes.CIB_NODE_RENAME_ELEMENT_UPDATED,
                    element_type="Location constraint",
                    element_id=self.location_id,
                    attribute_desc="node",
                    old_value=self.old_name,
                    new_value=self.new_name,
                ),
            ]
        )

    def test_live_cib_non_live_corosync_not_consistent(self):
        self.config.env.set_corosync_conf_data(
            _corosync_conf(self.new_name, "other_node")
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.rename_node_cib(
                self.env_assist.get_env(), self.old_name, self.new_name
            ),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_NOT_CONSISTENT,
                    mocked_files=[file_type_codes.COROSYNC_CONF],
                    required_files=[file_type_codes.CIB],
                ),
            ],
            expected_in_processor=False,
        )

    def test_cib_from_file_skips_corosync_check(self):
        cib_xml = dedent(
            f"""\
            <cib>
              <configuration>
                <constraints>
                  {_location(self.location_id, self.old_name)}
                  </constraints>
            </configuration>
            </cib>
            """
        )
        self.config.env.set_cib_data(cib_xml)
        self.config.runner.cib.load_content(
            cib_xml,
            env={"CIB_file": "/fake/tmp/file"},
        )
        self.config.env.push_cib(
            constraints=_constraints(
                _location(self.location_id, self.new_name)
            ),
            load_key="runner.cib.load_content",
        )
        lib.rename_node_cib(self.env_assist.get_env(), "old_name", "new_name")
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.CIB_NODE_RENAME_ELEMENT_UPDATED,
                    element_type="Location constraint",
                    element_id=self.location_id,
                    attribute_desc="node",
                    old_value=self.old_name,
                    new_value=self.new_name,
                ),
            ]
        )
