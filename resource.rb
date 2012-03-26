def getResources
  stdin, stdout, stderror = Open3.popen3('/root/pacemaker/tools/crm_mon -r --as-xml=/tmp/testclusterstatus')
  stdout.readlines
  stderror.readlines

  doc = REXML::Document.new(File.open("/tmp/testclusterstatus", "rb"))
  resource_list = []
  doc.elements.each('crm_mon/resources/resource') do |e|
    resource_list.push(Resource.new(e))
  end
  doc.elements.each('crm_mon/resources/group/resource') do |e|
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

def getResourceAgents(resource_agent)
  resource_agent_list = {}
  if resource_agent == nil
    return resource_agent_list
  end
  agents = Dir.glob(HEARTBEAT_AGENTS_DIR + '*')
  agents.each { |a|
    ra = ResourceAgent.new
    ra.name = "ocf::heartbeat:" + a.sub(/.*\//,"")

    if a.sub(/.*\//,"") == resource_agent.sub(/.*:/,"")
      required_options, optional_options = getResourceMetadata(a)
      ra.required_options = required_options
      ra.optional_options = optional_options
    end
    resource_agent_list[ra.name] = ra
  }
  resource_agent_list
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
    @active = e.attributes["active"] == "true" ? true : false
    @nodes = []
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
