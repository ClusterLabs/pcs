require 'json'
require 'pp'
require 'orderedhash'

require 'cluster.rb'
require 'permissions.rb'

class PCSConfig
  CURRENT_FORMAT = 2
  attr_accessor :clusters, :permissions_local, :format_version, :data_version

  def initialize(cfg_text)
    @format_version = 0
    @data_version = 0
    @clusters = []
    @permissions_local = Permissions::PermissionsSet.new([])

    input_clusters = []
    input_permissions = {}

    begin
      json = JSON.parse(cfg_text)
      if not(json.is_a?(Hash) and json.key?("format_version"))
        @format_version = 1
      else
        @format_version = json["format_version"]
      end

      if @format_version > CURRENT_FORMAT
        $logger.warn(
          "pcs_settings file format version is #{@format_version}" +
          ", newest fully supported version is #{CURRENT_FORMAT}"
        )
      end

      if @format_version >= 2
        @data_version = json["data_version"] || 0
        input_clusters = json["clusters"] || []
        input_permissions = json['permissions'] || {}
      elsif @format_version == 1
        input_clusters = json
        # backward compatibility code start
        # pcsd without permission support used format_version == 1
        # all users, who were member of 'haclient' group, had full access
        input_permissions = {
          'local_cluster' => [
            {
              'type' => Permissions::TYPE_GROUP,
              'name' => ADMIN_GROUP,
              'allow' => [Permissions::FULL],
            },
          ],
        }
        # backward compatibility code end
      else
        $logger.error("Unable to parse pcs_settings file")
      end
    rescue => e
      $logger.error("Unable to parse pcs_settings file: #{e}")
    end

    input_clusters.each {|c|
      @clusters << Cluster.new(c["name"], c["nodes"])
    }

    if input_permissions.key?('local_cluster')
      perm_list = []
      input_permissions['local_cluster'].each { |perm|
        perm_list << Permissions::EntityPermissions.new(
          perm['type'], perm['name'], perm['allow']
        )
      }
      @permissions_local = Permissions::PermissionsSet.new(perm_list)
    end
  end

  def update_cluster(cluster_name, node_list)
    if node_list.length == 0
      @clusters.delete_if{|c|c.name == cluster_name}
      $logger.info("Removing cluster from pcs_settings: #{cluster_name}")
      return
    end
    @clusters.each {|c|
      if c.name == cluster_name
        c.nodes = node_list.uniq.sort
        break
      end
    }
  end

  def text()
    out_hash = OrderedHash.new
    out_hash['format_version'] = CURRENT_FORMAT
    out_hash['data_version'] = @data_version
    out_hash['clusters'] = []
    out_hash['permissions'] = OrderedHash.new
    out_hash['permissions']['local_cluster'] = []

    @clusters.each { |c|
      c_hash = OrderedHash.new
      c_hash['name'] = c.name
      c_hash['nodes'] = c.nodes.uniq.sort
      out_hash['clusters'] << c_hash
    }

    perm_set = []
    @permissions_local.entity_permissions_list.each { |perm|
      perm_hash = OrderedHash.new
      perm_hash['type'] = perm.type
      perm_hash['name'] = perm.name
      perm_hash['allow'] = perm.allow_list.uniq.sort
      perm_set << perm_hash
    }
    out_hash['permissions']['local_cluster'] = perm_set.sort { |a, b|
      a['type'] == b['type'] ? a['name'] <=> b['name'] : a['type'] <=> b['type']
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

  def cluster_nodes_equal?(cluster_name, nodes)
    my_nodes = get_nodes(cluster_name) || []
    nodes = nodes || []
    return my_nodes.sort.uniq == nodes.sort.uniq
  end
end


class PCSTokens
  CURRENT_FORMAT = 2
  attr_accessor :tokens, :format_version, :data_version

  def initialize(cfg_text)
    @format_version = 0
    @data_version = 0
    @tokens = {}

    begin
      json = JSON.parse(cfg_text)
      if not(json.is_a?(Hash) and json.key?('format_version') and json.key?('tokens'))
        @format_version = 1
      else
        @format_version = json['format_version']
      end

      if @format_version > CURRENT_FORMAT
        $logger.warn(
          "tokens file format version is #{@format_version}" +
          ", newest fully supported version is #{CURRENT_FORMAT}"
        )
      end

      if @format_version >= 2
        @data_version = json['data_version'] || 0
        @tokens = json['tokens'] || {}
      elsif @format_version == 1
        @tokens = json
      else
        $logger.error('Unable to parse tokens file')
      end
    rescue => e
      $logger.error("Unable to parse tokens file: #{e}")
    end
  end

  def text()
    tokens_hash = OrderedHash.new
    @tokens.keys.sort.each { |key| tokens_hash[key] = @tokens[key] }

    out_hash = OrderedHash.new
    out_hash['format_version'] = CURRENT_FORMAT
    out_hash['data_version'] = @data_version
    out_hash['tokens'] = tokens_hash

    return JSON.pretty_generate(out_hash)
  end
end
