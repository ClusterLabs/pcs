class Cluster 
  attr_accessor :id, :name, :nodes, :num_nodes
  def initialize(name, nodes)
    @name = name
    @nodes = nodes
    @num_nodes = nodes.length
  end

  def ui_address
    return "http://" + nodes[0] + ":2222/nodes"
  end
end
