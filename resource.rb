require 'pp'

def getResourcesGroups(get_fence_devices = false)
  stdin, stdout, stderror = Open3.popen3('crm_mon --one-shot -r --as-xml')
  crm_output =  stdout.readlines

  doc = REXML::Document.new(crm_output.join("\n"))
  resource_list = []
  group_list = []
  doc.elements.each('crm_mon/resources/resource') do |e|
    if e.attributes["resource_agent"] && e.attributes["resource_agent"].index('stonith:') == 0
      get_fence_devices && resource_list.push(Resource.new(e))
    else
      !get_fence_devices && resource_list.push(Resource.new(e))
    end
  end
  doc.elements.each('crm_mon/resources/group/resource') do |e|
    if e.attributes["resource_agent"] && e.attributes["resource_agent"].index('stonith:') == 0
      get_fence_devices && resource_list.push(Resource.new(e,e.parent.attributes["id"]))
    else
      !get_fence_devices && resource_list.push(Resource.new(e,e.parent.attributes["id"]))
    end
  end

  doc.elements.each('crm_mon/resources/group') do |e|
    group_list.push(e.attributes["id"])
  end

  resource_list.sort_by!{|a| (a.group ? "1" : "0").to_s + a.group.to_s + "-" +  a.id}

  [resource_list, group_list]
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

def getResourceMetadata(resourcepath)
  ENV['OCF_ROOT'] = OCF_ROOT
  metadata = `#{resourcepath} meta-data`
  doc = REXML::Document.new(metadata)
  options_required = {}
  options_optional = {}
  doc.elements.each('resource-agent/parameters/parameter') { |param|
    if param.attributes["required"] == "1"
      options_required[param.attributes["name"]] = ""
    else
      options_optional[param.attributes["name"]] = ""
    end
  }
  [options_required, options_optional]
end

def getResourceAgents(resource_agent = nil)
  resource_agent_list = {}
  agents = Dir.glob(HEARTBEAT_AGENTS_DIR + '*')
  agents.each { |a|
    ra = ResourceAgent.new
    ra.name = "ocf::heartbeat:" + a.sub(/.*\//,"")

    if resource_agent and a.sub(/.*\//,"") == resource_agent.sub(/.*:/,"")
      required_options, optional_options = getResourceMetadata(a)
      ra.required_options = required_options
      ra.optional_options = optional_options
    end
    resource_agent_list[ra.name] = ra
  }
  resource_agent_list
end

class Resource 
  attr_accessor :id, :name, :type, :agent, :agentname, :role, :active,
    :orphaned, :managed, :failed, :failure_ignored, :nodes, :location,
    :options, :group
  def initialize(e, group = nil)
    @id = e.attributes["id"]
    @agentname = e.attributes["resource_agent"]
    @active = e.attributes["active"] == "true" ? true : false
    @orphaned = e.attributes["orphaned"] == "true" ? true : false
    @failed = e.attributes["failed"] == "true" ? true : false
    @active = e.attributes["active"] == "true" ? true : false
    @nodes = []
    @group = group
    e.elements.each do |n| 
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
  attr_accessor :name, :resource_class, :required_options, :optional_options
  def initialize(name=nil, required_options={}, optional_options={}, resource_class=nil)
    @name = name
    @required_options = {}
    @optional_options = {}
    @required_options = required_options
    @optional_options = optional_options
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
