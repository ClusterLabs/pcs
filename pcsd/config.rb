require 'json'
require 'pp'

require 'cluster.rb'

class PCSConfig
  CURRENT_FORMAT = 2
  attr_accessor :clusters, :format_version, :data_version

  def initialize(cfg_text)
    @format_version = 0
    @data_version = 0
    @clusters = []

    input_clusters = []
    begin
      json = JSON.parse(cfg_text)
      if not(json.is_a?(Hash) and json.key?("format_version"))
        @format_version = 1
      else
        @format_version = json["format_version"]
      end

      if @format_version > CURRENT_FORMAT
        $logger.warn(
          "Config file format version is #{@format_version}" +
          ", newest fully supported version is #{CURRENT_FORMAT}"
        )
      end

      if @format_version >= 2
        @data_version = json["data_version"] || 0
        input_clusters = json["clusters"] || []
      elsif @format_version == 1
        input_clusters = json
      else
        $logger.error("Unable to parse config file")
      end
    rescue => e
      $logger.error("Unable to parse config file: #{e}")
    end
    input_clusters.each {|c|
      @clusters << Cluster.new(c["name"], c["nodes"])
    }
  end

  def update(cluster_name, node_list)
    if node_list.length == 0
      @clusters.delete_if{|c|c.name == cluster_name}
      $logger.info("Removing cluster: #{cluster_name}")
      return
    end
    @clusters.each {|c|
      if c.name == cluster_name
        c.nodes = node_list
        break
      end
    }
  end

  def text()
    out_hash = {
      "format_version" => CURRENT_FORMAT,
      "data_version" => @data_version,
      "clusters" => [],
    }

    cluster_list = []
    @clusters.each { |c|
      out_hash["clusters"] << {
        "name" => c.name,
        "nodes" => c.nodes,
      }
      cluster_list << c.name
    }

    return JSON.pretty_generate(out_hash)
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
