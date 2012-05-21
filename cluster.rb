class Cluster 
  attr_accessor :id, :name, :nodes, :num_nodes
  def initialize(name, nodes,num_nodes)
    @name = name
    @nodes = nodes
    @num_nodes = num_nodes
  end

  def ui_address
    return "http://" + nodes[0] + ":2222/"
  end
end
