require 'test/unit'

require 'resource.rb'

class GetResourceAgentNameStructure < Test::Unit::TestCase
  def test_three_parts
    assert_equal(
      get_resource_agent_name_structure('standard:provider:type'),
      {
        :full_name => 'standard:provider:type',
        :class => 'standard',
        :provider => 'provider',
        :type => 'type',
      }
    )
  end

  def test_two_parts
    assert_equal(
      get_resource_agent_name_structure('standard:type'),
      {
        :full_name => 'standard:type',
        :class => 'standard',
        :provider => nil,
        :type => 'type',
      }
    )
  end

  def test_systemd_instance
    assert_equal(
      get_resource_agent_name_structure('systemd:service@instance:name'),
      {
        :full_name => 'systemd:service@instance:name',
        :class => 'systemd',
        :provider => nil,
        :type => 'service@instance:name',
      }
    )
  end

  def test_service_instance
    assert_equal(
      get_resource_agent_name_structure('service:service@instance:name'),
      {
        :full_name => 'service:service@instance:name',
        :class => 'service',
        :provider => nil,
        :type => 'service@instance:name',
      }
    )
  end
end
