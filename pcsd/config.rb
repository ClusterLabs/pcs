require 'json'
require 'pp'

require 'cfgsync.rb'

class PCSConfig
  attr_accessor :clusters

  def initialize
    @clusters = []
    begin
      json = Cfgsync::PcsdSettings.from_file().text()
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

  def update_without_saving(cluster_name, node_list)
    if node_list.length == 0
      @clusters.delete_if{|c|c.name == cluster_name}
      $logger.info("Removing cluster: #{cluster_name}")
    else
    @clusters.each {|c|
      if c.name == cluster_name
        c.nodes = node_list
        break
      end
    }
    end
  end

  def update(cluster_name, node_list)
    update_without_saving(cluster_name, node_list)
    self.save
  end

  def save
    out_cluster_array = []
    @clusters.each { |c|
      temphash = {}
      temphash["name"] = c.name
      temphash["nodes"] = c.nodes
      out_cluster_array << temphash
    }

    cfg = Cfgsync::PcsdSettings.from_text(
      JSON.pretty_generate(out_cluster_array)
    )
    cfg.save()
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
