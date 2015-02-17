require 'sinatra'
require 'sinatra/reloader' if development?  #require 'rack/ssl'
require 'sinatra/cookies'
require 'rexml/document'
require 'resource.rb'
require 'remote.rb'
require 'fenceagent.rb'
require 'cluster.rb'
require 'config.rb'
require 'pcs.rb'
require 'auth.rb'
require 'wizard.rb'
require 'webrick'
require 'pp'
require 'webrick/https'
require 'openssl'
require 'logger'

Dir["wizards/*.rb"].each {|file| require file}

use Rack::CommonLogger

COOKIE_FILE = "/var/lib/pcsd/pcsd.cookiesecret"

begin
  secret = File.read(COOKIE_FILE)
rescue Errno::ENOENT => e
  secret = SecureRandom.hex(30)
  File.open(COOKIE_FILE, 'w', 0700) {|f| f.write(secret)}
end

use Rack::Session::Cookie,
  :expire_after => 60 * 60,
  :secret => secret

#use Rack::SSL

Dir["wizards/*.rb"].each {|file| also_reload file}
also_reload 'resource.rb'
also_reload 'remote.rb'
also_reload 'fenceagent.rb'
also_reload 'cluster.rb'
also_reload 'config.rb'
also_reload 'pcs.rb'
also_reload 'auth.rb'
also_reload 'wizard.rb'

enable :sessions

before do
  $session = session
  $cookies = cookies
  if request.path != '/login' and not request.path == "/logout" and not request.path == '/remote/auth'
    protected! 
  end
  $cluster_name = get_cluster_version()
  @errorval = session[:errorval]
  @error = session[:error]
  session[:errorval] = nil
  session[:error] = nil
end

configure do
  PCS_VERSION = "0.9.139"
  ISRHEL6 = is_rhel6
  ISSYSTEMCTL = is_systemctl
  DISABLE_GUI = false

  OCF_ROOT = "/usr/lib/ocf"
  HEARTBEAT_AGENTS_DIR = "/usr/lib/ocf/resource.d/heartbeat/"
  PACEMAKER_AGENTS_DIR = "/usr/lib/ocf/resource.d/pacemaker/"
  PENGINE = "/usr/libexec/pacemaker/pengine"
  CRM_NODE = "/usr/sbin/crm_node"
  if Dir.pwd == "/var/lib/pcsd"
    PCS = "/usr/sbin/pcs" 
  else
    PCS = "../pcs/pcs" 
  end
  CRM_ATTRIBUTE = "/usr/sbin/crm_attribute"
  COROSYNC = "/usr/sbin/corosync"
  if ISRHEL6
    COROSYNC_CMAPCTL = "/usr/sbin/corosync-objctl"
  else
    COROSYNC_CMAPCTL = "/usr/sbin/corosync-cmapctl"
  end
  COROSYNC_QUORUMTOOL = "/usr/sbin/corosync-quorumtool"
  CMAN_TOOL = "/usr/sbin/cman_tool"
  PACEMAKERD = "/usr/sbin/pacemakerd"
  COROSYNC_CONF = "/etc/corosync/corosync.conf"
  CLUSTER_CONF = "/etc/cluster/cluster.conf"
  CIBADMIN = "/usr/sbin/cibadmin"
  SETTINGS_FILE = "pcs_settings.conf"
  $user_pass_file = "pcs_users.conf"

  logger = File.open("/var/log/pcsd/pcsd.log", "a+", 0600)
  STDOUT.reopen(logger)
  STDERR.reopen(logger)
  STDOUT.sync = true
  STDERR.sync = true
  $logger = Logger.new('/var/log/pcsd/pcsd.log')
  if ENV['PCSD_DEBUG'] and ENV['PCSD_DEBUG'].downcase == "true" then
    $logger.level = Logger::DEBUG
    $logger.info "PCSD Debugging enabled"
  else
    $logger.level = Logger::INFO
  end

  if ISRHEL6
    $logger.debug "Detected RHEL 6"
  else
    $logger.debug "Did not detect RHEL 6"
  end

  if not defined? $cur_node_name
    $cur_node_name = `hostname`.chomp
  end
end

set :logging, true
set :run, false

helpers do
  def protected!
    if not PCSAuth.isLoggedIn(session, request.cookies)
      # If we're on /managec/<cluster_name>/main we redirect
      match_expr = "/managec/(.*)/(.*)"
      mymatch = request.path.match(match_expr)
      on_managec_main = false
      if mymatch and mymatch.length >= 3 and mymatch[2] == "main"
        on_managec_main = true
      end

      if request.path.start_with?('/remote') or (request.path.match(match_expr) and not on_managec_main)
	$logger.info "ERROR: Request without authentication"
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
    meta_options = ""
    params.each { |param, val|
      if param.start_with?("_res_paramne_") or (param.start_with?("_res_paramempty_") and val != "")
	myparam = param.sub(/^_res_paramne_/,"").sub(/^_res_paramempty_/,"")
	param_line += " #{myparam}=#{val}"
      end
      if param == "disabled"
      	meta_options += " meta target-role=Stopped"
      end
    }
    return param_line + meta_options
  end
end

get '/remote/?:command?' do
  return remote(params,request)
end

post '/remote/?:command?' do
  return remote(params,request)
end

if not DISABLE_GUI
  get('/login'){ erb :login, :layout => :main }

  get '/logout' do 
    session.clear
    erb :login, :layout => :main
  end

  post '/login' do
    if PCSAuth.validUser(params['username'],params['password'])
      session["username"] = params['username']
      # Temporarily ignore pre_login_path until we come up with a list of valid
      # paths to redirect to (to prevent status_all issues)
      #    if session["pre_login_path"]
      #      plp = session["pre_login_path"]
      #      session.delete("pre_login_path")
      #      pp "Pre Login Path: " + plp
      #      if plp == "" or plp == "/"
      #      	plp = '/manage'
      #      end
      #      redirect plp
      #    else
      redirect '/manage'
      #    end
    else
      session["bad_login_name"] = params['username']
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
    @load_data = true
    erb :manage, :layout => :main
  end

  get '/managec/:cluster/main' do
    @cluster_name = params[:cluster]
    #  @resources, @groups = getResourcesGroups
    @load_data = true
    pcs_config = PCSConfig.new
    @clusters = pcs_config.clusters
    @resources = []
    @groups = []
    @nodes = get_cluster_nodes(params[:cluster])
    if @nodes == []
      redirect '/manage/?error=badclustername&errorval=' + params[:cluster] + '#manage'
    end
    @resource_agents = get_resource_agents_avail() 
    @stonith_agents = get_stonith_agents_avail() 
    @config_options = getConfigOptions2(@cluster_name)

    erb :nodes, :layout => :main
  end

  get '/managec/:cluster/status_all' do
    status_all(params,get_cluster_nodes(params[:cluster]))
  end

  get '/managec/:cluster/?*' do
    raw_data = request.env["rack.input"].read
    if params[:cluster]
      send_cluster_request_with_token(params[:cluster], "/" + params[:splat].join("/"), false, params, true, raw_data)
    end
  end

  post '/managec/:cluster/?*' do
    raw_data = request.env["rack.input"].read
    if params[:cluster]
      request = "/" + params[:splat].join("/")
      code, out = send_cluster_request_with_token(params[:cluster], request, true, params, true, raw_data)

      # backward compatibility layer BEGIN
      # This code correctly remove constraints on pcs/pcsd version 0.9.137 and older
      redirection = {
          "/remove_constraint_remote" => "/resource_cmd/rm_constraint",
          "/remove_constraint_rule_remote" => "/resource_cmd/rm_constraint_rule"
      }
      if code == 404 and redirection.key?(request)
        code, out = send_cluster_request_with_token(params[:cluster], redirection[request], true, params, false, raw_data)
      end
      # bcl END
      return code, out
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
    code, result = send_request_with_token(node, 'status')
    status = JSON.parse(result)
    if status.has_key?("corosync_offline") and
      status.has_key?("corosync_online") then
      nodes = status["corosync_offline"] + status["corosync_online"]

      if status["cluster_name"] == ""
        session[:error] = "noname"
        session[:errorval] = node
        redirect '/manage'
      end

      if pcs_config.is_cluster_name_in_use(status["cluster_name"])
        session[:error] = "duplicatename"
        session[:errorval] = status["cluster_name"]
        redirect '/manage'
      end

      pcs_config.clusters << Cluster.new(status["cluster_name"], nodes)
      pcs_config.save
      redirect '/manage'
    else
      redirect '/manage/?error=notauthorized#manage'
    end
  end

  post '/manage/newcluster' do
    pcs_config = PCSConfig.new
    @manage = true
    @cluster_name = params[:clustername]
    @nodes = []
    @nodes_rrp = []
    options = {}
    params.each {|k,v|
      if k.start_with?("node-") and v != ""
        @nodes << v
        if params.has_key?("ring1-" + k) and params["ring1-" + k] != ""
          @nodes_rrp << v + "," + params["ring1-" + k]
        else
          @nodes_rrp << v
        end
      end
      if k.start_with?("config-") and v != ""
        options[k.sub("config-","")] = v
      end
    }
    if pcs_config.is_cluster_name_in_use(@cluster_name)
      session[:error] = "duplicatename"
      session[:errorval] = @cluster_name
      redirect '/manage'
    end

    @nodes.each {|n|
      if pcs_config.is_node_in_use(n)
        session[:error] = "duplicatenodename"
        session[:errorval] = n
        redirect '/manage'
      end
    }

    $logger.info("Sending setup cluster request for: " + @cluster_name + " to: " + @nodes[0])
    code,out = send_request_with_token(@nodes[0], "setup_cluster", true, {:clustername => @cluster_name, :nodes => @nodes_rrp.join(';'), :options => options.to_json}, true, nil, 60)

    if code == 200
      pcs_config.clusters << Cluster.new(@cluster_name, @nodes)
      pcs_config.save
    else
      session[:error] = "unabletocreate"
      session[:errorval] = out
    end

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

  get '/' do
    $logger.info "Redirecting '/'...\n"
    redirect '/manage'
  end

  get '/wizards/?:wizard?' do
    return wizard(params, request, params[:wizard])
  end

  post '/wizards/?:wizard?' do
    return wizard(params, request, params[:wizard])
  end

  get '*' do
    $logger.debug "Bad URL"
    $logger.debug params[:splat]
    $logger.info "Redirecting '*'...\n"
    redirect '/manage'
    redirect "Bad URL"
    call(env.merge("PATH_INFO" => '/nodes'))
  end
else
  get '*' do
    $logger.debug "ERROR: GUI Disabled, Bad URL"
    $logger.debug params[:splat]
    $logger.info "Redirecting '*'...\n"
    return "PCSD GUI is disabled"
  end

end

def getLocationDeps(cur_node)
  out, stderror, retval = run_cmd(PCS, "constraint", "location", "show", "nodes", cur_node.id)
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

def getConfigOptions2(cluster_name)
  config_options = {}
  general_page = []
#  general_page << ConfigOption.new("Cluster Delay Time", "cluster-delay",  "int", 4, "Seconds") 
#  general_page << ConfigOption.new("Batch Limit", "cdt",  "int", 4) 
#  general_page << ConfigOption.new("Default Action Timeout", "cdt",  "int", 4, "Seconds") 
#  general_page << ConfigOption.new("During timeout should cluster stop all active resources", "res_stop", "radio", "4", "", ["Yes","No"])

#  general_page << ConfigOption.new("PE Error Storage", "res_stop", "radio", "4", "", ["Yes","No"])
#  general_page << ConfigOption.new("PE Warning Storage", "res_stop", "radio", "4", "", ["Yes","No"])
#  general_page << ConfigOption.new("PE Input Storage", "res_stop", "radio", "4", "", ["Yes","No"])
  config_options["general"] = general_page

  pacemaker_page = []
  pacemaker_page << ConfigOption.new("Batch Limit", "batch-limit",  "int", 4, "jobs", {},  'The number of jobs that pacemaker is allowed to execute in parallel. The "correct" value will depend on the speed and load of your network and cluster nodes.')
  pacemaker_page << ConfigOption.new("No Quorum Policy", "no-quorum-policy",  "dropdown","" ,"", {"ignore" => "Ignore","freeze" => "Freeze", "stop" => "Stop", "suicide" => "Suicide"}, 'What to do when the cluster does not have quorum. Allowed values:
  * ignore - continue all resource management
  * freeze - continue resource management, but don\'t recover resources from nodes not in the affected partition
  * stop - stop all resources in the affected cluster partition
  * suicide - fence all nodes in the affected cluster partition')
  pacemaker_page << ConfigOption.new("Symmetric", "symmetric-cluster", "check",nil ,nil,nil,'Can all resources run on any node by default?')
  pacemaker_page << ConfigOption.new("Stonith Enabled", "stonith-enabled", "check",nil,nil,nil,'Should failed nodes and nodes with resources that can\'t be stopped be shot? If you value your data, set up a STONITH device and enable this.
If checked, the cluster will refuse to start resources unless one or more STONITH resources have been configured also.')
  pacemaker_page << ConfigOption.new("Stonith Action", "stonith-action",  "dropdown","" ,"", {"reboot" => "Reboot","off" => "Off", "poweroff" => "Poweroff"},'Action to send to STONITH device. Allowed values: reboot, off. The value poweroff is also allowed, but is only used for legacy devices.') 
  pacemaker_page << ConfigOption.new("Cluster Delay", "cluster-delay",  "int", 4,nil,nil,'Round trip delay over the network (excluding action execution). The "correct" value will depend on the speed and load of your network and cluster nodes.') 
  pacemaker_page << ConfigOption.new("Stop Orphan Resources", "stop-orphan-resources", "check",nil,nil,nil,'Should deleted resources be stopped?')
  pacemaker_page << ConfigOption.new("Stop Orphan Actions", "stop-orphan-actions", "check",nil,nil,nil,'Should deleted actions be cancelled?'
                                    )
  pacemaker_page << ConfigOption.new("Start Failure is Fatal", "start-failure-is-fatal", "check",nil,nil,nil,'When unchecked, the cluster will instead use the resource\'s failcount and value for resource-failure-stickiness.')
  pacemaker_page << ConfigOption.new("PE Error Storage", "pe-error-series-max", "int", "4",nil,nil,'The number of policy engine (PE) inputs resulting in ERRORs to save. Used when reporting problems.')
  pacemaker_page << ConfigOption.new("PE Warning Storage", "pe-warn-series-max", "int", "4",nil,nil,'The number of PE inputs resulting in WARNINGs to save. Used when reporting problems.')
  pacemaker_page << ConfigOption.new("PE Input Storage", "pe-input-series-max", "int", "4",nil,nil,'The number of "normal" PE inputs to save. Used when reporting problems.')
  pacemaker_page << ConfigOption.new("Enable ACLs", "enable-acl", "check", nil,nil,nil,'Should pacemaker use ACLs to determine access to cluster')
  config_options["pacemaker"] = pacemaker_page

  allconfigoptions = []
  config_options.each { |i,k| k.each { |j| allconfigoptions << j } }
  ConfigOption.getDefaultValues(allconfigoptions)
  ConfigOption.loadValues(allconfigoptions,cluster_name)
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
  attr_accessor :name, :configname, :type, :size, :units, :options, :default, :value, :desc
  def initialize(name, configname, type="str", size = 10, units = "", options = [], desc = "")
    @name = name
    @configname = configname
    @type = type
    @size = size
    @units = units
    @options = options
    @desc = desc
  end

  def self.loadValues(cos,cluster_name)
    code,output = send_cluster_request_with_token(cluster_name, "get_cib")
    $logger.info(code)
    if code != 200
      $logger.info "Error: unable to load cib"
      $logger.info output
      return
    end

    doc = REXML::Document.new(output)

    cos.each {|co|
      prop_found = false
      doc.elements.each("cib/configuration/crm_config/cluster_property_set/nvpair[@name='#{co.configname}']") { |e|
      	co.value = e.attributes["value"]
      	prop_found = true
      }
      if prop_found == false
      	co.value = co.default
      end
    }
  end

  def self.getDefaultValues(cos)
    metadata = `#{PENGINE} metadata`
    doc = REXML::Document.new(metadata)

    cos.each { |co|
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
      if value == "true" || value == "on"
	return "checked"
      else
	return ""
      end
    when "dropdown"
      if value == option
	return "selected"
      end
    end
  end

  def html
    paramname = "config[#{configname}]"
    hidden_paramname = "hidden[#{configname}]"
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
      ret = "<input type=checkbox name=\"#{paramname}\" " + self.checked(nil) + ">"
      ret += "<input type=hidden name=\"#{hidden_paramname}\" value=\"off\">"
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

helpers do
  def h(text)
    Rack::Utils.escape_html(text)
  end

  def nl2br(text)
    text.gsub(/\n/, "<br>")
  end
end
