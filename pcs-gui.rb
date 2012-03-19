require 'sinatra'
require 'sinatra/reloader' if development?
require 'open3'
require 'rexml/document'
require './resource.rb'

use Rack::CommonLogger

also_reload './resource.rb'

configure do
  OCF_ROOT = "/usr/lib/ocf"
  HEARTBEAT_AGENTS_DIR = "/usr/lib/ocf/resource.d/heartbeat/"
  PENGINE = "/usr/lib64/heartbeat/pengine"
  PCS = "/root/pcs/pcs/pcs" 
  CRM_ATTRIBUTE = "/usr/sbin/crm_attribute"
end

set :port, 2222
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

    @loc_dep_allow, @loc_dep_disallow = getLocationDeps(@cur_node)
  end
end

post '*' do
  print params
  params[:config].each { |key, value|
    if (value == "on")
      value = "true"
    elsif value == "off"
      value = "false"
    end

    print `#{CRM_ATTRIBUTE} --attr-name #{key} --attr-value #{value} 2>&1`
    print "#{key} - #{value}\n"
  }
  redirect params[:splat][0]
end

get '/configure/?:page?' do
  @config_options = getConfigOptions(params[:page])
  @configuremenuclass = "class=\"active\""
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
  erb :resource, :layout => :main
end

get '/resources/metadata/:resourcename/?:new?' do
  @resource = ResourceAgent.new(params[:resourcename])
  @resource.options = getResourceMetadata(HEARTBEAT_AGENTS_DIR + params[:resourcename])
  @new_resource = params[:new]
  
  erb :resourceagentform
end

get '/nodes/?:node?' do
  setup()
  @nodemenuclass = "class=\"active\""
  @resources = getResources
  @resources_running = []
  @resources.each { |r|
    r.nodes && r.nodes.each {|n|
      if n.name == @cur_node.id
	@resources_running << r
      end
    }
  }
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

def getLocationDeps(cur_node)
  stdin, stdout, stderror = Open3.popen3("#{PCS} constraint location show nodes #{cur_node.id}")
  out = stdout.readlines
  deps_allow = []
  deps_disallow = []
  allowed = false
  disallowed = false
  out.each {|line|
    line = line.strip
    next if line == "Location Constraints:" or line.match(/^Node:/)

    if line == "Allowed to run:"
      allowed = true
      next
    elsif line == "Not allowed to run:"
      disallowed = true
      next
    end

    if disallowed == true
      deps_disallow << line.sub(/ .*/,"")
    elsif allowed == true
      deps_allow << line.sub(/ .*/,"")
    end
  }  
  [deps_allow, deps_disallow]
end

def getNodes
  stdin, stdout, stderror = Open3.popen3("#{PCS} status nodes")
  out = stdout.readlines
  [out[1].split(' ')[1..-1], out[2].split(' ')[1..-1]]
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
	@@cache_value[configname] = resource_value
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
    paramname = "config[#{configname}]"
    case type
    when "int"
      return "<input name=\"#{paramname}\" value=\"#{value}\" type=text size=#{size}>"
    when "str"
      return "<input name=\"#{paramname}\" value=\"#{value}\" type=text size=#{size}>"
    when "radio"
      ret = ""
      options.each {|option|
	ret += "<input type=radio #{checked(option)} name=\"#{paramname}\" value=\"#{option}\">#{option}"
      }
      return ret
    when "check"
      ret = "<input name=\"#{paramname}\" value=\"off\" type=hidden size=#{size}>"
      ret += "<input name=\"#{paramname}\" #{checked(paramname)} type=checkbox size=#{size}>"
      return ret
    when "dropdown"
      ret = "<select name=\"#{paramname}\">"
      options.each {|key, option|
	ret += "<option #{checked(key)} value=\"#{key}\">#{option}</option>"
      }
      ret += "<select"
      return ret
    end
  end
end
