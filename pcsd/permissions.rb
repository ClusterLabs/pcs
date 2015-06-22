module Permissions

  TYPE_USER = 'user'
  TYPE_GROUP = 'group'

  READ = 'read'
  WRITE = 'write'
  GRANT = 'grant'
  FULL = 'full'

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
      if @allow_list.include?(FULL)
        return true
      elsif @allow_list.include?(action)
        return true
      elsif READ == action and allows?(WRITE)
        return true
      end
      return false
    end

    def merge!(other)
      @allow_list = (@allow_list + other.allow_list).uniq
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

    def allows?(username, groups, action)
      $logger.debug(
        "permission check action=#{action} username=#{username} groups=#{groups}"
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
