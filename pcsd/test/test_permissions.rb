require 'test/unit'

require 'pcsd_test_utils.rb'
require 'permissions.rb'

class TestPermissions < Test::Unit::TestCase

  def test_is_user_type()
    assert_equal(true, Permissions::is_user_type(Permissions::TYPE_USER))
    assert_equal(true, Permissions::is_user_type(Permissions::TYPE_GROUP))
    assert_equal(false, Permissions::is_user_type(''))
    assert_equal(false, Permissions::is_user_type('nonsense'))
  end

  def test_is_permission_type()
    assert_equal(true, Permissions::is_permission_type(Permissions::READ))
    assert_equal(true, Permissions::is_permission_type(Permissions::WRITE))
    assert_equal(true, Permissions::is_permission_type(Permissions::GRANT))
    assert_equal(true, Permissions::is_permission_type(Permissions::FULL))
    assert_equal(false, Permissions::is_permission_type(''))
    assert_equal(false, Permissions::is_permission_type('nonsense'))
  end
end


class TestEntityPermissions < Test::Unit::TestCase

  def setup
    $logger = MockLogger.new
  end

  def test_applies_to()
    ep = Permissions::EntityPermissions.new(Permissions::TYPE_USER, 'user', [])
    assert_equal(true, ep.applies_to(Permissions::TYPE_USER, 'user'))
    assert_equal(false, ep.applies_to(Permissions::TYPE_USER, 'group'))
    assert_equal(false, ep.applies_to(Permissions::TYPE_GROUP, 'user'))
    assert_equal(false, ep.applies_to(Permissions::TYPE_GROUP, 'group'))

    ep = Permissions::EntityPermissions.new(Permissions::TYPE_GROUP, 'group', [])
    assert_equal(false, ep.applies_to(Permissions::TYPE_USER, 'user'))
    assert_equal(false, ep.applies_to(Permissions::TYPE_USER, 'user'))
    assert_equal(false, ep.applies_to(Permissions::TYPE_GROUP, 'user'))
    assert_equal(true, ep.applies_to(Permissions::TYPE_GROUP, 'group'))
  end

  def test_allows()
    ep = Permissions::EntityPermissions.new(Permissions::TYPE_USER, 'user', [])
    assert_equal(false, ep.allows?(Permissions::FULL))
    assert_equal(false, ep.allows?(Permissions::GRANT))
    assert_equal(false, ep.allows?(Permissions::WRITE))
    assert_equal(false, ep.allows?(Permissions::READ))

    ep = Permissions::EntityPermissions.new(Permissions::TYPE_USER, 'user', [
      Permissions::READ
    ])
    assert_equal(false, ep.allows?(Permissions::FULL))
    assert_equal(false, ep.allows?(Permissions::GRANT))
    assert_equal(false, ep.allows?(Permissions::WRITE))
    assert_equal(true, ep.allows?(Permissions::READ))

    ep = Permissions::EntityPermissions.new(Permissions::TYPE_USER, 'user', [
      Permissions::WRITE
    ])
    assert_equal(false, ep.allows?(Permissions::FULL))
    assert_equal(false, ep.allows?(Permissions::GRANT))
    assert_equal(true, ep.allows?(Permissions::WRITE))
    assert_equal(true, ep.allows?(Permissions::READ))

    ep = Permissions::EntityPermissions.new(Permissions::TYPE_USER, 'user', [
      Permissions::GRANT
    ])
    assert_equal(false, ep.allows?(Permissions::FULL))
    assert_equal(true, ep.allows?(Permissions::GRANT))
    assert_equal(false, ep.allows?(Permissions::WRITE))
    assert_equal(false, ep.allows?(Permissions::READ))

    ep = Permissions::EntityPermissions.new(Permissions::TYPE_USER, 'user', [
      Permissions::FULL
    ])
    assert_equal(true, ep.allows?(Permissions::FULL))
    assert_equal(true, ep.allows?(Permissions::GRANT))
    assert_equal(true, ep.allows?(Permissions::WRITE))
    assert_equal(true, ep.allows?(Permissions::READ))

    ep = Permissions::EntityPermissions.new(Permissions::TYPE_USER, 'user', [
      Permissions::READ, Permissions::WRITE
    ])
    assert_equal(false, ep.allows?(Permissions::FULL))
    assert_equal(false, ep.allows?(Permissions::GRANT))
    assert_equal(true, ep.allows?(Permissions::WRITE))
    assert_equal(true, ep.allows?(Permissions::READ))

    ep = Permissions::EntityPermissions.new(Permissions::TYPE_USER, 'user', [
      Permissions::READ, Permissions::WRITE, Permissions::GRANT
    ])
    assert_equal(false, ep.allows?(Permissions::FULL))
    assert_equal(true, ep.allows?(Permissions::GRANT))
    assert_equal(true, ep.allows?(Permissions::WRITE))
    assert_equal(true, ep.allows?(Permissions::READ))

    ep = Permissions::EntityPermissions.new(Permissions::TYPE_USER, 'user', [
      Permissions::READ, Permissions::WRITE, Permissions::GRANT, Permissions::FULL
    ])
    assert_equal(true, ep.allows?(Permissions::FULL))
    assert_equal(true, ep.allows?(Permissions::GRANT))
    assert_equal(true, ep.allows?(Permissions::WRITE))
    assert_equal(true, ep.allows?(Permissions::READ))
  end

  def test_merge!()
    ep = Permissions::EntityPermissions.new(Permissions::TYPE_USER, 'user', [
      Permissions::READ
    ])
    assert_equal(false, ep.allows?(Permissions::FULL))
    assert_equal(false, ep.allows?(Permissions::GRANT))
    assert_equal(false, ep.allows?(Permissions::WRITE))
    assert_equal(true, ep.allows?(Permissions::READ))

    ep.merge!(Permissions::EntityPermissions.new(Permissions::TYPE_USER, 'user', [
      Permissions::GRANT
    ]))
    assert_equal(false, ep.allows?(Permissions::FULL))
    assert_equal(true, ep.allows?(Permissions::GRANT))
    assert_equal(false, ep.allows?(Permissions::WRITE))
    assert_equal(true, ep.allows?(Permissions::READ))
  end

end


class TestPermissionsSet < Test::Unit::TestCase

  def setup
    $logger = MockLogger.new
  end

  def test_allows_empty
    perms = Permissions::PermissionsSet.new([])

    assert_equal(true, perms.allows?('hacluster', [], Permissions::FULL))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::GRANT))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::WRITE))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', [], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', [], Permissions::GRANT))
    assert_equal(false, perms.allows?('user1', [], Permissions::WRITE))
    assert_equal(false, perms.allows?('user1', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::GRANT))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::WRITE))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::READ))
  end

  def test_allows_user
    perms = Permissions::PermissionsSet.new([
      Permissions::EntityPermissions.new(
        Permissions::TYPE_USER, 'user1', []
      ),
    ])

    assert_equal(true, perms.allows?('hacluster', [], Permissions::FULL))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::GRANT))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::WRITE))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', [], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', [], Permissions::GRANT))
    assert_equal(false, perms.allows?('user1', [], Permissions::WRITE))
    assert_equal(false, perms.allows?('user1', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::GRANT))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::WRITE))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::READ))


    perms = Permissions::PermissionsSet.new([
      Permissions::EntityPermissions.new(
        Permissions::TYPE_USER, 'user1', [Permissions::WRITE]
      ),
    ])

    assert_equal(true, perms.allows?('hacluster', [], Permissions::FULL))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::GRANT))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::WRITE))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', [], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', [], Permissions::GRANT))
    assert_equal(true, perms.allows?('user1', [], Permissions::WRITE))
    assert_equal(true, perms.allows?('user1', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::GRANT))
    assert_equal(true, perms.allows?('user1', ['group1'], Permissions::WRITE))
    assert_equal(true, perms.allows?('user1', ['group1'], Permissions::READ))

    assert_equal(false, perms.allows?('user2', [], Permissions::FULL))
    assert_equal(false, perms.allows?('user2', [], Permissions::GRANT))
    assert_equal(false, perms.allows?('user2', [], Permissions::WRITE))
    assert_equal(false, perms.allows?('user2', [], Permissions::READ))

    assert_equal(false, perms.allows?('user2', ['group1'], Permissions::FULL))
    assert_equal(false, perms.allows?('user2', ['group1'], Permissions::GRANT))
    assert_equal(false, perms.allows?('user2', ['group1'], Permissions::WRITE))
    assert_equal(false, perms.allows?('user2', ['group1'], Permissions::READ))


    perms = Permissions::PermissionsSet.new([
      Permissions::EntityPermissions.new(
        Permissions::TYPE_USER, 'user1', [Permissions::WRITE]
      ),
      Permissions::EntityPermissions.new(
        Permissions::TYPE_USER, 'user2', [Permissions::GRANT]
      ),
    ])

    assert_equal(true, perms.allows?('hacluster', [], Permissions::FULL))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::GRANT))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::WRITE))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', [], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', [], Permissions::GRANT))
    assert_equal(true, perms.allows?('user1', [], Permissions::WRITE))
    assert_equal(true, perms.allows?('user1', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::GRANT))
    assert_equal(true, perms.allows?('user1', ['group1'], Permissions::WRITE))
    assert_equal(true, perms.allows?('user1', ['group1'], Permissions::READ))

    assert_equal(false, perms.allows?('user2', [], Permissions::FULL))
    assert_equal(true, perms.allows?('user2', [], Permissions::GRANT))
    assert_equal(false, perms.allows?('user2', [], Permissions::WRITE))
    assert_equal(false, perms.allows?('user2', [], Permissions::READ))

    assert_equal(false, perms.allows?('user2', ['group1'], Permissions::FULL))
    assert_equal(true, perms.allows?('user2', ['group1'], Permissions::GRANT))
    assert_equal(false, perms.allows?('user2', ['group1'], Permissions::WRITE))
    assert_equal(false, perms.allows?('user2', ['group1'], Permissions::READ))
  end

  def test_allows_group
    perms = Permissions::PermissionsSet.new([
      Permissions::EntityPermissions.new(
        Permissions::TYPE_GROUP, 'group1', []
      ),
    ])

    assert_equal(true, perms.allows?('hacluster', [], Permissions::FULL))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::GRANT))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::WRITE))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', [], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', [], Permissions::GRANT))
    assert_equal(false, perms.allows?('user1', [], Permissions::WRITE))
    assert_equal(false, perms.allows?('user1', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::GRANT))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::WRITE))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::READ))


    perms = Permissions::PermissionsSet.new([
      Permissions::EntityPermissions.new(
        Permissions::TYPE_GROUP, 'group1', [Permissions::WRITE]
      ),
    ])

    assert_equal(true, perms.allows?('hacluster', [], Permissions::FULL))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::GRANT))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::WRITE))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', [], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', [], Permissions::GRANT))
    assert_equal(false, perms.allows?('user1', [], Permissions::WRITE))
    assert_equal(false, perms.allows?('user1', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::GRANT))
    assert_equal(true, perms.allows?('user1', ['group1'], Permissions::WRITE))
    assert_equal(true, perms.allows?('user1', ['group1'], Permissions::READ))

    assert_equal(false, perms.allows?('user2', [], Permissions::FULL))
    assert_equal(false, perms.allows?('user2', [], Permissions::GRANT))
    assert_equal(false, perms.allows?('user2', [], Permissions::WRITE))
    assert_equal(false, perms.allows?('user2', [], Permissions::READ))

    assert_equal(false, perms.allows?('user2', ['group1'], Permissions::FULL))
    assert_equal(false, perms.allows?('user2', ['group1'], Permissions::GRANT))
    assert_equal(true, perms.allows?('user2', ['group1'], Permissions::WRITE))
    assert_equal(true, perms.allows?('user2', ['group1'], Permissions::READ))


    perms = Permissions::PermissionsSet.new([
      Permissions::EntityPermissions.new(
        Permissions::TYPE_GROUP, 'group1', [Permissions::WRITE]
      ),
      Permissions::EntityPermissions.new(
        Permissions::TYPE_GROUP, 'group2', [Permissions::GRANT]
      ),
    ])

    assert_equal(true, perms.allows?('hacluster', [], Permissions::FULL))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::GRANT))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::WRITE))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', [], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', [], Permissions::GRANT))
    assert_equal(false, perms.allows?('user1', [], Permissions::WRITE))
    assert_equal(false, perms.allows?('user1', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::GRANT))
    assert_equal(true, perms.allows?('user1', ['group1'], Permissions::WRITE))
    assert_equal(true, perms.allows?('user1', ['group1'], Permissions::READ))

    assert_equal(false, perms.allows?('user1', ['group2'], Permissions::FULL))
    assert_equal(true, perms.allows?('user1', ['group2'], Permissions::GRANT))
    assert_equal(false, perms.allows?('user1', ['group2'], Permissions::WRITE))
    assert_equal(false, perms.allows?('user1', ['group2'], Permissions::READ))

    assert_equal(false, perms.allows?('user1', ['group1', 'group2'], Permissions::FULL))
    assert_equal(true, perms.allows?('user1', ['group1', 'group2'], Permissions::GRANT))
    assert_equal(true, perms.allows?('user1', ['group1', 'group2'], Permissions::WRITE))
    assert_equal(true, perms.allows?('user1', ['group1', 'group2'], Permissions::READ))
  end

  def test_allows_user_group
    perms = Permissions::PermissionsSet.new([
      Permissions::EntityPermissions.new(
        Permissions::TYPE_USER, 'user1', []
      ),
      Permissions::EntityPermissions.new(
        Permissions::TYPE_GROUP, 'group1', []
      ),
    ])

    assert_equal(true, perms.allows?('hacluster', [], Permissions::FULL))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::GRANT))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::WRITE))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', [], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', [], Permissions::GRANT))
    assert_equal(false, perms.allows?('user1', [], Permissions::WRITE))
    assert_equal(false, perms.allows?('user1', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::FULL))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::GRANT))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::WRITE))
    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::READ))

    assert_equal(
      [
        ['debug', 'permission check action=full username=hacluster groups='],
        ['debug', 'permission granted for superuser'],
        ['debug', 'permission check action=grant username=hacluster groups='],
        ['debug', 'permission granted for superuser'],
        ['debug', 'permission check action=write username=hacluster groups='],
        ['debug', 'permission granted for superuser'],
        ['debug', 'permission check action=read username=hacluster groups='],
        ['debug', 'permission granted for superuser'],
        ['debug', 'permission check action=full username=user1 groups='],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=grant username=user1 groups='],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=write username=user1 groups='],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=read username=user1 groups='],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=full username=user1 groups=group1'],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=grant username=user1 groups=group1'],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=write username=user1 groups=group1'],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=read username=user1 groups=group1'],
        ['debug', 'permission denied'],
      ],
      $logger.log
    )
    $logger.clean

    perms = Permissions::PermissionsSet.new([
      Permissions::EntityPermissions.new(
        Permissions::TYPE_USER, 'user1', [Permissions::GRANT]
      ),
      Permissions::EntityPermissions.new(
        Permissions::TYPE_GROUP, 'group1', [Permissions::WRITE]
      ),
      Permissions::EntityPermissions.new(
        Permissions::TYPE_USER, 'user3', [Permissions::FULL]
      ),
      Permissions::EntityPermissions.new(
        Permissions::TYPE_GROUP, 'group3', [Permissions::FULL]
      ),
    ])

    assert_equal(true, perms.allows?('hacluster', [], Permissions::FULL))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::GRANT))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::WRITE))
    assert_equal(true, perms.allows?('hacluster', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', [], Permissions::FULL))
    assert_equal(true, perms.allows?('user1', [], Permissions::GRANT))
    assert_equal(false, perms.allows?('user1', [], Permissions::WRITE))
    assert_equal(false, perms.allows?('user1', [], Permissions::READ))

    assert_equal(false, perms.allows?('user1', ['group1'], Permissions::FULL))
    assert_equal(true, perms.allows?('user1', ['group1'], Permissions::GRANT))
    assert_equal(true, perms.allows?('user1', ['group1'], Permissions::WRITE))
    assert_equal(true, perms.allows?('user1', ['group1'], Permissions::READ))

    assert_equal(false, perms.allows?('user2', [], Permissions::FULL))
    assert_equal(false, perms.allows?('user2', [], Permissions::GRANT))
    assert_equal(false, perms.allows?('user2', [], Permissions::WRITE))
    assert_equal(false, perms.allows?('user2', [], Permissions::READ))

    assert_equal(false, perms.allows?('user2', ['group1'], Permissions::FULL))
    assert_equal(false, perms.allows?('user2', ['group1'], Permissions::GRANT))
    assert_equal(true, perms.allows?('user2', ['group1'], Permissions::WRITE))
    assert_equal(true, perms.allows?('user2', ['group1'], Permissions::READ))

    assert_equal(
      [
        ['debug', 'permission check action=full username=hacluster groups='],
        ['debug', 'permission granted for superuser'],
        ['debug', 'permission check action=grant username=hacluster groups='],
        ['debug', 'permission granted for superuser'],
        ['debug', 'permission check action=write username=hacluster groups='],
        ['debug', 'permission granted for superuser'],
        ['debug', 'permission check action=read username=hacluster groups='],
        ['debug', 'permission granted for superuser'],
        ['debug', 'permission check action=full username=user1 groups='],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=grant username=user1 groups='],
        ['debug', 'permission granted for user user1'],
        ['debug', 'permission check action=write username=user1 groups='],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=read username=user1 groups='],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=full username=user1 groups=group1'],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=grant username=user1 groups=group1'],
        ['debug', 'permission granted for user user1'],
        ['debug', 'permission check action=write username=user1 groups=group1'],
        ['debug', 'permission granted for group group1'],
        ['debug', 'permission check action=read username=user1 groups=group1'],
        ['debug', 'permission granted for group group1'],
        ['debug', 'permission check action=full username=user2 groups='],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=grant username=user2 groups='],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=write username=user2 groups='],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=read username=user2 groups='],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=full username=user2 groups=group1'],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=grant username=user2 groups=group1'],
        ['debug', 'permission denied'],
        ['debug', 'permission check action=write username=user2 groups=group1'],
        ['debug', 'permission granted for group group1'],
        ['debug', 'permission check action=read username=user2 groups=group1'],
        ['debug', 'permission granted for group group1'],
      ],
      $logger.log
    )
  end

  def test_merge!
    perms = Permissions::PermissionsSet.new([
      Permissions::EntityPermissions.new(
        Permissions::TYPE_USER, 'user1', [Permissions::GRANT]
      ),
      Permissions::EntityPermissions.new(
        Permissions::TYPE_GROUP, 'user2', [Permissions::FULL]
      ),
      Permissions::EntityPermissions.new(
        Permissions::TYPE_USER, 'user1', [Permissions::READ]
      ),
    ])

    assert_equal(false, perms.allows?('user1', [], Permissions::FULL))
    assert_equal(true, perms.allows?('user1', [], Permissions::GRANT))
    assert_equal(false, perms.allows?('user1', [], Permissions::WRITE))
    assert_equal(true, perms.allows?('user1', [], Permissions::READ))
  end

end
