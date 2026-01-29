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
