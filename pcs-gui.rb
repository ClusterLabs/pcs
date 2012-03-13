require 'sinatra'
require 'sinatra/reloader' if development?
require 'open3'
require 'rexml/document'

use Rack::CommonLogger

OCF_ROOT = "/usr/lib/ocf"
HEARTBEAT_AGENTS_DIR = "/usr/lib/ocf/resource.d/heartbeat/"
PENGINE = "/usr/lib64/heartbeat/pengine"
PCS = "/root/pcs/pcs/pcs" 
CRM_ATTRIBUTE = "/usr/sbin/crm_attribute"

#set :port, 2222
set :logging, true


@nodes = (1..7)

helpers do
  def setup
    @nodes_online, @nodes_offline = getNodes
    @nodes = {}
    @nodes_online.each do |i|
      @nodes[i]  = Node.new(i, i, i, true)
    end
    @nodes_offline.each do |i|
      @nodes[i]  = Node.new(i, i, i, false)
    end

    if params[:node]
      @cur_node = @nodes[params[:node]]
    else
      @cur_node = @nodes.values[0]
    end
  end
end

get '/blah' do
  print "blah"
  erb "Blah!"
end

get '/configure/?:page?' do
  @config_options = getConfigOptions(params[:page])
  erb :configure, :layout => :main
end

get '/resourcedeps/?:resource?' do
  @resourcedepsmenuclass = "class=\"active\""
  setup()
  erb :resourcedeps, :layout => :main
end

get '/resources/?:resource?' do
  @resources = getResources
  @resourcemenuclass = "class=\"active\""

  @cur_resource = @resources[0]
  @cur_resource.options = getResourceOptions(@cur_resource.id)
  if params[:resource]
    @resources.each do |r|
      if r.id == params[:resource]
	@cur_resource = r
	@cur_resource.options = getResourceOptions(r.id)
	break
      end
    end
  end

  @resource_agents = getResourceAgents(@cur_resource.agentname)
  puts "OUTPUT"
  puts @cur_resource.id
  puts @cur_resource.name
  erb :resource, :layout => :main
end

get '/nodes/?:node?' do
  print "Nodes\n"
  setup()
  @nodemenuclass = "class=\"active\""
  erb :nodes, :layout => :main
end

get '/' do
  print "Redirecting...\n"
  call(env.merge("PATH_INFO" => '/nodes'))
end


get '*' do
  print params[:splat]
  print "2Redirecting...\n"
  call(env.merge("PATH_INFO" => '/nodes'))
end

def getNodes
  stdin, stdout, stderror = Open3.popen3("#{PCS} status nodes")
  out = stdout.readlines
  [out[1].split(' ')[1..-1], out[2].split(' ')[1..-1]]
end

def getResources
  stdin, stdout, stderror = Open3.popen3('/root/pacemaker/tools/crm_mon --as-xml=/tmp/testclusterstatus')

  doc = REXML::Document.new(File.open("/tmp/testclusterstatus", "rb"))
  resource_list = []
  doc.elements.each('crm_mon/resources/resource') do |e|
    resource_list.push(Resource.new(e))
  end
  resource_list
end

def getResourceOptions(resource_id)
  ret = {}
  resource_options = `#{PCS} resource show #{resource_id}`
  resource_options.each_line { |line|
    keyval = line.strip.split(/: /,2)
    ret[keyval[0]] = keyval[1]
  }
  return ret
end

def getResourceAgents(resource_agent)
  resource_agent_list = {}
  if resource_agent == nil
    return resource_agent_list
  end
  agents = Dir.glob(HEARTBEAT_AGENTS_DIR + '*')
  agents.each { |a|
    ra = ResourceAgent.new
    ra.name = "ocf::heartbeat:" + a.sub(/.*\//,"")

    print a + "-" + resource_agent + "\n"
    if a.sub(/.*\//,"") == resource_agent.sub(/.*:/,"")
      ENV['OCF_ROOT'] = OCF_ROOT
      metadata = `#{a} meta-data`

      doc = REXML::Document.new(metadata)
      doc.elements.each('resource-agent/parameters/parameter') { |param|
	print param.attributes["name"]
	ra.options[param.attributes["name"]] = param.attributes["name"]
      }
    end


    print ra.name+"\n"
    resource_agent_list[ra.name] = ra
  }
  resource_agent_list
end

def getConfigOptions(page="general")
  config_options = []
  case page
  when "general", nil
    cg1 = []
    cg1 << ConfigOption.new("Cluster Delay Time", "cdt",  "int", 4, "Seconds") 
    cg1 << ConfigOption.new("Batch Limit", "cdt",  "int", 4) 
    cg1 << ConfigOption.new("Default Action Timeout", "cdt",  "int", 4, "Seconds") 
    cg2 = []
    cg2 << ConfigOption.new("During timeout should cluster stop all active resources", "res_stop", "radio", "4", "", ["Yes","No"])

    cg3 = []
    cg3 << ConfigOption.new("PE Error Storage", "res_stop", "radio", "4", "", ["Yes","No"])
    cg3 << ConfigOption.new("PE Warning Storage", "res_stop", "radio", "4", "", ["Yes","No"])
    cg3 << ConfigOption.new("PE Input Storage", "res_stop", "radio", "4", "", ["Yes","No"])

    config_options << cg1
    config_options << cg2
    config_options << cg3
  when "pacemaker"
    cg1 = []
    cg1 << ConfigOption.new("Batch Limit", "batch-limit",  "int", 4, "jobs") 
    cg1 << ConfigOption.new("No Quorum Policy", "no-quorum-policy",  "dropdown","" ,"", {"ignore" => "Ignore","freeze" => "Freeze", "stop" => "Stop", "suicide" => "Suicide"}) 
    cg1 << ConfigOption.new("Symmetric", "symmetric-cluster", "check")
    cg2 = []
    cg2 << ConfigOption.new("Stonith Enabled", "stonith-enabled", "check")
    cg2 << ConfigOption.new("Stonith Action", "stonith-action",  "dropdown","" ,"", {"reboot" => "Reboot","poweroff" => "Poweroff"}) 
    cg3 = []
    cg3 << ConfigOption.new("Cluster Delay", "cluster-delay",  "int", 4) 
    cg3 << ConfigOption.new("Stop Orphan Resources", "stop-orphan-resources", "check")
    cg3 << ConfigOption.new("Stop Orphan Actions", "stop-orphan-actions", "check")
    cg3 << ConfigOption.new("Start Failure is Fatal", "start-failure-is-fatal", "check")
    cg3 << ConfigOption.new("PE Error Storage", "pe-error-series-max", "int", "4")
    cg3 << ConfigOption.new("PE Warning Storage", "pe-warn-series-max", "int", "4")
    cg3 << ConfigOption.new("PE Input Storage", "pe-input-series-max", "int", "4")

    config_options << cg1
    config_options << cg2
    config_options << cg3
  end

  allconfigoptions = []
  config_options.each { |i| i.each { |j| allconfigoptions << j } }
  ConfigOption.getDefaultValues(allconfigoptions)
  return config_options
end

class Node
  attr_accessor :active, :id, :name, :hostname

  def initialize(id=nil, name=nil, hostname=nil, active=nil)
    @id, @name, @hostname, @active = id, name, hostname, active
  end
end

class Resource 
  attr_accessor :id, :name, :type, :agent, :agentname, :role, :active, :orphaned, :managed,
    :failed, :failure_ignored, :nodes, :location, :options
  def initialize(e)
    @id = e.attributes["id"]
    @agentname = e.attributes["resource_agent"]
    @active = e.attributes["active"] == "true" ? true : false
    @orphaned = e.attributes["orphaned"] == "true" ? true : false
    @failed = e.attributes["failed"] == "true" ? true : false
    @nodes = []
    print "New Resource!\n"
    e.elements.each do |n| 
      print "NODE #{n.attributes["id"]}\n\n\n"
      node = Node.new
      node.name = n.attributes["name"]
      node.id = n.attributes["id"]
      @nodes.push(node)
    end
    if @nodes.length != 0
      @location = @nodes[0].name
    else
      @location = ""
    end
  end
end

class ResourceAgent
  attr_accessor :name, :options, :resource_class
  def initialize(name=nil, options={}, resource_class=nil)
    @name = name
    @options = options
    @resource_class = nil
  end

  def provider
    name.gsub(/::.*/,"")
  end

  def class
    name.gsub(/.*::(.*):.*/,"$1")
  end

  def type
    name.gsub(/.*:/,"")
  end
end

class ConfigOption
  attr_accessor :name, :configname, :type, :size, :units, :options, :default
  def initialize(name, configname, type="str", size = 10, units = "", options = [])
    @name = name
    @configname = configname
    @type = type
    @size = size
    @units = units
    @options = options
  end

  def value
    @@cache_value ||= {}
    @@cache_value = {}
    if @@cache_value[configname]  == nil
      puts "GET VALUE FOR: #{configname}"
      resource_options = `#{CRM_ATTRIBUTE} --get-value -n #{configname} 2>&1`
      resource_value = resource_options.sub(/.*value=/m,"").strip
      if resource_value == "(null)"
	@@cache_value[configname] = default
      else
	@@cache_value[configname] = resource_options.sub(/.*: /,"").strip
      end
    else
      print "#{configname} is defined: #{@@cache_value[configname]}...\n"
    end

    return @@cache_value[configname]
  end

  def self.getDefaultValues(cos)
    metadata = `/usr/lib64/heartbeat/pengine metadata`
    doc = REXML::Document.new(metadata)

    cos.each { |co|
      puts "resource-agent/parameters/parameter[@name='#{co.configname}']"
      doc.elements.each("resource-agent/parameters/parameter[@name='#{co.configname}']/content") { |e|
	co.default = e.attributes["default"]
	break
      }
    }
  end

  def checked(option)
    case type
    when "radio"
      val = value
      if option == "Yes"
	if val == "true"
	  return "checked"
	end
      else
	if val == "false"
	  return "checked"
	end
      end
    when "check"
      if value == "true"
	return "checked"
      end
    when "dropdown"
      print "Dropdown: #{value}-#{option}\n"
      if value == option
	return "selected"
      end
    end
  end

  def html
    case type
    when "int"
      return "<input name=\"#{configname}\" value=\"#{value}\" type=text size=#{size}>"
    when "str"
      return "<input name=\"#{configname}\" value=\"#{value}\" type=text size=#{size}>"
    when "radio"
      ret = ""
      options.each {|option|
	ret += "<input type=radio #{checked(option)} name=\"#{configname}\" value=\"#{option}\">#{option}"
      }
      return ret
    when "check"
      return "<input name=\"#{configname}\" #{checked(configname)} type=checkbox size=#{size}>"
    when "dropdown"
      ret = "<select name=\"#{configname}\">"
      options.each {|key, option|
	ret += "<option #{checked(key)} value=\"#{key}\">#{option}</option>"
      }
      ret += "<select"
      return ret
    end
  end
end
