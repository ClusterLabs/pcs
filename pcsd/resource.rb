require 'pp'

def getResourcesGroups(get_fence_devices = false, get_all_options = false)
  stdout, stderror, retval = run_cmd("crm_mon", "--one-shot", "-r", "--as-xml")
  if retval != 0
    return [],[], retval
  end

  crm_output = stdout

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
  doc.elements.each('crm_mon/resources/clone/resource') do |e|
    if e.attributes["resource_agent"] && e.attributes["resource_agent"].index('stonith:') == 0
      get_fence_devices && resource_list.push(Resource.new(e))
    else
      ms = false
      if e.parent.attributes["multi_state"] == "true"
      	ms = true
      end
      !get_fence_devices && resource_list.push(Resource.new(e, nil, !ms, ms))
    end
  end
  doc.elements.each('crm_mon/resources/clone/group/resource') do |e|
    if e.attributes["resource_agent"] && e.attributes["resource_agent"].index('stonith:') == 0
      get_fence_devices && resource_list.push(Resource.new(e,e.parent.parent.attributes["id"] + "/" + e.parent.attributes["id"]))
    else
      ms = false
      if e.parent.parent.attributes["multi_state"] == "true"
      	ms = true
      end
      !get_fence_devices && resource_list.push(Resource.new(e,e.parent.parent.attributes["id"] + "/" + e.parent.attributes["id"],!ms, ms))
    end
  end

  doc.elements.each('crm_mon/resources/group') do |e|
    group_list.push(e.attributes["id"])
  end

  resource_list = resource_list.sort_by{|a| (a.group ? "1" : "0").to_s + a.group.to_s + "-" +  a.id}

  if get_all_options
    stdout, stderror, retval = run_cmd("cibadmin", "-Q", "-l")
    cib_output = stdout
    resources_inst_attr_map = {}
    resources_meta_attr_map = {}
    begin
      doc = REXML::Document.new(cib_output.join("\n"))

      doc.elements.each('//primitive') do |r|
	resources_inst_attr_map[r.attributes["id"]] = {}
	resources_meta_attr_map[r.attributes["id"]] = {}
	r.each_recursive do |ia|
	  if ia.node_type == :element and ia.name == "nvpair"
	    if ia.parent.name == "instance_attributes"
	      resources_inst_attr_map[r.attributes["id"]][ia.attributes["name"]] = ia.attributes["value"]
	    elsif ia.parent.name == "meta_attributes"
	      resources_meta_attr_map[r.attributes["id"]][ia.attributes["name"]] = [ia.attributes["id"],ia.attributes["value"],ia.parent.parent.attributes["id"]]
	    end
	  end
	  if ["group","clone","master"].include?(r.parent.name)
	    r.parent.elements.each('./meta_attributes/nvpair') do |ma|
	      resources_meta_attr_map[r.attributes["id"]][ma.attributes["name"]] ||= []
	      resources_meta_attr_map[r.attributes["id"]][ma.attributes["name"]] = [ma.attributes["id"],ma.attributes["value"],ma.parent.parent.attributes["id"]]
            end
          end

	end

      end

      resource_list.each {|r|
	r.options = resources_inst_attr_map[r.id]
	r.instance_attr = resources_inst_attr_map[r.id]
	r.meta_attr = resources_meta_attr_map[r.id]
      }
    rescue REXML::ParseException
      $logger.info("ERROR: Parse Exception parsing cibadmin -Q")
    end
  end

  [resource_list, group_list, 0]
end

def getResourceOptions(resource_id,stonith=false)
  # Strip ':' from resource name (for clones & master/slave)
  resource_id = resource_id.sub(/(.*):.*/,'\1')

  ret = {}
  if stonith
    resource_options = `#{PCS} stonith show #{resource_id}`
  else
    resource_options = `#{PCS} resource show #{resource_id}`
  end
  resource_options.each_line { |line|
    keyval = line.strip.split(/: /,2)
    if keyval[0] == "Attributes" then
      options = keyval[1].split(/ /)
      options.each {|opt|
      	kv = opt.split(/=/)
      	ret[kv[0]] = kv[1]
      }
    end
  }
  return ret
end

def getAllConstraints()
  stdout, stderror, retval = run_cmd("cibadmin", "-Q", "-l", "--xpath", "//constraints")
  constraints = {}
  if retval != 0
    return {}
  end
  doc = REXML::Document.new(stdout.join("\n"))
  constraints = {}
  doc.elements.each('constraints/*') do |e|
    if e.name == 'rsc_location' and e.has_elements?()
      rule_export = RuleToExpression.new()
      e.elements.each('rule') { |rule|
        rule_info = {
          'rule_string' => rule_export.export(rule),
          'rsc' => e.attributes['rsc'],
        }
        rule.attributes.each { |name, value|
          rule_info[name] = value unless name == 'boolean-op'
        }
        if constraints[e.name]
          constraints[e.name] << rule_info
        else
          constraints[e.name] = [rule_info]
        end
      }
    elsif e.has_elements?()
      constraint_info = {}
      e.attributes.each { |name, value| constraint_info[name] = value }
      constraint_info['sets'] = []
      e.elements.each('resource_set') { |set_el|
        set_info = {}
        set_el.attributes.each { |name, value| set_info[name] = value }
        set_info['resources'] = []
        set_el.elements.each('resource_ref') { |res_el|
          set_info['resources'] << res_el.attributes['id']
        }
        constraint_info['sets'] << set_info
      }
      if constraints[e.name]
        constraints[e.name] << constraint_info
      else
        constraints[e.name] = [constraint_info]
      end
    else
      if constraints[e.name]
        constraints[e.name] << e.attributes
      else
        constraints[e.name] = [e.attributes]
      end
    end
  end
  return constraints
end

# Returns two arrays, one that lists resources that start before
# one that lists resources that start after
def getOrderingConstraints(resource_id)
  ordering_constraints = `#{PCS} constraint order show all`
  before = []
  after = []
  ordering_constraints.each_line { |line|
    if line.start_with?("Ordering Constraints:")
      next
    end
    line.strip!
    sline = line.split(/ /,6)
    if (sline[0] == resource_id)
      after << [sline[-1].to_s[4..-2],sline[2]]
    end
    if (sline[2] == resource_id)
      before << [sline[-1].to_s[4..-2],sline[0]]
    end
  }
  return before,after
end

# Returns two arrays, one that lists nodes that can run resource
# one that lists nodes that cannot
def getLocationConstraints(resource_id)
  location_constraints = `#{PCS} constraint location show all`
  enabled_nodes = {}
  disabled_nodes = {}
  inResource = false
  location_constraints.each_line { |line|
    line.strip!
    next if line.start_with?("Location Constraints:")
    if line.start_with?("Resource:")
      if line == "Resource: " + resource_id
	inResource = true
      else
	inResource = false
      end
      next
    end
    next if !inResource
    if line.start_with?("Enabled on:")
      prev = nil
      line.split(/: /,2)[1].split(/ /).each { |n|
	if n.start_with?("(id:")
	  enabled_nodes[prev][0] = n[4..-2]
	elsif n.start_with?("(")
	  enabled_nodes[prev][1] = n[1..-2]
	else
	  enabled_nodes[n] = []
	  prev = n
	end
      }
    end
    if line.start_with?("Disabled on:")
      prev = nil
      line.split(/: /,2)[1].split(/ /).each { |n|
	if n.start_with?("(id:")
	  disabled_nodes[prev][0] = n[4..-2]
	elsif n.start_with?("(")
	  disabled_nodes[prev][1] = n[1..-2]
	else
	  disabled_nodes[n] = []
	  prev = n
	end
      }
    end
  }
  return enabled_nodes,disabled_nodes
end

# Returns two arrays, one that lists resources that should be together
# one that lists resources that should be apart
def getColocationConstraints(resource_id)
  colocation_constraints = `#{PCS} constraint colocation show all`
  together = []
  apart = []
  colocation_constraints.each_line { |line|
    if line.start_with?("Colocation Constraints:")
      next
    end
    line.strip!
    sline = line.split(/ /,5)
    score = []
    score[0] = sline[4][4..-2]
    score[1] = sline[3][1..-2]
    if (sline[0] == resource_id)
      if score[1] == "INFINITY"  or (score[1] != "-INFINITY" and score[1].to_i >= 0)
	together << [sline[2],score]
      else
	apart << [sline[2],score]
      end
    end

    if (sline[2] == resource_id)
      if score[1] == "INFINITY"  or (score[1] != "-INFINITY" and score[1].to_i >= 0)
	together << [sline[0],score]
      else
	apart << [sline[0],score]
      end
    end
  }
  return together,apart
end

def getResourceMetadata(resourcepath)
  ENV['OCF_ROOT'] = OCF_ROOT
  metadata = `#{resourcepath} meta-data`
  doc = REXML::Document.new(metadata)
  options_required = {}
  options_optional = {}
  long_desc = ""
  short_desc = ""
  doc.elements.each('resource-agent/longdesc') {|ld|
    long_desc = ld.text ? ld.text.strip : ld.text
  }
  doc.elements.each('resource-agent/shortdesc') {|ld|
    short_desc = ld.text ? ld.text.strip : ld.text
  }

  doc.elements.each('resource-agent/parameters/parameter') { |param|
    temp_array = []
    if param.attributes["required"] == "1"
      if param.elements["shortdesc"] and param.elements["shortdesc"].text
	temp_array << param.elements["shortdesc"].text.strip
      else
      	temp_array << ""
      end
      if param.elements["longdesc"] and param.elements["longdesc"].text
	temp_array << param.elements["longdesc"].text.strip
      else
      	temp_array << ""
      end
      options_required[param.attributes["name"]] = temp_array
    else
      if param.elements["shortdesc"] and param.elements["shortdesc"].text
	temp_array << param.elements["shortdesc"].text.strip
      else
      	temp_array << ""
      end
      if param.elements["longdesc"] and param.elements["longdesc"].text
	temp_array << param.elements["longdesc"].text.strip
      else
      	temp_array << ""
      end
      options_optional[param.attributes["name"]] = temp_array
    end
  }
  [options_required, options_optional, [short_desc,long_desc]]
end

def getResourceAgents(resource_agent = nil)
  resource_agent_list = {}
  stdout, stderr, retval = run_cmd(PCS, "resource", "list", "--nodesc")
  if retval != 0
    logger.error("Error running 'pcs resource list --nodesc")
    logger.error(stdout + stderr)
    return {}
  end

  agents = stdout

  agents.each { |a|
    ra = ResourceAgent.new
    ra.name = a.chomp

    if resource_agent and (a.start_with?("ocf:heartbeat:") or a.start_with?("ocf:pacemaker:"))
      split_agent = ra.name.split(/:/)
      path = OCF_ROOT + '/resource.d/' + split_agent[1] + "/" + split_agent[2]
      required_options, optional_options, resource_info = getResourceMetadata(path)
      ra.required_options = required_options
      ra.optional_options = optional_options
      ra.info = resource_info
    end
    resource_agent_list[ra.name] = ra
  }
  resource_agent_list
end

class Resource 
  attr_accessor :id, :name, :type, :agent, :agentname, :role, :active,
    :orphaned, :managed, :failed, :failure_ignored, :nodes, :location,
    :options, :group, :clone, :stonith, :ms, :operations,
    :instance_attr, :meta_attr, :clone_id, :ms_id
  def initialize(e, group = nil, clone = false, ms = false)
    # Strip ':' from resource name (for clones & master/slave)
    @id = e.attributes["id"].sub(/(.*):.*/, '\1')
    @agentname = e.attributes["resource_agent"]
    @active = e.attributes["active"] == "true" ? true : false
    @orphaned = e.attributes["orphaned"] == "true" ? true : false
    @failed = e.attributes["failed"] == "true" ? true : false
    @active = e.attributes["active"] == "true" ? true : false
    @nodes = []
    # Strip ':' from group name (for clones & master/slave created from a group)
    @group = group ? group.sub(/(.*):.*/, '\1') : group
    @clone = clone
    @ms = ms
    @clone_id = nil
    @ms_id = nil
    @stonith = false
    @options = {}
    @instance_attr = {}
    @meta_attr = {}
    @operations = {}
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

    @clone_id = e.parent.attributes["id"] if @clone
    @ms_id = e.parent.attributes["id"] if @ms
  end

  def disabled
    if meta_attr and meta_attr["target-role"] and meta_attr["target-role"] == "Stopped"
      return true
    else
      return false
    end
  end
end

class ResourceAgent
  attr_accessor :name, :resource_class, :required_options, :optional_options, :info
  def initialize(name=nil, required_options={}, optional_options={}, resource_class=nil)
    @name = name
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

  def name
    @name
  end

  def to_json(options = {})
    JSON.generate({"type" => type})
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

class RuleToExpression

  def export(rule)
    boolean_op = 'and'
    if rule.attributes.key?('boolean-op')
      boolean_op = rule.attributes['boolean-op']
    end
    part_list = []
    rule.elements.each { |element|
      case element.name
        when 'expression'
          part_list << exportExpression(element)
        when 'date_expression'
          part_list << exportDateExpression(element)
        when 'rule'
          part_list << "(#{export(element)})"
      end
    }
    return part_list.join(" #{boolean_op} ")
  end

  private

  def exportExpression(expression)
    part_list = []
    if expression.attributes.key?('value')
      part_list << expression.attributes['attribute']
      part_list << expression.attributes['operation']
      if expression.attributes.key?('type')
        part_list << expression.attributes['type']
      end
      value = expression.attributes['value']
      value = "\"#{value}\"" if value.include?(' ')
      part_list << value
    else
      part_list << expression.attributes['operation']
      part_list << expression.attributes['attribute']
    end
    return part_list.join(' ')
  end

  def exportDateExpression(expression)
    part_list = []
    operation = expression.attributes['operation']
    if operation == 'date_spec'
      part_list << 'date-spec'
      expression.elements.each('date_spec') { |date_spec|
        date_spec.attributes.each { |name, value|
          part_list << "#{name}=#{value}" if name != 'id'
        }
      }
    elsif operation == 'in_range'
      part_list << 'date' << operation
      if expression.attributes.key?('start')
        part_list << expression.attributes['start'] << 'to'
      end
      if expression.attributes.key?('end')
        part_list << expression.attributes['end']
      end
      expression.elements.each('duration') { |duration|
        part_list << 'duration'
        duration.attributes.each { |name, value|
          part_list << "#{name}=#{value}" if name != 'id'
        }
      }
    else
      part_list << 'date' << operation
      if expression.attributes.key?('start')
        part_list << expression.attributes['start']
      end
      if expression.attributes.key?('end')
        part_list << expression.attributes['end']
      end
    end
    return part_list.join(' ')
  end

end
