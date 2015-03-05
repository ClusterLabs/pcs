require 'json'
require 'pp'

class PCSConfig
  attr_accessor :clusters

  def initialize
    @clusters = []
    begin
      json = File.read(SETTINGS_FILE)
      input_clusters = JSON.parse(json)
    rescue
      input_clusters = []
    end
    input_clusters.each {|c|
      @clusters << Cluster.new(c["name"], c["nodes"])
    }
  end

  def self.refresh_cluster_nodes(cluster_name, node_list)
    node_list.uniq!
    if node_list.length > 0
      config = self.new
      old_node_list = config.get_nodes(cluster_name)
      if old_node_list & node_list != old_node_list or old_node_list.size!=node_list.size
        $logger.info("Updating node list for: " + cluster_name + " " + old_node_list.inspect + "->" + node_list.inspect)
        config.update(cluster_name, node_list)
        return true
      end
    end
    return false
  end

  def update(cluster_name, node_list)
    if node_list.length == 0
      @clusters.delete_if{|c|c.name == cluster_name}
      $logger.info("Removing cluster: #{cluster_name}")
      self.save
      return
    end
    @clusters.each {|c|
      if c.name == cluster_name
        c.nodes = node_list
        self.save
        break
      end
    }
  end

  def save
    out_cluster_array = []
    @clusters.each { |c|
      temphash = {}
      temphash["name"] = c.name
      temphash["nodes"] = c.nodes
      out_cluster_array << temphash
    }

    File.open(SETTINGS_FILE, "w") do |f|
	f.write(JSON.pretty_generate(out_cluster_array))
    end
  end

  def remove_cluster(cluster_name)
    @clusters.delete_if { |c| c.name == cluster_name }
  end

  def is_cluster_name_in_use(cname)
    @clusters.each {|c|
      if c.name == cname
      	return true
      end
    }
    return false
  end

  def is_node_in_use(nodename)
    @clusters.each {|c|
      c.nodes.each {|n|
      	return true if n == nodename
      }
    }
    return false
  end

  def get_nodes(clustername)
    @clusters.each {|c|
      if c.name == clustername
        return c.nodes
      end
    }
    return nil
  end
end
