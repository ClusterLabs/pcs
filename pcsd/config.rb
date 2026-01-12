require 'json'

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
    default_permissions = [
      {
        'type' => Permissions::TYPE_GROUP,
        'name' => ADMIN_GROUP,
        'allow' => [
          Permissions::READ,
          Permissions::WRITE,
          Permissions::GRANT,
        ]
      },
    ]

    # set a reasonable default if file doesn't exist
    # set default permissions for backwards compatibility (there is no way to
    # differentiante between an old cluster without config and a new cluster
    # without config)
    # Since ADMIN_GROUP has access to pacemaker by default anyway, we can safely
    # allow access in pcsd as well even for new clusters.
    if cfg_text.nil?
      @format_version = CURRENT_FORMAT
      perm_list = []
      default_permissions.each { |perm|
        perm_list << Permissions::EntityPermissions.new(
          perm['type'], perm['name'], perm['allow']
        )
      }
      @permissions_local = Permissions::PermissionsSet.new(perm_list)
      return
    end

    # set a reasonable default if got empty text (i.e. file exists but is empty)
    if cfg_text.strip.empty?
      @format_version = CURRENT_FORMAT
      return
    end

    # main parsing
    begin
      json = JSON.parse(cfg_text)
      if json.is_a?(Array)
        @format_version = 1
      elsif (
        json.is_a?(Hash) and
        json.key?('format_version') and
        json['format_version'].is_a?(Integer)
      )
        @format_version = json["format_version"]
      else
        raise 'invalid file format'
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
        # Old pcsd without permission support was using format_version == 1.
        # All members of 'haclient' group had unrestricted access.
        # We give them access to most functions except reading tokens and keys,
        # they also won't be able to add and remove nodes because of that.
        input_permissions = {'local_cluster' => default_permissions}
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
        c.nodes = node_list
        break
      end
    }
  end

  def text()
    out_hash = Hash.new
    out_hash['clusters'] = []
    out_hash['data_version'] = @data_version
    out_hash['format_version'] = CURRENT_FORMAT
    out_hash['permissions'] = Hash.new
    out_hash['permissions']['local_cluster'] = []

    @clusters.each { |c|
      c_hash = Hash.new
      c_hash['name'] = c.name
      c_hash['nodes'] = c.nodes.uniq.sort
      out_hash['clusters'] << c_hash
    }

    out_hash['permissions']['local_cluster'] = @permissions_local.to_hash()

    return JSON.pretty_generate(out_hash, {indent: '    '})
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

  def get_nodes_cluster(nodename)
    @clusters.each {|c|
      c.nodes.each {|n|
        return c.name if n == nodename
      }
    }
    return nil
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


class CfgKnownHosts
  CURRENT_FORMAT = 1
  attr_reader :format_version, :known_hosts
  attr_accessor :data_version

  def initialize(cfg_text)
    @format_version = CURRENT_FORMAT
    @data_version = 0
    @known_hosts = {}

    # set a reasonable parseable default if got empty text
    if cfg_text.nil? or cfg_text.strip.empty?
      # all has been set above, nothing more to do
      return
    end

    begin
      json = JSON.parse(cfg_text)

      @format_version = json.fetch('format_version')
      @data_version = json.fetch('data_version')

      if @format_version > CURRENT_FORMAT
        $logger.warn(
          "known-hosts file format version is #{@format_version}" +
          ", newest fully supported version is #{CURRENT_FORMAT}"
        )
      end

      if @format_version == 1
        json.fetch('known_hosts').each { |name, data|
          dest_list = []
          data.fetch('dest_list').each { |dest|
            dest_list << {
              'addr' => dest.fetch('addr'),
              'port' => dest.fetch('port'),
            }
          }
          @known_hosts[name] = PcsKnownHost.new(
            name,
            data.fetch('token'),
            dest_list
          )
        }
      else
        $logger.error(
          'Unable to parse known-hosts file, ' +
          "unknown format_version '#{@format_version}'"
        )
      end

    rescue => e
      $logger.error("Unable to parse known-hosts file: #{e}")
    end
  end

  def text()
    out_hosts = {}
    @known_hosts.keys.sort.each { |host_name|
      host = @known_hosts[host_name]
      out_hosts[host_name] = {
        'dest_list' => host.dest_list,
        'token' => host.token,
      }
    }
    out_hash = {
      'data_version' => @data_version,
      'format_version' => CURRENT_FORMAT,
      'known_hosts' => out_hosts,
    }
    return JSON.pretty_generate(out_hash, {indent: '    '})
  end
end

class PcsKnownHost
  attr_reader :name, :token

  def initialize(name, token, dest_list)
    @name = name
    @token = token
    @dest_list = []
    dest_list.each { |dest|
      @dest_list << {
        'addr' => dest.fetch('addr'),
        'port' => dest.fetch('port'),
      }
    }
  end

  def dest_list()
    output_list = []
    @dest_list.each { |dest|
      output_list << dest.clone()
    }
    return output_list
  end

  def first_dest()
    if @dest_list.length > 0
      return @dest_list[0].clone()
    else
      return {}
    end
  end
end
