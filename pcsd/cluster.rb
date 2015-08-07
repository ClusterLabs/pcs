class Cluster
  attr_accessor :name
  attr_reader :nodes

  def initialize(name, node_list)
    @name = name
    self.nodes = node_list
  end

  def nodes=(node_list)
    @nodes = []
    node_list.each { |n|
      @nodes << n if n.is_a?(String)
    }
    @nodes = @nodes.uniq.sort
    return self
  end

  def num_nodes
    @nodes.length
  end

  def ui_address
    return "/managec/" + @name + "/main"
  end
end
