require 'pathname'

def get_normalized_role(role)
  role_map = {
    'Promoted' => 'Master',
    'Unpromoted' => 'Slave',
  }
  return role_map.fetch(role, role)
end

def run_crm_mon_xml(auth_user)
  stdout, stderr, _ = run_cmd(auth_user, CRM_MON, '--help-all')
  new_format = (
    stdout.join("\n").include?('--output-as=') or
    stderr.join("\n").include?('--output-as=')
  )
  cmd = [CRM_MON, '--one-shot', '--inactive']
  if new_format
    cmd << '--output-as=xml'
  else
    cmd << '--as-xml'
  end
  stdout, stderr, retval = run_cmd(auth_user, *cmd)
  return stdout, stderr, retval
end

# TODO deprecated, remove, not used anymore
def getResourcesGroups(auth_user, get_fence_devices = false, get_all_options = false,
  get_operations=false
)
  crm_output, stderr, retval = run_crm_mon_xml(auth_user)
  if retval != 0
    return [],[], retval
  end

  doc = REXML::Document.new(crm_output.join("\n"))
  resource_list = []
  group_list = []
  doc.elements.each('/crm_mon/resources/resource | /pacemaker-result/resources/resource') do |e|
    if e.attributes["resource_agent"] && e.attributes["resource_agent"].index('stonith:') == 0
      get_fence_devices && resource_list.push(Resource.new(e))
    else
      !get_fence_devices && resource_list.push(Resource.new(e))
    end
  end
  doc.elements.each('/crm_mon/resources/group/resource | /pacemaker-result/resources/group/resource') do |e|
    if e.attributes["resource_agent"] && e.attributes["resource_agent"].index('stonith:') == 0
      get_fence_devices && resource_list.push(Resource.new(e,e.parent.attributes["id"]))
    else
      !get_fence_devices && resource_list.push(Resource.new(e,e.parent.attributes["id"]))
    end
  end
  doc.elements.each('/crm_mon/resources/clone/resource | /pacemaker-result/resources/clone/resource') do |e|
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
  doc.elements.each('/crm_mon/resources/clone/group/resource | /pacemaker-result/resources/clone/group/resource') do |e|
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

  doc.elements.each('/crm_mon/resources/group | /pacemaker-result/resources/group') do |e|
    group_list.push(e.attributes["id"])
  end

  resource_list = resource_list.select { |x| not x.orphaned }
  resource_list = resource_list.sort_by{|a| (a.group ? "1" : "0").to_s + a.group.to_s + "-" +  a.id}

  if get_all_options or get_operations
    stdout, stderror, retval = run_cmd(auth_user, CIBADMIN, "-Q", "-l")
    cib_output = stdout
    resources_inst_attr_map = {}
    resources_meta_attr_map = {}
    resources_operation_map = {}
    begin
      doc = REXML::Document.new(cib_output.join("\n"))
      if get_all_options
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
      end

      if get_operations
        doc.elements.each('//lrm_rsc_op') { |rsc_op|
          resources_operation_map[rsc_op.parent.attributes['id']] ||= []
          resources_operation_map[rsc_op.parent.attributes['id']] << (
            ResourceOperation.new(rsc_op)
          )
        }
        resource_list.each {|r|
          if resources_operation_map[r.id]
            r.operations = resources_operation_map[r.id].sort { |a, b|
              a.call_id <=> b.call_id
            }
          end
        }
      end
    rescue REXML::ParseException
      $logger.info("ERROR: Parse Exception parsing cibadmin -Q")
    end
  end

  [resource_list, group_list, 0]
end

def getAllConstraints(constraints_dom)
  constraints = {}
  doc = constraints_dom

  doc.elements.each() { |e|
    if e.name == 'rsc_location' and e.has_elements?()
      rule_export = RuleToExpression.new()
      e.elements.each('rule') { |rule|
        rule_info = {
          'rule_string' => rule_export.export(rule),
        }
        if e.attributes["rsc-pattern"]
          rule_info["rsc-pattern"] = e.attributes["rsc-pattern"]
        else
          rule_info["rsc"] = e.attributes["rsc"]
        end
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
  }
  return constraints
end

def getResourceAgents(auth_user)
  stdout, stderr, retval = run_cmd(
    auth_user, PCS, "--nodesc", "--", "resource", "list"
  )
  if retval != 0
    $logger.error("Error running 'pcs resource list --nodesc")
    $logger.error(stdout + stderr)
    return []
  end

  return stdout.map{|agent_name| agent_name.chomp}
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
    @role = get_normalized_role(e.attributes['role'])
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
    @operations = []
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
    return false if @stonith
    if meta_attr and meta_attr["target-role"] and meta_attr["target-role"][1] == "Stopped"
      return true
    else
      return false
    end
  end
end


def get_resource_agent_name_structure(agent_name)
  [
    # full_agent_name could be for example systemd:lvm2-pvscan@252:2
    # note that the second colon is not separator of provider and type
    /^(?<standard>systemd|service):(?<type>[^:@]+@.*)$/,
    /^(?<standard>[^:]+)(:(?<provider>[^:]+))?:(?<type>[^:]+)$/,
  ].each{|expression|
    match = expression.match(agent_name)
    if match
      provider = match.names.include?('provider') ? match[:provider] : nil
      class_provider = provider.nil? ? match[:standard] : "#{match[:standard]}:#{provider}"
      return {
        :full_name => agent_name,
        # TODO remove, this is only used by the old web UI
        :class_provider => class_provider,
        :class => match[:standard],
        :provider => provider,
        :type => match[:type],
      }
    end
  }
  return nil
end


class ResourceOperation
  attr_accessor :call_id, :crm_debug_origin, :crm_feature_set, :exec_time,
    :exit_reason, :id, :interval, :last_rc_change, :last_run, :on_node,
    :op_digest, :operation, :operation_key, :op_force_restart,
    :op_restart_digest, :op_status, :queue_time, :rc_code, :transition_key,
    :transition_magic
  def initialize(op_element)
    @call_id = op_element.attributes['call-id'].to_i
    @crm_debug_origin = op_element.attributes['crm-debug-origin']
    @crm_feature_set = op_element.attributes['crm_feature_set']
    @exec_time = op_element.attributes['exec-time'].to_i
    @exit_reason = op_element.attributes['exit-reason']
    @id = op_element.attributes['id']
    @interval = op_element.attributes['interval'].to_i
    @last_rc_change = op_element.attributes['last-rc-change'].to_i
    @last_run = op_element.attributes['last-run'].to_i
    @on_node = op_element.attributes['on_node']
    @op_digest = op_element.attributes['op-digest']
    @operation_key = op_element.attributes['operation_key']
    @operation = op_element.attributes['operation']
    @op_force_restart = op_element.attributes['op-force-restart']
    @op_restart_digest = op_element.attributes['op-restart-digest']
    @op_status = op_element.attributes['op-status'].to_i
    @queue_time = op_element.attributes['queue-time'].to_i
    @rc_code = op_element.attributes['rc-code'].to_i
    @transition_key = op_element.attributes['transition-key']
    @transition_magic = op_element.attributes['transition-magic']

    if not @on_node
      elem = op_element.parent
      while elem
        if elem.name == 'node_state'
          @on_node = elem.attributes['uname']
          break
        end
        elem = elem.parent
      end
    end
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
