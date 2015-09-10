require 'test/unit'
require 'fileutils'
require 'json'
require 'rexml/document'

require 'pcs.rb'

class TestGetNodesAttributes < Test::Unit::TestCase
  def test_empty
    cib = '
<cib>
  <configuration>
    <nodes>
      <node uname="node1">
        <instance_attributes/>
      </node>
      <node uname="node2"/>
      <node uname="node3">
        <instance_attributes/>
      </node>
    </nodes>
  </configuration>
</cib>'
    cib_dom = REXML::Document.new(cib)
    assert_equal({}, get_node_attributes(nil, cib_dom))
  end

  def test_bad_path
    cib = '
<cib>
  <configuration>
    <nodes>
      <node uname="node1">
        <instance_attributes/>
        <nvpair name="test1" value="test2"/>
      </node>
      <node uname="node2"/>
      <node uname="node3">
        <instance_attributes/>
      </node>
    </nodes>
  </configuration>
  <nvpair name="test" value="testval"/>
</cib>
'
    cib_dom = REXML::Document.new(cib)
    assert_equal({}, get_node_attributes(nil, cib_dom))
  end

  def test_attributes
    cib = '
<cib>
  <configuration>
    <nodes>
      <node id="1" uname="node1">
        <instance_attributes id="nodes-1"/>
      </node>
      <node id="2" uname="node2">
        <instance_attributes id="nodes-2">
          <nvpair id="nodes-2-test" name="test" value="44"/>
        </instance_attributes>
      </node>
      <node id="3" uname="node3">
        <instance_attributes id="nodes-3">
          <nvpair id="nodes-3-test" name="test" value="testval2"/>
          <nvpair id="nodes-3-test2" name="test2" value="1"/>
          <nvpair id="nodes-3-test321" name="test321" value="321"/>
        </instance_attributes>
      </node>
    </nodes>
  </configuration>
</cib>
'
    cib_dom = REXML::Document.new(cib)
    expected = {}
    expected['node2'] = JSON.parse(
      '[
        {
          "id": "nodes-2-test",
          "key": "test",
          "value": "44"
        }
      ]', {:symbolize_names => true})
    expected['node3'] = JSON.parse(
      '[
        {
          "id": "nodes-3-test",
          "key": "test",
          "value": "testval2"
        },
        {
          "id": "nodes-3-test2",
          "key": "test2",
          "value": "1"
        },
        {
          "id": "nodes-3-test321",
          "key": "test321",
          "value": "321"
        }
      ]', {:symbolize_names => true})
    assert_equal(expected, get_node_attributes(nil, cib_dom))
  end
end

class TestGetFenceLevels < Test::Unit::TestCase
  def test_empty
    cib = '
<cib>
  <configuration>
    <fencing-topology/>
  </configuration>
</cib>'
    cib_dom = REXML::Document.new(cib)
    assert_equal({}, get_fence_levels(nil, cib_dom))
  end

  def test_bad_path
    cib = '
<cib>
  <configuration>
    <fencing-topology/>
    <fencing-level devices="node2-stonith" id="fl-node3-33" index="33" target="node3"/>
  </configuration>
  <fencing-level devices="node1-stonith" id="fl-node1-1" index="1" target="node1"/>
</cib>'
    cib_dom = REXML::Document.new(cib)
    assert_equal({}, get_fence_levels(nil, cib_dom))
  end

  def test_levels
    cib = '
<cib>
  <configuration>
    <fencing-topology>
      <fencing-level devices="node1-stonith" id="fl-node1-1" index="1" target="node1"/>
      <fencing-level devices="node2-stonith" id="fl-node1-2" index="2" target="node1"/>
      <fencing-level devices="node1-stonith" id="fl-node3-121" index="121" target="node3"/>
      <fencing-level devices="node3-stonith" id="fl-node3-312" index="312" target="node3"/>
      <fencing-level devices="node2-stonith" id="fl-node3-33" index="33" target="node3"/>
    </fencing-topology>
  </configuration>
</cib>'
    cib_dom = REXML::Document.new(cib)
    expected_json = '
{
  "node1": [
    {
      "level": "1",
      "devices": "node1-stonith"
    },
    {
      "level": "2",
      "devices": "node2-stonith"
    }
  ],
  "node3": [
    {
      "level": "33",
      "devices": "node2-stonith"
    },
    {
      "level": "121",
      "devices": "node1-stonith"
    },
    {
      "level": "312",
      "devices": "node3-stonith"
    }
  ]
}
'
    assert_equal(JSON.parse(expected_json), get_fence_levels(nil, cib_dom))
  end
end

class TestGetAcls < Test::Unit::TestCase
  def test_empty
    cib = '
<cib>
  <configuration>
    <acls/>
  </configuration>
</cib>'
    cib_dom = REXML::Document.new(cib)
    expected = {"group"=>{}, "role"=>{}, "target"=>{}, "user"=>{}}
    assert_equal(expected, get_acls(nil, cib_dom))
  end

  def test_bad_path
    cib = '
<cib>
  <configuration>
    <acls/>
    <acl_role id="test">
      <acl_permission id="test1" kind="read" reference="test-ref"/>
    </acl_role>
    <acl_target id="target_id">
      <role id="test"/>
    </acl_target>
  </configuration>
</cib>'
    cib_dom = REXML::Document.new(cib)
    expected = {"group"=>{}, "role"=>{}, "target"=>{}, "user"=>{}}
    assert_equal(expected, get_acls(nil, cib_dom))
  end

  def test_acls
    cib = '
<cib>
  <configuration>
    <acls>
      <acl_role description="testing" id="test">
        <acl_permission id="test-read" kind="read" xpath="/*"/>
        <acl_permission id="test-write" kind="write" reference="test-read"/>
      </acl_role>
      <acl_target id="test2">
        <role id="test"/>
      </acl_target>
      <acl_group id="testgroup">
        <role id="test"/>
      </acl_group>
    </acls>
  </configuration>
</cib>'
    cib_dom = REXML::Document.new(cib)
    expected_json = '
{
  "role": {
    "test": {
      "description": "testing",
      "permissions": [
        "read xpath /* (test-read)",
        "write id test-read (test-write)"
      ]
    }
  },
  "group": {
    "testgroup": [
      "test"
    ]
  },
  "user": {
    "test2": [
      "test"
    ]
  },
  "target": {
    "test2": [
      "test"
    ]
  }
}
    '
    assert_equal(JSON.parse(expected_json), get_acls(nil, cib_dom))
  end
end
