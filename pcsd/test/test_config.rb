require 'test/unit'
require 'fileutils'

require 'pcsd_test_utils.rb'
require 'config.rb'
require 'permissions.rb'

def assert_equal_json(json1, json2)
  # https://bugzilla.redhat.com/show_bug.cgi?id=2331005
  assert_equal(
    JSON.pretty_generate(JSON.parse(json1)),
    JSON.pretty_generate(JSON.parse(json2))
  )
end

class TestConfig < Test::Unit::TestCase
  def setup
    $logger = MockLogger.new
    FileUtils.cp(File.join(CURRENT_DIR, 'pcs_settings.conf'), CFG_PCSD_SETTINGS)
  end

  def fixture_nil_config()
    return (
'{
  "format_version": 2,
  "data_version": 0,
  "clusters": [

  ],
  "permissions": {
    "local_cluster": [
      {
        "type": "group",
        "name": "haclient",
        "allow": [
          "grant",
          "read",
          "write"
        ]
      }
    ]
  }
}')
  end

  def fixture_empty_config()
    return (
'{
  "format_version": 2,
  "data_version": 0,
  "clusters": [

  ],
  "permissions": {
    "local_cluster": [

    ]
  }
}')
  end

  def test_parse_nil()
    text = nil
    cfg = PCSConfig.new(text)
    assert_equal(0, cfg.clusters.length)
    assert_equal([], $logger.log)
    assert_equal_json(fixture_nil_config, cfg.text)
  end

  def test_parse_empty()
    text = ''
    cfg = PCSConfig.new(text)
    assert_equal(0, cfg.clusters.length)
    assert_equal([], $logger.log)
    assert_equal_json(fixture_empty_config, cfg.text)
  end

  def test_parse_whitespace()
    text = "  \n  "
    cfg = PCSConfig.new(text)
    assert_equal(0, cfg.clusters.length)
    assert_equal([], $logger.log)
    assert_equal_json(fixture_empty_config, cfg.text)
  end

  def test_parse_hash_empty()
    text = '{}'
    cfg = PCSConfig.new(text)
    assert_equal(
      [['error', 'Unable to parse pcs_settings file: invalid file format']],
      $logger.log
    )
    assert_equal_json(fixture_empty_config, cfg.text)
  end

  def test_parse_hash_no_version()
    text =
'{
  "data_version": 9,
  "clusters": [
    {
      "name": "cluster71",
      "nodes": [
        "rh71-node1",
        "rh71-node2"
      ]
    }
  ]
}'
    cfg = PCSConfig.new(text)
    assert_equal(
      [['error', 'Unable to parse pcs_settings file: invalid file format']],
      $logger.log
    )
    assert_equal_json(fixture_empty_config, cfg.text)
  end

  def test_parse_malformed()
    text =
'{
  "data_version": 9,
  "clusters": [
    {
      "name": "cluster71",
      "nodes": [
        "rh71-node1"
        "rh71-node2"
      ]
    }
  ]
}'
    cfg = PCSConfig.new(text)
    assert_equal(1, $logger.log.length)
    assert_equal('error', $logger.log[0][0])
    assert_match(
      # the number is based on JSON gem version
      /Unable to parse pcs_settings file: (\d+: )?unexpected token/,
      $logger.log[0][1]
    )
    assert_equal_json(fixture_empty_config, cfg.text)
  end

  def test_parse_format1_empty()
    text = '[]'
    cfg = PCSConfig.new(text)
    assert_equal(0, cfg.clusters.length)
    assert_equal_json(
'{
  "format_version": 2,
  "data_version": 0,
  "clusters": [

  ],
  "permissions": {
    "local_cluster": [
      {
        "type": "group",
        "name": "haclient",
        "allow": [
          "grant",
          "read",
          "write"
        ]
      }
    ]
  }
}',
      cfg.text
    )
  end

  def test_parse_format1_one_cluster()
    text = '
[
  {
    "name": "cluster71",
    "nodes": [
      "rh71-node1",
      "rh71-node2"
    ]
  }
]
'
    cfg = PCSConfig.new(text)
    assert_equal(1, cfg.clusters.length)
    assert_equal("cluster71", cfg.clusters[0].name)
    assert_equal(["rh71-node1", "rh71-node2"], cfg.clusters[0].nodes)
    assert_equal_json(
'{
  "format_version": 2,
  "data_version": 0,
  "clusters": [
    {
      "name": "cluster71",
      "nodes": [
        "rh71-node1",
        "rh71-node2"
      ]
    }
  ],
  "permissions": {
    "local_cluster": [
      {
        "type": "group",
        "name": "haclient",
        "allow": [
          "grant",
          "read",
          "write"
        ]
      }
    ]
  }
}',
      cfg.text
    )
  end

  def test_parse_format2_empty()
    text = '
{
  "format_version": 2
}
'
    cfg = PCSConfig.new(text)
    assert_equal(2, cfg.format_version)
    assert_equal(0, cfg.data_version)
    assert_equal(0, cfg.clusters.length)
    assert_equal_json(fixture_empty_config, cfg.text)
  end

  def test_parse_format2_one_cluster()
    text =
'{
  "format_version": 2,
  "data_version": 9,
  "clusters": [
    {
      "name": "cluster71",
      "nodes": [
        "rh71-node1",
        "rh71-node2"
      ]
    }
  ],
  "permissions": {
    "local_cluster": [

    ]
  }
}'
    cfg = PCSConfig.new(text)
    assert_equal(2, cfg.format_version)
    assert_equal(9, cfg.data_version)
    assert_equal(1, cfg.clusters.length)
    assert_equal("cluster71", cfg.clusters[0].name)
    assert_equal(["rh71-node1", "rh71-node2"], cfg.clusters[0].nodes)
    assert_equal_json(text, cfg.text)
  end

  def test_parse_format2_two_clusters()
    text =
'{
  "format_version": 2,
  "data_version": 9,
  "clusters": [
    {
      "name": "cluster71",
      "nodes": [
        "rh71-node2",
        "rh71-node1",
        "rh71-node3",
        "rh71-node2"
      ]
    },
    {
      "name": "abcd",
      "nodes": [
        "abcd-node2",
        "abcd-node1",
        "abcd-node3",
        "abcd-node2"
      ]
    }
  ],
  "permissions": {
    "local_cluster": [

    ]
  }
}'
    cfg = PCSConfig.new(text)
    assert_equal(2, cfg.format_version)
    assert_equal(9, cfg.data_version)
    assert_equal(2, cfg.clusters.length)
    assert_equal("cluster71", cfg.clusters[0].name)
    assert_equal(
      ["rh71-node1", "rh71-node2", "rh71-node3"],
      cfg.clusters[0].nodes
    )
    out_text =
'{
  "format_version": 2,
  "data_version": 9,
  "clusters": [
    {
      "name": "cluster71",
      "nodes": [
        "rh71-node1",
        "rh71-node2",
        "rh71-node3"
      ]
    },
    {
      "name": "abcd",
      "nodes": [
        "abcd-node1",
        "abcd-node2",
        "abcd-node3"
      ]
    }
  ],
  "permissions": {
    "local_cluster": [

    ]
  }
}'
    assert_equal_json(out_text, cfg.text)
  end

  def test_parse_format2_bad_cluster()
    text =
'{
  "format_version": 2,
  "data_version": 9,
  "clusters": [
    {
      "name": "cluster71",
      "nodes": [
        "rh71-node2",
        "rh71-node1",
          [
            "xxx",
            "yyy"
          ],
        "rh71-node2"
      ]
    }
  ]
}'
    cfg = PCSConfig.new(text)
    assert_equal(2, cfg.format_version)
    assert_equal(9, cfg.data_version)
    assert_equal(1, cfg.clusters.length)
    assert_equal("cluster71", cfg.clusters[0].name)
    assert_equal(["rh71-node1", "rh71-node2"], cfg.clusters[0].nodes)
    assert_equal_json(
'{
  "format_version": 2,
  "data_version": 9,
  "clusters": [
    {
      "name": "cluster71",
      "nodes": [
        "rh71-node1",
        "rh71-node2"
      ]
    }
  ],
  "permissions": {
    "local_cluster": [

    ]
  }
}',
      cfg.text
    )
  end

  def test_parse_format2_permissions()
    text =
'{
  "format_version": 2,
  "data_version": 9,
  "clusters": [
    {
      "name": "cluster71",
      "nodes": [
        "rh71-node1",
        "rh71-node2"
      ]
    }
  ],
  "permissions": {
    "local_cluster": [
      {
        "type": "group",
        "name": "group2",
        "allow": [
          "read"
        ]
      },
      {
        "type": "user",
        "name": "user2",
        "allow": [

        ]
      },
      {
        "type": "group",
        "name": "group2",
        "allow": [
          "grant"
        ]
      },
      {
        "type": "group",
        "name": "group1",
        "allow": [
          "write", "full", "write"
        ]
      },
      {
        "type": "user",
        "name": "user1",
        "allow": [
          "grant", "write", "grant", "read"
        ]
      }
    ]
  }
}'
    out_text =
'{
  "format_version": 2,
  "data_version": 9,
  "clusters": [
    {
      "name": "cluster71",
      "nodes": [
        "rh71-node1",
        "rh71-node2"
      ]
    }
  ],
  "permissions": {
    "local_cluster": [
      {
        "type": "group",
        "name": "group1",
        "allow": [
          "full",
          "write"
        ]
      },
      {
        "type": "group",
        "name": "group2",
        "allow": [
          "grant",
          "read"
        ]
      },
      {
        "type": "user",
        "name": "user1",
        "allow": [
          "grant",
          "read",
          "write"
        ]
      },
      {
        "type": "user",
        "name": "user2",
        "allow": [

        ]
      }
    ]
  }
}'
    cfg = PCSConfig.new(text)
    assert_equal_json(out_text, cfg.text)

    perms = cfg.permissions_local
    assert_equal(false, perms.allows?('user1', [], Permissions::FULL))
    assert_equal(true, perms.allows?('user1', [], Permissions::GRANT))
    assert_equal(true, perms.allows?('user1', [], Permissions::WRITE))
    assert_equal(true, perms.allows?('user1', [], Permissions::READ))

    assert_equal(true, perms.allows?('user1', ['group1'], Permissions::FULL))
    assert_equal(true, perms.allows?('user1', ['group1'], Permissions::GRANT))
    assert_equal(true, perms.allows?('user1', ['group1'], Permissions::WRITE))
    assert_equal(true, perms.allows?('user1', ['group1'], Permissions::READ))

    assert_equal(false, perms.allows?('user2', [], Permissions::FULL))
    assert_equal(false, perms.allows?('user2', [], Permissions::GRANT))
    assert_equal(false, perms.allows?('user2', [], Permissions::WRITE))
    assert_equal(false, perms.allows?('user2', [], Permissions::READ))

    assert_equal(false, perms.allows?('user2', ['group2'], Permissions::FULL))
    assert_equal(true, perms.allows?('user2', ['group2'], Permissions::GRANT))
    assert_equal(false, perms.allows?('user2', ['group2'], Permissions::WRITE))
    assert_equal(true, perms.allows?('user2', ['group2'], Permissions::READ))
  end

  def test_in_use()
    cfg = PCSConfig.new(File.open(CFG_PCSD_SETTINGS).read)

    assert(cfg.is_cluster_name_in_use('cluster71'))
    assert(cfg.is_cluster_name_in_use('cluster67'))
    assert(! cfg.is_cluster_name_in_use('nonexistent'))

    assert_equal(cfg.get_nodes_cluster('rh71-node1'), 'cluster71')
    assert_equal(cfg.get_nodes_cluster('rh67-node3'), 'cluster67')
    assert_equal(cfg.get_nodes_cluster('rh71-node3'), nil)

    assert_equal(
      ["rh71-node1", "rh71-node2"],
      cfg.get_nodes('cluster71')
    )
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )
    assert_equal(
      nil,
      cfg.get_nodes('nonexistent')
    )
  end

  def test_update_cluster()
    cfg = PCSConfig.new(File.open(CFG_PCSD_SETTINGS).read)
    assert_equal(
      ["rh71-node1", "rh71-node2"],
      cfg.get_nodes('cluster71')
    )
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )

    cfg.update_cluster('cluster71', ["rh71-node1", "rh71-node2", "rh71-node3"])
    assert_equal(
      ["rh71-node1", "rh71-node2", "rh71-node3"],
      cfg.get_nodes('cluster71')
    )
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )

    cfg.update_cluster('cluster71', ["rh71-node1", "rh71-node2"])
    assert_equal(
      ["rh71-node1", "rh71-node2"],
      cfg.get_nodes('cluster71')
    )
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )

    cfg.update_cluster('cluster71', [])
    assert(! cfg.is_cluster_name_in_use('cluster71'))
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )

    cfg.update_cluster(
      'cluster67',
      ['rh67-node3', [], 'rh67-node1', 'rh67-node2', ['xx'], 'rh67-node1']
    )
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )
  end

  def test_remove_cluster()
    cfg = PCSConfig.new(File.open(CFG_PCSD_SETTINGS).read)
    assert_equal(
      ["rh71-node1", "rh71-node2"],
      cfg.get_nodes('cluster71')
    )
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )

    cfg.remove_cluster('nonexistent')
    assert_equal(
      ["rh71-node1", "rh71-node2"],
      cfg.get_nodes('cluster71')
    )
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )

    cfg.remove_cluster('cluster71')
    assert(! cfg.is_cluster_name_in_use('cluster71'))
    assert_equal(
      ["rh67-node1", "rh67-node2", "rh67-node3"],
      cfg.get_nodes('cluster67')
    )
  end

  def test_cluster_nodes_equal?()
    text =
'{
  "format_version": 2,
  "data_version": 9,
  "clusters": [
    {
      "name": "cluster71",
      "nodes": [
        "rh71-node1",
        "rh71-node2"
      ]
    }
  ],
  "permissions": {
    "local_cluster": [

    ]
  }
}'
    cfg = PCSConfig.new(text)

    assert_equal(
      true,
      cfg.cluster_nodes_equal?('cluster71', ['rh71-node1', 'rh71-node2'])
    )
    assert_equal(
      true,
      cfg.cluster_nodes_equal?('cluster71', ['rh71-node1', 'rh71-node2', 'rh71-node1'])
    )
    assert_equal(
      true,
      cfg.cluster_nodes_equal?('cluster71', ['rh71-node2', 'rh71-node1'])
    )
    assert_equal(
      false,
      cfg.cluster_nodes_equal?('cluster71', [])
    )
    assert_equal(
      false,
      cfg.cluster_nodes_equal?('cluster71', ['rh71-node1'])
    )
    assert_equal(
      false,
      cfg.cluster_nodes_equal?('cluster71', ['rh71-node3', 'rh71-node1'])
    )
    assert_equal(
      false,
      cfg.cluster_nodes_equal?('cluster71', ['rh71-node1', 'rh71-node2', 'rh71-node3'])
    )

    assert_equal(
      false,
      cfg.cluster_nodes_equal?('abcd', ['rh71-node3', 'rh71-node1'])
    )
    assert_equal(
      true,
      cfg.cluster_nodes_equal?('abcd', [])
    )
  end
end


class TestCfgKnownHosts < Test::Unit::TestCase
  def setup
    $logger = MockLogger.new
  end

  def fixture_empty_config()
    return(
'{
  "format_version": 1,
  "data_version": 0,
  "known_hosts": {
  }
}'
    )
  end

  def assert_empty_data(cfg)
    assert_equal(1, cfg.format_version)
    assert_equal(0, cfg.data_version)
    assert_equal(0, cfg.known_hosts.length)
    assert_equal_json(fixture_empty_config(), cfg.text)
  end

  def assert_known_host(host, name, token, dest_list)
    assert_equal(name, host.name)
    assert_equal(token, host.token)
    assert_equal(dest_list, host.dest_list)
  end

  def test_parse_nil()
    cfg = CfgKnownHosts.new(nil)
    assert_equal([], $logger.log)
    assert_empty_data(cfg)
  end

  def test_parse_empty()
    cfg = CfgKnownHosts.new('')
    assert_equal([], $logger.log)
    assert_empty_data(cfg)
  end

  def test_parse_whitespace()
    cfg = CfgKnownHosts.new("   \n   ")
    assert_equal([], $logger.log)
    assert_empty_data(cfg)
  end

  def test_parse_malformed()
    text =
'{
  "format_version": 1,
  "data_version": 0,
  "known_hosts": {
}'
    cfg = CfgKnownHosts.new(text)
    assert_equal(1, $logger.log.length)
    assert_equal('error', $logger.log[0][0])
    assert_match(
      # the number is based on JSON gem version
      /Unable to parse known-hosts file: (\d+: )?unexpected token/,
      $logger.log[0][1]
    )
    assert_empty_data(cfg)
  end

  def test_parse_format1_empty()
    cfg = CfgKnownHosts.new(fixture_empty_config())
    assert_equal([], $logger.log)
    assert_empty_data(cfg)
  end

  def test_parse_format1_simple()
    text =
'{
  "format_version": 1,
  "data_version": 2,
  "known_hosts": {
    "node1": {
      "dest_list": [
        {
          "addr": "10.0.1.1",
          "port": 2224
        }
      ],
      "token": "abcde"
    }
  }
}'
    cfg = CfgKnownHosts.new(text)
    assert_equal([], $logger.log)
    assert_equal(1, cfg.format_version)
    assert_equal(2, cfg.data_version)
    assert_equal(1, cfg.known_hosts.length)
    assert_equal('node1', cfg.known_hosts['node1'].name)
    assert_equal('abcde', cfg.known_hosts['node1'].token)
    assert_equal(
      [
        {'addr' => '10.0.1.1', 'port' => 2224}
      ],
      cfg.known_hosts['node1'].dest_list
    )
    assert_equal_json(text, cfg.text)
  end

  def test_parse_format1_complex()
    text =
'{
  "format_version": 1,
  "data_version": 2,
  "known_hosts": {
    "node1": {
      "dest_list": [
        {
          "addr": "10.0.1.1",
          "port": 2224
        },
        {
          "addr": "10.0.2.1",
          "port": 2225
        }
      ],
      "token": "abcde"
    },
    "node2": {
      "dest_list": [
        {
          "addr": "10.0.1.2",
          "port": 2234
        },
        {
          "addr": "10.0.2.2",
          "port": 2235
        }
      ],
      "token": "fghij"
    }
  }
}'
    cfg = CfgKnownHosts.new(text)
    assert_equal([], $logger.log)
    assert_equal(1, cfg.format_version)
    assert_equal(2, cfg.data_version)
    assert_equal(2, cfg.known_hosts.length)
    assert_known_host(
      cfg.known_hosts['node1'],
      'node1',
      'abcde',
      [
        {'addr' => '10.0.1.1', 'port' => 2224},
        {'addr' => '10.0.2.1', 'port' => 2225}
      ]
    )
    assert_known_host(
      cfg.known_hosts['node2'],
      'node2',
      'fghij',
      [
        {'addr' => '10.0.1.2', 'port' => 2234},
        {'addr' => '10.0.2.2', 'port' => 2235}
      ]
    )
    assert_equal_json(text, cfg.text)
  end

  def test_parse_format1_error()
    text =
'{
  "format_version": 1,
  "data_version": 2,
  "known_hosts": {
    "node1": {
      "token": "abcde"
    }
  }
}'
    cfg = CfgKnownHosts.new(text)
    assert_equal(1, $logger.log.length)
    assert_equal('error', $logger.log[0][0])
    assert_match(
      'Unable to parse known-hosts file: key not found: "dest_list"',
      $logger.log[0][1]
    )
    assert_equal(1, cfg.format_version)
    assert_equal(2, cfg.data_version)
    assert_equal(0, cfg.known_hosts.length)
  end

  def test_update()
    text =
'{
  "format_version": 1,
  "data_version": 2,
  "known_hosts": {
    "node1": {
      "dest_list": [
        {
          "addr": "10.0.1.1",
          "port": 2224
        }
      ],
      "token": "abcde"
    },
    "node2": {
      "dest_list": [
        {
          "addr": "10.0.1.2",
          "port": 2234
        }
      ],
      "token": "fghij"
    }
  }
}'
    cfg = CfgKnownHosts.new(text)
    assert_equal([], $logger.log)
    cfg.data_version += 1
    cfg.known_hosts.delete('node2')
    cfg.known_hosts['node3'] = PcsKnownHost.new(
      'node3',
      'klmno',
      [
        {'addr' => '10.0.1.3', 'port' => 2224}
      ]
    )
    assert_equal_json(
      cfg.text,
'{
  "format_version": 1,
  "data_version": 3,
  "known_hosts": {
    "node1": {
      "dest_list": [
        {
          "addr": "10.0.1.1",
          "port": 2224
        }
      ],
      "token": "abcde"
    },
    "node3": {
      "dest_list": [
        {
          "addr": "10.0.1.3",
          "port": 2224
        }
      ],
      "token": "klmno"
    }
  }
}'
    )
  end
end
