def getFenceAgents(auth_user)
  fence_agent_list = {}
  stdout, stderr, retval = run_cmd(
    auth_user, PCS, "stonith", "list", "--nodesc"
  )
  if retval != 0
    $logger.error("Error running 'pcs stonith list --nodesc")
    $logger.error(stdout + stderr)
    return {}
  end

  agents = stdout
  agents.each { |a|
    fa = FenceAgent.new
    fa.name = a.chomp
    fence_agent_list[fa.name] = fa
  }
  return fence_agent_list
end

class FenceAgent
  attr_accessor :name, :resource_class, :required_options, :optional_options, :advanced_options, :info
  def initialize(name=nil, required_options={}, optional_options={}, resource_class=nil, advanced_options={})
    @name = name
    @required_options = {}
    @optional_options = {}
    @required_options = required_options
    @optional_options = optional_options
    @advanced_options = advanced_options
    @resource_class = nil
  end

  def type
    name
  end

  def to_json(options = {})
    JSON.generate({:type => name})
  end

  def long_desc
    if info && info.length >= 2
      return info[1]
    end
    return ""
  end

  def short_desc
    if info && info.length >= 1
      return info[0]
    end
    return ""
  end
end
