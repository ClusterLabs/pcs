require 'orderedhash'

module Permissions

  TYPE_USER = 'user'
  TYPE_GROUP = 'group'

  READ = 'read'
  WRITE = 'write'
  GRANT = 'grant'
  FULL = 'full'

  def self.get_user_types()
    return [
      {
        'code' => TYPE_USER,
        'label' => 'User',
        'description' => '',
      },
      {
        'code' => TYPE_GROUP,
        'label' => 'Group',
        'description' => '',
      }
    ]
  end

  def self.get_permission_types()
    return [
      {
        'code' => READ,
        'label' => 'Read',
        'description' => 'Allows to view cluster settings',
      },
      {
        'code' => WRITE,
        'label' => 'Write',
        'description' => 'Allows to modify cluster settings except permissions and ACLs',
      },
      {
        'code' => GRANT,
        'label' => 'Grant',
        'description' => 'Allows to modify cluster permissions and ACLs',
      },
      {
        'code' => FULL,
        'label' => 'Full',
        'description' => ('Allows unrestricted access to a cluster including '\
          + 'adding and removing nodes and access to keys and certificates'),
      }
    ]
  end

  def self.is_user_type(type)
    return [TYPE_USER, TYPE_GROUP].include?(type)
  end

  def self.is_permission_type(permission)
    return [READ, WRITE, GRANT, FULL].include?(permission)
  end

  def self.permissions_dependencies()
    return {
      'also_allows' => {
        WRITE => [READ],
        FULL => [READ, WRITE, GRANT],
      },
    }
  end

  class EntityPermissions
    attr_reader :type, :name, :allow_list

    def initialize(type, name, allow_list)
      # possibility to add deny_list
      @type = type
      @name = name
      @allow_list = allow_list.uniq
    end

    def applies_to(type, name)
      return (type == @type and name == @name)
    end

    def allows?(action)
      # - possibility to extend to more elaborate evaluation
      #   e.g. "read" allows both "read_nodes" and "read_resources"
      # - possibility to add deny_list
      if @allow_list.include?(action)
        return true
      else
        deps = Permissions.permissions_dependencies()
        deps['also_allows'].each { |new_action, also_allows|
          if also_allows.include?(action) and @allow_list.include?(new_action)
            return true
          end
        }
      end
      return false
    end

    def merge!(other)
      @allow_list = (@allow_list + other.allow_list).uniq
    end

    def to_hash()
      perm_hash = OrderedHash.new
      perm_hash['type'] = @type
      perm_hash['name'] = @name
      perm_hash['allow'] = @allow_list.uniq.sort
      return perm_hash
    end
  end

  class PermissionsSet
    def initialize(entity_permissions_list)
      @permissions = {
        TYPE_USER => {},
        TYPE_GROUP => {},
      }
      entity_permissions_list.each{ |perm|
        if not @permissions.key?(perm.type)
          @permissions[perm.type] = {}
        end
        if @permissions[perm.type][perm.name]
          @permissions[perm.type][perm.name].merge!(perm)
        else
          @permissions[perm.type][perm.name] = perm
        end
      }
    end

    def entity_permissions_list()
      return @permissions.values.collect { |perm| perm.values }.flatten
    end

    def to_hash()
      perm_set = []
      entity_permissions_list.each { |perm|
        perm_set << perm.to_hash()
      }
      return perm_set.sort { |a, b|
        a['type'] == b['type'] ? a['name'] <=> b['name'] : a['type'] <=> b['type']
      }
    end

    def allows?(username, groups, action)
      $logger.debug(
        "permission check action=#{action} username=#{username} groups=#{groups.join(' ')}"
      )

      if ::SUPERUSER == username
        $logger.debug('permission granted for superuser')
        return true
      end

      if @permissions[TYPE_USER].key?(username)
        if @permissions[TYPE_USER][username].allows?(action)
          $logger.debug("permission granted for user #{username}")
          return true
        end
      end

      groups.each { |group|
        if (
          @permissions[TYPE_GROUP].key?(group)\
          and\
          @permissions[TYPE_GROUP][group].allows?(action)
        )
          $logger.debug("permission granted for group #{group}")
          return true
        end
      }

      $logger.debug('permission denied')
      return false
    end
  end

end
