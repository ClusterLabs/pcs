require 'resource.rb'
require 'pcs.rb'

module ClusterEntity

  def self.get_rsc_status(crm_dom)
    unless crm_dom
      return {}
    end
    status = {}
    crm_dom.elements.each('/crm_mon/resources//resource') { |e|
      rsc_id = e.attributes['id'].split(':')[0]
      status[rsc_id] ||= []
      status[rsc_id] << ClusterEntity::CRMResourceStatus.new(e)
    }
    return status
  end

  def self.get_resources_operations(cib_dom)
    unless cib_dom
      return {}
    end
    operations = {}
    cib_dom.elements.each(
      '/cib/status/node_state/lrm/lrm_resources/lrm_resource/lrm_rsc_op'
    ) { |e|
      rsc_id = e.parent.attributes['id'].split(':')[0]
      operations[rsc_id] ||= []
      operations[rsc_id] << ClusterEntity::ResourceOperation.new(e)
    }
    return operations
  end

  def self.obj_to_hash(obj, variables=nil)
    unless variables
      variables = obj.instance_variables
    end
    hash = {}
    variables.each do |var|
      hash[var.to_s[1..-1].to_sym] = obj.instance_variable_get var if obj.instance_variable_defined? var
    end
    hash
  end

  def self.get_meta_attr_version1(obj)
    meta_attr = []
    obj.meta_attr.each { |pair|
      meta_attr << {
        :key => pair.name,
        :value => pair.value,
        :id => pair.id,
        :parent => obj.id
      }
    }
    return meta_attr
  end

  def self.merge_meta_attr_version1(meta1, meta2)
    to_add = []
    meta2_keys = meta2.map { |x| x[:key]}
    meta1.each { |m1|
      unless meta2_keys.include? m1[:key]
        to_add << m1
      end
    }
    return meta2 + to_add
  end

  def self.get_meta_attr_from_status_v1(resource_id, meta_attr)
    new_ma = ClusterEntity::NvSet.new
    meta_attr.each { |v|
      if v[:parent] == resource_id
        new_ma << ClusterEntity::NvPair.new(v[:id], v[:key], v[:value])
      end
    }
    return new_ma
  end

  def self.get_primitives_from_status_v1(resource_list)
    primitives = {}
    resource_list.each { |resource|
      unless primitives.include?(resource[:id].to_sym)
        p = ClusterEntity::Primitive.new
        p.id = resource[:id]
        p.agentname = resource[:agentname]
        p.stonith = resource[:stonith]
        if p.stonith
          p._class = 'stonith'
          p.type = p.agentname.split(':', 2)[1]
        else
          s =  p.agentname.split('::', 2)
          p._class = s[0]
          s = s[1].split(':', 2)
          p.provider = s[0]
          p.type = s[1]
        end

        p.meta_attr = ClusterEntity::get_meta_attr_from_status_v1(
          p.id,
          resource[:meta_attr]
        )

        resource[:instance_attr].each { |k, v|
          p.instance_attr << ClusterEntity::NvPair.new(nil, k, v)
        }

        primitives[p.id.to_sym] = [
          p,
          {
            :group => resource[:group],
            :clone => resource[:clone_id],
            :master => resource[:ms_id],
            :meta_attr => resource[:meta_attr]
          }
        ]
      end

      primitive_struct = primitives[resource[:id].to_sym]
      primitive = primitive_struct[0]
      status = ClusterEntity::CRMResourceStatus.new
      status.id = primitive.id
      status.resource_agent = primitive.agentname
      status.managed = true
      status.failed = resource[:failed]
      status.role = nil
      status.active = resource[:active]
      status.orphaned = resource[:orphaned]
      status.failure_ignored = false
      status.nodes_running_on = resource[:nodes].length
      status.pending = nil
      if status.nodes_running_on > 0
        node = {
          :id => nil,
          :name => resource[:nodes][0],
          :cached => false
        }
      else
        node = nil
      end
      status.node = node
      primitive.crm_status << status
    }
    primitives.each {|_, resource|
      resource[0].update_status
    }
    return primitives
  end

  def self.make_resources_tree(primitives)
    not_primitives = {}
    tree = []
    primitives.each { |_, primitive_struct|
      p = primitive_struct[0]
      data = primitive_struct[1]
      unless data[:group] or data[:clone] or data[:master]
        tree << p
        next
      end
      group = nil
      if data[:group]
        if data[:clone] or data[:master]
          group_id = data[:group].split('/', 2)[1]
        else
          group_id = data[:group]
        end
        if not_primitives.include?(group_id.to_sym)
          group = not_primitives[group_id.to_sym]
        else
          group = ClusterEntity::Group.new
          group.id = group_id
          group.meta_attr = ClusterEntity::get_meta_attr_from_status_v1(
            group.id,
            data[:meta_attr]
          )
          not_primitives[group_id.to_sym] = group
          unless data[:clone] or data[:master]
            tree << group
          end
        end
        p.parent = group
        group.members << p
      end
      if data[:clone] or data[:master]
        if data[:group]
          mi_id = data[:group].split('/', 2)[0]
        else
          mi_id = (data[:clone] or data[:master])
        end
        unless not_primitives.include?(mi_id.to_sym)
          if data[:clone]
            mi =  ClusterEntity::Clone.new
          else
            mi = ClusterEntity::MasterSlave.new
            mi.masters_unknown = true
          end
          mi.id = mi_id
          mi.meta_attr = ClusterEntity::get_meta_attr_from_status_v1(
            mi_id,
            data[:meta_attr]
          )
          if group
            group.parent = mi
            mi.member = group
          else
            p.parent = mi
            mi.member = p
          end
          not_primitives[mi_id.to_sym] = mi
          tree << mi
        end
      end
    }
    tree.each {|resource|
      resource.update_status
    }
    return tree
  end

  class JSONable
    def to_status(version='1')
      ClusterEntity::obj_to_hash(self)
    end
    def to_json(version='1')
      JSON.generate(to_status(version))
    end
  end

  class NvPair < JSONable
    attr_accessor :id, :name, :value

    def initialize(id, name, value=nil)
      @id = id
      @name = name
      @value = value
    end

    def self.from_dom(nvpair_dom_element)
      return NvPair.new(
        nvpair_dom_element.attributes['id'],
        nvpair_dom_element.attributes['name'],
        nvpair_dom_element.attributes['value']
      )
    end
  end

  class NvSet < JSONable
    include Enumerable

    def initialize
      @list = []
    end

    def include?(name)
      @list.each { |pair|
        return true if pair.name == name
      }
      return false
    end

    def [](name)
      @list.each { |pair|
        return pair if pair.name == name
      }
      return nil
    end

    def <<(pair)
      unless pair.instance_of?(ClusterEntity::NvPair)
        raise ArgumentError.new('Argument has to be NvPair')
      end
      p = self[pair.name]
      if p
        @list.delete(p)
      end
      @list << pair
      return self
    end

    def each(&block)
      return enum_for(__method__) if block.nil?
      @list.each do |ob|
        block.call(ob)
      end
    end

    def empty?
      @list.empty?
    end

    def length
      @list.length
    end

    def delete(name)
      @list.delete(self[name])
    end

    def to_status(version='1')
      status = []
      @list.each { |pair|
        status << pair.to_status(version)
      }
      return status
    end
  end

  class ResourceStatus
    include Comparable
    attr_reader :status

    STATUSES = {
      :running => {
        :val => 1,
        :str => 'running'
      },
      :partially_running => {
        :val => 2,
        :str => 'partially running'
      },
      :disabled => {
        :val => 3,
        :str => 'disabled'
      },
      :failed => {
        :val => 4,
        :str => 'failed'
      },
      :blocked => {
        :val => 5,
        :str => 'blocked'
      },
      :unknown => {
        :val => 6,
        :str => 'unknown'
      },
    }

    def initialize(status=:unknown)
      @status = STATUSES.include?(status) ? status : :unknown
    end

    def to_s
      STATUSES[@status][:str]
    end

    def <=>(other)
      STATUSES[@status][:val] <=> STATUSES[other.status][:val]
    end
  end


  class Resource < JSONable
    attr_accessor :parent, :meta_attr, :id, :error_list, :warning_list,
                  :status
    attr_reader :class_type

    def initialize(resource_cib_element=nil, crm_dom=nil, parent=nil)
      @class_type = nil
      @parent = parent
      @meta_attr = ClusterEntity::NvSet.new
      @id = nil
      @error_list = []
      @warning_list = []
      @status = ClusterEntity::ResourceStatus.new
      element_names = {
        'ClusterEntity::Primitive'.to_sym => 'primitive',
        'ClusterEntity::Group'.to_sym => 'group',
        'ClusterEntity::Clone'.to_sym => 'clone',
        'ClusterEntity::MasterSlave'.to_sym => 'master'
      }
      if (resource_cib_element and
        resource_cib_element.name == element_names[self.class.name.to_sym]
      )
        @id = resource_cib_element.attributes['id']
        resource_cib_element.elements.each('meta_attributes/nvpair') { |e|
          @meta_attr << ClusterEntity::NvPair.from_dom(e)
        }
      end
    end

    def disabled?
      return true if @parent and @parent.disabled?
      return !!(@meta_attr['target-role'] and
        @meta_attr['target-role'].value.downcase == 'stopped'
      )
    end

    def get_group
      if parent.instance_of?(ClusterEntity::Group)
        return parent.id
      end
      return nil
    end

    def get_clone
      if parent.instance_of?(ClusterEntity::Clone)
        return parent.id
      elsif (parent.instance_of?(ClusterEntity::Group) and
        parent.parent.instance_of?(ClusterEntity::Clone)
      )
        return parent.parent.id
      end
      return nil
    end

    def get_master
      if parent.instance_of?(ClusterEntity::MasterSlave)
        return parent.id
      elsif (parent.instance_of?(ClusterEntity::Group) and
        parent.parent.instance_of?(ClusterEntity::MasterSlave)
      )
        return parent.parent.id
      end
      return nil
    end

    def to_status(version='1')
      if version == '2'
        status = ClusterEntity::obj_to_hash(
          self,
          [:@id, :@error_list, :@warning_list, :@class_type]
        )
        status.update(
          {
            :status => @status.to_s,
            :meta_attr => @meta_attr.to_status,
            :parent_id => @parent ? @parent.id : nil,
            :disabled => disabled?
          }
        )
      else
        status = ClusterEntity::obj_to_hash(self, [:@id])
      end
      return status
    end

    def get_map
      return {@id.to_sym => self}
    end
  end


  class CRMResourceStatus < JSONable
    attr_accessor :id, :resource_agent, :managed, :failed, :role, :active,
                  :orphaned, :failure_ignored, :nodes_running_on, :pending,
                  :node

    def initialize(resource_crm_element=nil)
      @id = nil
      @resource_agent = nil
      @managed = false
      @failed = false
      @role = nil
      @active = false
      @orphaned = false
      @failure_ignored = false
      @nodes_running_on = 0
      @pending = nil
      @node = nil

      if resource_crm_element and resource_crm_element.name == 'resource'
        crm = resource_crm_element
        @id = crm.attributes['id']
        @resource_agent = crm.attributes['resource_agent']
        @managed = crm.attributes['managed'] == 'true'
        @failed = crm.attributes['failed'] == 'true'
        @role = crm.attributes['role']
        @active = crm.attributes['active'] == 'true'
        @orphaned = crm.attributes['orphaned'] == 'true'
        @failure_ignored = crm.attributes['failure_ignored'] == 'true'
        @nodes_running_on = crm.attributes['nodes_running_on'].to_i
        @pending = crm.attributes['pending']
        node = crm.elements['node']
        if node
          @node = {
            :name => node.attributes['name'],
            :id => node.attributes['id'],
            :cached => node.attributes['cached'] == 'true'
          }
        end
      end
    end
  end


  class Primitive < Resource
    attr_accessor :agentname, :_class, :provider, :type, :stonith,
                  :instance_attr, :crm_status, :operations, :utilization

    def initialize(primitive_cib_element=nil, rsc_status=nil, parent=nil,
        operations=nil)
      super(primitive_cib_element, nil, parent)
      @class_type = 'primitive'
      @agentname = nil
      @_class = nil
      @provider = nil
      @type = nil
      @stonith = false
      @instance_attr = ClusterEntity::NvSet.new
      @crm_status = []
      @operations = []
      @utilization = ClusterEntity::NvSet.new
      cib = primitive_cib_element
      if primitive_cib_element and primitive_cib_element.name == 'primitive'
        @_class = cib.attributes['class']
        @provider = cib.attributes['provider']
        @type = cib.attributes['type']
        @agentname = ("#{@_class}%s:#{@type}" % [
          @provider ? "::#{@provider}" : ''
        ]) if @_class and @type

        cib.elements.each('instance_attributes/nvpair') { |e|
          @instance_attr << ClusterEntity::NvPair.from_dom(e)
        }
        cib.elements.each('utilization/nvpair') { |e|
          @utilization << ClusterEntity::NvPair.from_dom(e)
        }
        @stonith = @_class == 'stonith'
        if @id and rsc_status
          @crm_status = rsc_status[@id] || []
        end

        @status = get_status
        load_operations(operations)
      end
    end

    def update_status
      @status = get_status
    end

    def get_status
      running = 0
      failed = 0
      @crm_status.each do |s|
        if s.active
          running += 1
        elsif s.failed
          failed += 1
        end
      end

      if disabled?
        status = ClusterEntity::ResourceStatus.new(:disabled)
      elsif running > 0
        status = ClusterEntity::ResourceStatus.new(:running)
      elsif failed > 0 or @error_list.length > 0
        status = ClusterEntity::ResourceStatus.new(:failed)
      else
        status = ClusterEntity::ResourceStatus.new(:blocked)
      end

      return status
    end

    def load_operations(operations)
      @operations = []
      unless operations and @id and operations[@id]
        return
      end

      failed_ops = []
      message_list = []
      operations[@id].each { |o|
        @operations << o
        if o.rc_code != 0
          # 7 == OCF_NOT_RUNNING == The resource is safely stopped.
          next if o.operation == 'monitor' and o.rc_code == 7
          # 8 == OCF_RUNNING_MASTER == The resource is running in master mode.
          next if 8 == o.rc_code
          failed_ops << o
          message = "Failed to #{o.operation} #{@id}"
          message += " on #{Time.at(o.last_rc_change).asctime}"
          message += " on node #{o.on_node}" if o.on_node
          message += ": #{o.exit_reason}" if o.exit_reason
          message_list << {
            :message => message
          }
        end
      }

      status = get_status
      if (failed_ops.length > 0 and
        status == ClusterEntity::ResourceStatus.new(:blocked)
      )
        @status = ClusterEntity::ResourceStatus.new(:failed)
      end

      if @status == ClusterEntity::ResourceStatus.new(:failed)
        @error_list += message_list
      else
        @warning_list += message_list
      end
    end

    def disabled?
      if @stonith
        return false
      end
      return super
    end

    def to_status(version='1')
      hash = super(version)
      if version == '2'
        hash.update(
          ClusterEntity::obj_to_hash(
            self,
            [:@agentname, :@provider, :@type, :@stonith]
          )
        )
        hash[:utilization] = @utilization.to_status
        hash[:instance_attr] = @instance_attr.to_status
        hash[:class] = @_class

        rsc_status = []
        @crm_status.each { |s|
          rsc_status << s.to_status(version)
        }
        hash[:crm_status] = rsc_status

        operations = []
        @operations.each { |o|
          operations << o.to_status(version)
        }
        hash[:operations] = operations
      else
        instance_attr = {}
        @instance_attr.each { |v|
          instance_attr[v.name.to_sym] = v.value
        }
        hash.update(
          {
            :agentname => @agentname,
            :group => nil,
            :clone => false,
            :clone_id => nil,
            :ms => false,
            :ms_id => nil,
            :operations => [],
            :meta_attr => ClusterEntity::get_meta_attr_version1(self),
            :instance_attr => instance_attr,
            :options => instance_attr,
            :stonith => @stonith,
            :disabled => disabled?,
            :active => false,
            :failed => false,
            :orphaned => false,
            :nodes => [],
          }
        )
        if @crm_status and @crm_status.length >= 1
          rsc = hash
          hash = []
          @crm_status.each do |s|
            actual = {}
            actual.update(rsc)
            actual.update(
              ClusterEntity::obj_to_hash(s, [:@active, :@failed, :@orphaned])
            )
            actual[:nodes] = (s.node) ? [s.node[:name]] : []
            hash << actual
          end
        else
          hash.update(
            ClusterEntity::obj_to_hash(
              CRMResourceStatus.new,
              [:@active, :@failed, :@orphaned]
            )
          )
          hash = [hash]
        end
      end
      return hash
    end
  end


  class Group < Resource
    attr_accessor :members

    def initialize(
      group_cib_element=nil, rsc_status=nil, parent=nil, operations=nil
    )
      super(group_cib_element, nil, parent)
      @class_type = 'group'
      @members = []
      if group_cib_element and group_cib_element.name == 'group'
        @status = ClusterEntity::ResourceStatus.new(:running)
        group_cib_element.elements.each('primitive') { |e|
          p = Primitive.new(e, rsc_status, self, operations)
          members << p
        }
        update_status
      end
    end

    def update_status
      @status = ClusterEntity::ResourceStatus.new(:running)
      first = true
      @members.each { |p|
        p.update_status
        if first
          first = false
          next
        end
        if (
          p.status == ClusterEntity::ResourceStatus.new(:disabled) or
          p.status == ClusterEntity::ResourceStatus.new(:blocked) or
          p.status == ClusterEntity::ResourceStatus.new(:failed)
        )
          @status = ClusterEntity::ResourceStatus.new(:partially_running)
        end
      }
      if (@members and @members.length > 0 and
        (ClusterEntity::ResourceStatus.new(:running) != @members[0].status and
        ClusterEntity::ResourceStatus.new(:unknown) != @members[0].status)
      )
        @status = @members[0].status
      end
      if disabled?
        @status = ClusterEntity::ResourceStatus.new(:disabled)
      end
    end

    def to_status(version='1')
      if version == '2'
        hash = super(version)
        members = []
        @members.each do |m|
          members << m.to_status(version)
        end
        hash[:members] = members
      else
        hash = []
        meta_attr = ClusterEntity::get_meta_attr_version1(self)
        @members.each do |m|
          hash.concat(m.to_status(version))
        end
        group_id = (@parent) ? "#{@parent.id}/#{@id}" : @id
        hash.each do |m|
          m[:group] = group_id
          m[:meta_attr] = ClusterEntity::merge_meta_attr_version1(
            m[:meta_attr],
            meta_attr
          )
        end
      end
      return hash
    end

    def get_map
      map = super
      @members.each do |m|
        map.update(m.get_map)
      end
      return map
    end
  end


  class MultiInstance < Resource
    attr_accessor :member, :unique, :managed, :failed, :failure_ignored

    def initialize(resource_cib_element=nil, crm_dom=nil, rsc_status=nil,
                   parent=nil, operations=nil)
      super(resource_cib_element, nil, parent)
      @member = nil
      @multi_state = false
      @unique = false
      @managed = false
      @failed = false
      @failure_ignored = false
      element_names = {
        'ClusterEntity::Clone'.to_sym => 'clone',
        'ClusterEntity::MasterSlave'.to_sym => 'master'
      }
      if (resource_cib_element and
        resource_cib_element.name == element_names[self.class.name.to_sym]
      )
        member = resource_cib_element.elements['group | primitive']
        if member and member.name == 'group'
          @member = Group.new(member, rsc_status, self, operations)
        elsif member and member.name == 'primitive'
          @member = Primitive.new(member, rsc_status, self, operations)
        end
        update_status
        if crm_dom
          status = crm_dom.elements["/crm_mon/resources//clone[@id='#{@id}']"]
          if status
            @unique = status.attributes['unique'] == 'true'
            @managed = status.attributes['managed'] == 'true'
            @failed = status.attributes['failed'] == 'true'
            @failure_ignored = status.attributes['failure_ignored'] == 'true'
          end
        end
      end
    end

    def update_status
      if @member
        @member.update_status
        @status = @member.status
      end
      if disabled?
        @status = ClusterEntity::ResourceStatus.new(:disabled)
      end
    end

    def to_status(version='1')
      if version == '2'
        hash = super(version)
        hash[:member] = @member.to_status(version)
        return hash
      else
        return @member ? @member.to_status(version) : []
      end
    end

    def get_map
      map = super
      map.update(@member.get_map)
      return map
    end
  end


  class Clone < MultiInstance

    def initialize(
      resource_cib_element=nil, crm_dom=nil, rsc_status=nil, parent=nil,
      operations=nil
    )
      super(resource_cib_element, crm_dom, rsc_status, parent, operations)
      @class_type = 'clone'
    end

    def to_status(version='1')
      member = super(version)
      if version == '2'
        return member
      else
        meta_attr = []
        unless @member.instance_of?(Group)
          meta_attr = ClusterEntity::get_meta_attr_version1(self)
        end
        clone_id = @member.instance_of?(Group) ? @member.id : @id
        member.each do |m|
          m[:clone] = true
          m[:clone_id] = clone_id
          m[:meta_attr] = ClusterEntity::merge_meta_attr_version1(
            m[:meta_attr],
            meta_attr
          )
        end
        return member
      end
    end
  end


  class MasterSlave < MultiInstance
    attr_accessor :masters, :slaves, :masters_unknown

    def initialize(master_cib_element=nil, crm_dom=nil, rsc_status=nil, parent=nil, operations=nil)
      super(master_cib_element, crm_dom, rsc_status, parent, operations)
      @masters_unknown = false
      @class_type = 'master'
      @masters = []
      @slaves = []
      update_status
      if @member
        if @member.instance_of?(Primitive)
          primitive_list = [@member]
        else
          primitive_list = @member.members
        end
        @masters, @slaves = get_masters_slaves(primitive_list)
        if (@masters.empty? and !@masters_unknown and
          @status != ClusterEntity::ResourceStatus.new(:disabled)
        )
          @warning_list << {
            :message => 'Resource is master/slave but has not been promoted '\
              + 'to master on any node.',
            :type => 'no_master'
          }
        end
      end
    end

    def to_status(version='1')
      member = super(version)
      if version == '2'
        return member
      else
        meta_attr = []
        unless @member.instance_of?(Group)
          meta_attr = ClusterEntity::get_meta_attr_version1(self)
        end
        ms_id = @member.instance_of?(Group) ? @member.id : @id
        member.each do |m|
          m[:ms] = true
          m[:ms_id] = ms_id
          m[:meta_attr] = ClusterEntity::merge_meta_attr_version1(
            m[:meta_attr],
            meta_attr
          )
        end
        return member
      end
    end

    def update_status
      if @member
        @member.update_status
        @status = @member.status
        if @member.instance_of?(Primitive)
          primitive_list = [@member]
        else
          primitive_list = @member.members
        end
        @masters, @slaves = get_masters_slaves(primitive_list)
        if (@masters.empty? and !@masters_unknown and
          @member.status == ClusterEntity::ResourceStatus.new(:running)
        )
          @status = ClusterEntity::ResourceStatus.new(:partially_running)
        end
      end
      if disabled?
        @status = ClusterEntity::ResourceStatus.new(:disabled)
      end
    end

    private
    def get_masters_slaves(primitive_list)
      masters = []
      slaves = []
      primitive_list.each { |primitive|
        if primitive.instance_of?(ClusterEntity::Primitive)
          primitive.crm_status.each { |stat|
            if stat.role == 'Master'
              if stat.node
                masters << stat.node[:name]
              end
            else
              if stat.node
                slaves << stat.node[:name]
              end
            end
          }
        end
      }
      return [masters, slaves]
    end
  end


  class ResourceOperation < JSONable
    attr_accessor :call_id, :crm_debug_origin, :crm_feature_set, :exec_time,
                  :exit_reason, :id, :interval, :last_rc_change, :last_run,
                  :on_node, :op_digest, :operation, :operation_key,
                  :op_force_restart, :op_restart_digest, :op_status,
                  :queue_time, :rc_code, :transition_key, :transition_magic
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

      unless @on_node
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


  class Node < JSONable
    attr_accessor :id, :error_list, :warning_list, :status, :quorum, :uptime,
                  :name, :corosync, :pacemaker, :cman, :corosync_enabled,
                  :pacemaker_enabled, :pcsd_enabled, :services, :sbd_config

    def initialize
      @id = nil
      @error_list = []
      @warning_list = []
      @status = 'unknown'
      @quorum = nil
      @uptime = 'unknown'
      @name = nil
      @services = {}
      [
        :pacemaker, :pacemaker_remote, :corosync, :pcsd, :cman, :sbd
      ].each do |service|
        @services[service] = {
          :installed => nil,
          :running => nil,
          :enabled => nil
        }
      end
      @corosync = false
      @pacemaker = false
      @cman = false
      @corosync_enabled = false
      @pacemaker_enabled = false
      @pcsd_enabled = false
      @sbd_config = nil
    end

    def self.load_current_node(crm_dom=nil)
      node = ClusterEntity::Node.new
      node.services.each do |service, info|
        info[:running] = is_service_running?(service.to_s)
        info[:enabled] = is_service_enabled?(service.to_s)
        info[:installed] = is_service_installed?(service.to_s)
      end
      node.corosync = node.services[:corosync][:running]
      node.corosync_enabled = node.services[:corosync][:enabled]
      node.pacemaker = node.services[:pacemaker][:running]
      node.pacemaker_enabled = node.services[:pacemaker][:enabled]
      node.cman = node.services[:cman][:running]
      node.pcsd_enabled = node.services[:pcsd][:enabled]

      node_online = (node.corosync and node.pacemaker)
      node.status =  node_online ? 'online' : 'offline'

      node.uptime = get_node_uptime
      node.id = get_local_node_id

      if node_online and crm_dom
        node_el = crm_dom.elements["//node[@id='#{node.id}']"]
        if node_el and node_el.attributes['standby'] == 'true'
          node.status = 'standby'
        else
          node.status = 'online'
        end
        node.quorum = !!crm_dom.elements['//current_dc[@with_quorum="true"]']
      else
        node.status = 'offline'
      end
      node.sbd_config = get_parsed_local_sbd_config()
      return node
    end
  end
end
