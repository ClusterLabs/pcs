require 'sinatra'
require 'sinatra/reloader' if development?
require 'open3'
require 'rexml/document'

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
  erb :resourcedeps, :layout => :main
end

get '/resources/?:resource?' do
  @resources = getResources
  @resource_agents = getResourceAgents
  @resourcemenuclass = "class=\"active\""

  @cur_resource = @resources[0]
  if params[:resource]
    @resources.each do |r|
      if r.id == params[:resource]
	@cur_resource = r
	break
      end
    end
  end

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

def getResourceAgents
  doc = REXML::Document.new(File.open("/usr/share/ccs/cluster.rng", "rb"))
  resource_agent_list = []
  doc.elements.each('grammar/define') do |e|
    if ["FENCE", "UNFENCE", "DEVICE","CHILDREN", "RESOURCEACTION", "FENCEDEVICEOPTIONS"].include?(e.attributes["name"]) 
      next
    end
    ra = ResourceAgent.new
    ra.name = e.attributes["name"]
    print ra.name+"\n"
  end
end


class Node
  attr_accessor :active, :id, :name, :hostname

  def initialize(id=nil, name=nil, hostname=nil, active=nil)
    @id, @name, @hostname, @active = id, name, hostname, active
  end
end

class Resource 
  attr_accessor :id, :name, :type, :agent, :role, :active, :orphaned, :managed,
    :failed, :failure_ignored, :nodes, :location
  def initialize(e)
    @id = e.attributes["id"]
    @agent = e.attributes["resource_agent"]
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
  attr_accessor :name, :attributes, :resource_class
  def initialize(name=nil, attributes=[], resource_class=nil)
    @name = name
    @attributes = attributes
    @resource_class = nil
  end
end
