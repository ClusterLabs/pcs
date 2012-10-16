require 'sinatra'
require 'sinatra/reloader' if development?  #require 'rack/ssl'
require 'open3'
require 'rexml/document'
require 'resource.rb'
require 'remote.rb'
require 'fenceagent.rb'
require 'cluster.rb'
require 'config.rb'
require 'pcs.rb'
require 'auth.rb'
require 'webrick'
require 'pp'
require 'webrick/https'
require 'openssl'
require 'logger'

use Rack::CommonLogger
#use Rack::SSL

also_reload 'resource.rb'
also_reload 'remote.rb'
also_reload 'fenceagent.rb'
also_reload 'cluster.rb'
also_reload 'config.rb'
also_reload 'pcs.rb'
also_reload 'auth.rb'

enable :sessions

before do
  @@cluster_name = get_cluster_version()
  puts "SESSION:"
  pp session
  puts "COOKIES:"
  pp request.cookies
  if request.path != '/login' and not request.path == "/logout" and not request.path == '/remote/auth'
    protected! 
  end
end

configure do
  OCF_ROOT = "/usr/lib/ocf"
  HEARTBEAT_AGENTS_DIR = "/usr/lib/ocf/resource.d/heartbeat/"
  PENGINE = "/usr/libexec/pacemaker/pengine"
  if Dir.pwd == "/var/lib/pcsd"
    PCS = "/sbin/pcs" 
  else
    PCS = "../pcs/pcs/pcs" 
  end
  CRM_ATTRIBUTE = "/usr/sbin/crm_attribute"
  COROSYNC_CONF = "/etc/corosync/corosync.conf"
  SETTINGS_FILE = "pcs_settings.conf"
  $user_pass_file = "pcs_users.conf"

  $logger = Logger.new('/var/lib/pcsd/pcsd.log', 'weekly')
  $logger.level = Logger::INFO
  $stdout.reopen('/var/lib/pcsd/pcsd-debug.log', 'a')
  $stdout.sync = true
  $stderr.reopen($stdout)
#  $stderr.reopen('/var/lib/pcsd/pcsd-stderror', 'a')
end

set :logging, true
set :run, false

if not defined? @@cur_node_name
  @@cur_node_name = `hostname`.chomp
end

helpers do
  def protected!
    if not PCSAuth.isLoggedIn(session, request.cookies)
      if request.path.start_with?('/remote')
	puts "ERROR: Request without authentication"
	halt [401, '{"notauthorized":"true"}']
      else
	session[:pre_login_path] = request.path
	redirect '/login'
      end
    end
  end

  def setup
    @nodes_online, @nodes_offline = get_nodes()
    @nodes = {}
    @nodes_online.each do |i|
      @nodes[i]  = Node.new(i, i, i, true)
    end
    @nodes_offline.each do |i|
      @nodes[i]  = Node.new(i, i, i, false)
    end

    if @nodes_online.length == 0
      @pcs_node_offline = true
    end

    if params[:node]
      @cur_node = @nodes[params[:node]]
      if not @cur_node
	@cur_node = @nodes.values[0]
      end
    else
      @cur_node = @nodes.values[0]
    end

    if @nodes.length != 0
      @loc_dep_allow, @loc_dep_disallow = getLocationDeps(@cur_node)
    end
    @nodes = @nodes_online.concat(@nodes_offline)
  end

  def getParamLine(params)
    param_line = ""
    params.each { |param, val|
      if param.start_with?("_res_paramne_") or (param.start_with?("_res_paramempty_") and val != "")
	myparam = param.sub(/^_res_paramne_/,"").sub(/^_res_paramempty_/,"")
	param_line += " #{myparam}=#{val}"
      end
    }
    param_line
  end
end


get('/login'){ erb :login, :layout => :main }

get '/logout' do 
  session.clear
  erb :login, :layout => :main
end

post '/login' do
  if PCSAuth.validUser(params['username'],params['password'])
    session["username"] = params['username']
    if session["pre_login_path"]
      plp = session["pre_login_path"]
      session.delete("pre_login_path")
      redirect plp
    else
      redirect '/'
    end
  else
    redirect '/login?badlogin=1'
  end
end

post '/fencerm' do
  params.each { |k,v|
    if k.index("resid-") == 0
      run_cmd(PCS, "resource", "delete", k.gsub("resid-",""))
    end
  }
  redirect "/fencedevices/"
end

get '/configure/?:page?' do
  @config_options = getConfigOptions(params[:page])
  @configuremenuclass = "class=\"active\""
  erb :configure, :layout => :main
end

get '/fencedevices2/?:fencedevice?' do
  @resources, @groups = getResourcesGroups(true)
  pp @resources

  if @resources.length == 0
    @cur_resource = nil
    @resource_agents = getFenceAgents()
  else
    @cur_resource = @resources[0]
    if params[:fencedevice]
      @resources.each do |fd|
	if fd.id == params[:fencedevice]
	  @cur_resource = fd
	  break
	end
      end
    end
    @cur_resource.options = getResourceOptions(@cur_resource.id)
    @resource_agents = getFenceAgents(@cur_resource.agentname)
  end
  erb :fencedevices, :layout => :main
end

['/resources2/?:resource?', '/resource_list/?:resource?'].each do |path|
  get path do
    @load_data = true
    @resources, @groups = getResourcesGroups
    @resourcemenuclass = "class=\"active\""

    if @resources.length == 0
      @cur_resource = nil
      @resource_agents = getResourceAgents()
    else
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
      @ord_dep_before, @ord_dep_after  = getOrderingConstraints(@cur_resource.id)
      @colo_dep_together, @colo_dep_apart = getColocationConstraints(@cur_resource.id)
      @enabled_nodes, @disabled_nodes = getLocationConstraints(@cur_resource.id)
    end

    @nodes_online, @nodes_offline = get_nodes

    if path.start_with? '/resource_list'
      erb :_resource_list
    else
      erb :resource, :layout => :main
    end
  end
end

get '/resources/metadata/:resourcename/?:new?' do
  return ""
  @resource = ResourceAgent.new(params[:resourcename])
  @resource.required_options, @resource.optional_options = getResourceMetadata(HEARTBEAT_AGENTS_DIR + params[:resourcename])
  @new_resource = params[:new]
  @resources, @groups = getResourcesGroups
  
  erb :resourceagentform
end

get '/fencedevices/metadata/:fencedevicename/?:new?' do
  return ""
  @fenceagent = FenceAgent.new(params[:fencedevicename])
  @fenceagent.required_options, @fenceagent.optional_options = getFenceAgentMetadata(params[:fencedevicename])
  @new_fenceagent = params[:new]
  
  erb :fenceagentform
end

get '/nodes/?:node?' do
  setup()
  @load_data = true
#  @nodemenuclass = "class=\"active\""
  @resources, @groups = getResourcesGroups
#  @resources_running = []
#  @resources.each { |r|
#    @cur_node && r.nodes && r.nodes.each {|n|
#      if n.name == @cur_node.id
#	@resources_running << r
#      end
#    }
#  }
  @resource_agents = getResourceAgents()
  @stonith_agents = getFenceAgents()
#  @nodes = @nodes.sort_by{|k,v|k}
  erb :nodes, :layout => :main
end

get '/manage/?' do
  @manage = true
  pcs_config = PCSConfig.new
  @clusters = pcs_config.clusters
  erb :manage, :layout => :main
end

get '/managec/:cluster/main' do
  @@cluster_name = params[:cluster]
#  @resources, @groups = getResourcesGroups
  @load_data = true
  @resources = []
  @groups = []
  @resource_agents = get_resource_agents_avail() 
  @stonith_agents = get_stonith_agents_avail() 
  puts "RA"
  puts @resource_agents
  puts "ST"
  puts @stonith_agents
  @nodes = get_cluster_nodes(params[:cluster])
  @config_options = getConfigOptions2()
  erb :nodes, :layout => :main
end

get '/managec/:cluster/status_all' do
  status_all("",get_cluster_nodes(params[:cluster]))
end

get '/managec/:cluster/?*' do
  puts "Lambda A GET"
  pp params[:splat]
  pp params
  puts "Lambda B"
  raw_data = request.env["rack.input"].read
  p "Raw Data"
  pp raw_data
  if params[:cluster]
    send_cluster_request_with_token(params[:cluster], "/" + params[:splat].join("/"), false, params, false, raw_data)
  end
end

post '/managec/:cluster/?*' do
  puts "Lambda A POST"
  pp params[:splat]
  pp params
  puts "Lambda B"
  raw_data = request.env["rack.input"].read
  p "Raw Data"
  pp raw_data
  if params[:cluster]
    send_cluster_request_with_token(params[:cluster], "/" + params[:splat].join("/"), true, params, false, raw_data)
  end
end

get '/manage/:node/?*' do
  if params[:node]
    return send_request_with_token(params[:node], params[:splat].join("/"), false, {}, false)
  end
end

post '/manage/existingcluster' do
  pcs_config = PCSConfig.new
  node = params['node-name']
  status =  JSON.parse(send_request_with_token(node, 'status'))
  if status.has_key?("corosync_offline") and
    status.has_key?("corosync_online") then
    nodes = status["corosync_offline"] + status["corosync_online"]
    pcs_config.clusters << Cluster.new(status["cluster_name"], nodes)
    pcs_config.save
    redirect '/manage'
  else
    redirect '/manage/?error=notauthorized'
  end
end

post '/manage/newcluster' do
  pcs_config = PCSConfig.new
  @manage = true
  @cluster_name = params[:clustername]
  @nodes = []
  params.each {|k,v|
    if k.start_with?("node-") and v != ""
      @nodes << v
    end
  }
  pcs_config.clusters << Cluster.new(@cluster_name, @nodes)
  pcs_config.save

  run_cmd(PCS, "cluster", "setup", "--start", @cluster_name, *@nodes)
  redirect '/manage'
end

post '/manage/removecluster' do
  pcs_config = PCSConfig.new
  params.each { |k,v|
    if k.start_with?("clusterid-")
      pcs_config.remove_cluster(k.sub("clusterid-",""))
    end
  }
  pcs_config.save
  redirect '/manage'
end

post '/resource_cmd/rm_constraint' do
  if params[:constraint_id]
    remove_constraint(params[:constraint_id])
  end
end

get '/' do
  print "Redirecting...\n"
  call(env.merge("PATH_INFO" => '/manage'))
end

get '/remote/?:command?' do
  return remote(params,request)
end

post '/remote/?:command?' do
  return remote(params,request)
end

get '*' do
  print params[:splat]
  print "2Redirecting...\n"
  return "Bad URL"
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

def getConfigOptions2()
  config_options = {}
  general_page = []
  general_page << ConfigOption.new("Cluster Delay Time", "cluster-delay",  "int", 4, "Seconds") 
#  general_page << ConfigOption.new("Batch Limit", "cdt",  "int", 4) 
#  general_page << ConfigOption.new("Default Action Timeout", "cdt",  "int", 4, "Seconds") 
#  general_page << ConfigOption.new("During timeout should cluster stop all active resources", "res_stop", "radio", "4", "", ["Yes","No"])

#  general_page << ConfigOption.new("PE Error Storage", "res_stop", "radio", "4", "", ["Yes","No"])
#  general_page << ConfigOption.new("PE Warning Storage", "res_stop", "radio", "4", "", ["Yes","No"])
#  general_page << ConfigOption.new("PE Input Storage", "res_stop", "radio", "4", "", ["Yes","No"])
  config_options["general"] = general_page

  pacemaker_page = []
  pacemaker_page << ConfigOption.new("Batch Limit", "batch-limit",  "int", 4, "jobs")
  pacemaker_page << ConfigOption.new("No Quorum Policy", "no-quorum-policy",  "dropdown","" ,"", {"ignore" => "Ignore","freeze" => "Freeze", "stop" => "Stop", "suicide" => "Suicide"})
  pacemaker_page << ConfigOption.new("Symmetric", "symmetric-cluster", "check")
  pacemaker_page << ConfigOption.new("Stonith Enabled", "stonith-enabled", "check")
  pacemaker_page << ConfigOption.new("Stonith Action", "stonith-action",  "dropdown","" ,"", {"reboot" => "Reboot","poweroff" => "Poweroff"}) 
  pacemaker_page << ConfigOption.new("Cluster Delay", "cluster-delay",  "int", 4) 
  pacemaker_page << ConfigOption.new("Stop Orphan Resources", "stop-orphan-resources", "check")
  pacemaker_page << ConfigOption.new("Stop Orphan Actions", "stop-orphan-actions", "check")
  pacemaker_page << ConfigOption.new("Start Failure is Fatal", "start-failure-is-fatal", "check")
  pacemaker_page << ConfigOption.new("PE Error Storage", "pe-error-series-max", "int", "4")
  pacemaker_page << ConfigOption.new("PE Warning Storage", "pe-warn-series-max", "int", "4")
  pacemaker_page << ConfigOption.new("PE Input Storage", "pe-input-series-max", "int", "4")
  config_options["pacemaker"] = pacemaker_page

  return config_options
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
    return "{{#{configname}}}"
    @@cache_value ||= {}
    @@cache_value = {}
    if @@cache_value[configname]  == nil
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
    metadata = `#{PENGINE} metadata`
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
    js_name = configname.gsub(/-/,"_")
    case type
    when "int"
      return "<input name=\"#{paramname}\" {{bindAttr value=\"cluster_settings.#{js_name}.value\"}} type=text size=#{size}>"
    when "str"
      return "<input name=\"#{paramname}\" value=\"{{cluster_name}}\" type=text size=#{size}>"
    when "radio"
      ret = ""
      options.each {|option|
	ret += "<input type=radio #{checked(option)} name=\"#{paramname}\" value=\"#{option}\">#{option}"
      }
      return ret
    when "check"
      ret = "{{view Ember.Checkbox checkedBinding=\"cluster_settings.#{js_name}.value\"}}"
      ret += "<input type=hidden name=\"#{js_name}-checkbox\" value=\"1\">"
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
