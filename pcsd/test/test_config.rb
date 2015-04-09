require 'test/unit'

require 'pcsd_test_utils.rb'
require 'config.rb'

class TestConfig < Test::Unit::TestCase
  def setup
    $logger = MockLogger.new
  end

  def test_parse_empty()
    text = ''
    cfg = PCSConfig.new(text)
    assert_equal(0, cfg.clusters.length)
    assert_equal(
      [[
        "error",
        "Unable to parse config file: A JSON text must at least contain two octets!"
      ]],
      $logger.log
    )
    assert_equal(
'{
  "format_version": 2,
  "data_version": 0,
  "clusters": [

  ]
}',
      cfg.text
    )
  end

  def test_parse_format1()
    text = '[]'
    cfg = PCSConfig.new(text)
    assert_equal(0, cfg.clusters.length)

    text = '
[
  {
    "name": "cluster71",
    "nodes": [
      "rh71-node1",
      "rh71-node2"
    ]
  }
]
'
    cfg = PCSConfig.new(text)
    assert_equal(1, cfg.clusters.length)
    assert_equal("cluster71", cfg.clusters[0].name)
    assert_equal(["rh71-node1", "rh71-node2"], cfg.clusters[0].nodes)
    assert_equal(
'{
  "format_version": 2,
  "data_version": 0,
  "clusters": [
    {
      "name": "cluster71",
      "nodes": [
        "rh71-node1",
        "rh71-node2"
      ]
    }
  ]
}',
      cfg.text
    )
  end

  def test_parse_format2()
  text = '
{
  "format_version": 2
}
'
    cfg = PCSConfig.new(text)
    assert_equal(2, cfg.format_version)
    assert_equal(0, cfg.data_version)
    assert_equal(0, cfg.clusters.length)
    assert_equal(
'{
  "format_version": 2,
  "data_version": 0,
  "clusters": [

  ]
}',
      cfg.text
    )

  text = 
'{
  "format_version": 2,
  "data_version": 9,
  "clusters": [
    {
      "name": "cluster71",
      "nodes": [
        "rh71-node1",
        "rh71-node2"
      ]
    }
  ]
}'
    cfg = PCSConfig.new(text)
    assert_equal(2, cfg.format_version)
    assert_equal(9, cfg.data_version)
    assert_equal(1, cfg.clusters.length)
    assert_equal("cluster71", cfg.clusters[0].name)
    assert_equal(["rh71-node1", "rh71-node2"], cfg.clusters[0].nodes)
    assert_equal(text, cfg.text)
  end

  def test_in_use()
    cfg = PCSConfig.new(File.open(CFG_PCSD_SETTINGS).read)

    assert(cfg.is_cluster_name_in_use('cluster71'))
    assert(cfg.is_cluster_name_in_use('cluster67'))
    assert(! cfg.is_cluster_name_in_use('nonexistent'))

    assert(cfg.is_node_in_use('rh71-node1'))
    assert(cfg.is_node_in_use('rh67-node3'))
    assert(! cfg.is_node_in_use('rh71-node3'))

    assert_equal(
      ["rh71-node1", "rh71-node2"],
      cfg.get_nodes('cluster71')
    )
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )
    assert_equal(
      nil,
      cfg.get_nodes('nonexistent')
    )
  end

  def test_update()
    cfg = PCSConfig.new(File.open(CFG_PCSD_SETTINGS).read)
    assert_equal(
      ["rh71-node1", "rh71-node2"],
      cfg.get_nodes('cluster71')
    )
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )

    cfg.update('cluster71', ["rh71-node1", "rh71-node2", "rh71-node3"])
    assert_equal(
      ["rh71-node1", "rh71-node2", "rh71-node3"],
      cfg.get_nodes('cluster71')
    )
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )

    cfg.update('cluster71', ["rh71-node1", "rh71-node2"])
    assert_equal(
      ["rh71-node1", "rh71-node2"],
      cfg.get_nodes('cluster71')
    )
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )

    cfg.update('cluster71', [])
    assert(! cfg.is_cluster_name_in_use('cluster71'))
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )
  end

  def test_remove()
    cfg = PCSConfig.new(File.open(CFG_PCSD_SETTINGS).read)
    assert_equal(
      ["rh71-node1", "rh71-node2"],
      cfg.get_nodes('cluster71')
    )
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )

    cfg.remove_cluster('nonexistent')
    assert_equal(
      ["rh71-node1", "rh71-node2"],
      cfg.get_nodes('cluster71')
    )
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )

    cfg.remove_cluster('cluster71')
    assert(! cfg.is_cluster_name_in_use('cluster71'))
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )
  end
end
