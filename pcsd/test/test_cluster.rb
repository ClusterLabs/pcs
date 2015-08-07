require 'test/unit'

require 'pcsd_test_utils.rb'
require 'cluster.rb'

class TestCluster < Test::Unit::TestCase

  def test_empty
    cluster = Cluster.new('test', [])
    assert_equal('test', cluster.name)
    assert_equal([], cluster.nodes)
    assert_equal(0, cluster.num_nodes)
  end

  def test_nodes
    cluster = Cluster.new('test', ['a', 'b'])
    assert_equal('test', cluster.name)
    assert_equal(['a', 'b'], cluster.nodes)
    assert_equal(2, cluster.num_nodes)

    cluster.nodes = ['x', 'y', 'z']
    assert_equal('test', cluster.name)
    assert_equal(['x', 'y', 'z'], cluster.nodes)
    assert_equal(3, cluster.num_nodes)
  end

  def test_nodes_cleanup
    cluster = Cluster.new('test', ['b', 'a'])
    assert_equal('test', cluster.name)
    assert_equal(['a', 'b'], cluster.nodes)
    assert_equal(2, cluster.num_nodes)

    cluster.nodes = ['z', 'x', 'y', 'z', 'x']
    assert_equal('test', cluster.name)
    assert_equal(['x', 'y', 'z'], cluster.nodes)
    assert_equal(3, cluster.num_nodes)
  end

  def test_nodes_bad
    cluster = Cluster.new('test', ['a', ['b', 'c'], 'd'])
    assert_equal('test', cluster.name)
    assert_equal(['a', 'd'], cluster.nodes)
    assert_equal(2, cluster.num_nodes)

    cluster.nodes = ['w', ['x'], 'y', [], 'z']
    assert_equal('test', cluster.name)
    assert_equal(['w', 'y', 'z'], cluster.nodes)
    assert_equal(3, cluster.num_nodes)
  end

end
