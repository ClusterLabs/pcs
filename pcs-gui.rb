require 'sinatra'
require 'sinatra/reloader' if development?
require 'open3'
require 'rexml/document'

OCF_ROOT = "/usr/lib/ocf"
HEARTBEAT_AGENTS_DIR = "/usr/lib/ocf/resource.d/heartbeat/"

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
  stdin, stdout, stderror = Open3.popen3('/root/pcs/pcs/pcs status nodes')
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
  resource_options = `/root/pcs/pcs/pcs resource show #{resource_id}`
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
