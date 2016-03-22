require 'test/unit'
require 'fileutils'

require 'pcsd_test_utils.rb'
require 'config.rb'
require 'permissions.rb'

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
    assert_equal(fixture_nil_config, cfg.text)
  end

  def test_parse_empty()
    text = ''
    cfg = PCSConfig.new(text)
    assert_equal(0, cfg.clusters.length)
    assert_equal([], $logger.log)
    assert_equal(fixture_empty_config, cfg.text)
  end

  def test_parse_whitespace()
    text = "  \n  "
    cfg = PCSConfig.new(text)
    assert_equal(0, cfg.clusters.length)
    assert_equal([], $logger.log)
    assert_equal(fixture_empty_config, cfg.text)
  end

  def test_parse_hash_empty()
    text = '{}'
    cfg = PCSConfig.new(text)
    assert_equal(
      [['error', 'Unable to parse pcs_settings file: invalid file format']],
      $logger.log
    )
    assert_equal(fixture_empty_config, cfg.text)
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
    assert_equal(fixture_empty_config, cfg.text)
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
    assert_equal(
      [[
        'error',
        "Unable to parse pcs_settings file: 399: unexpected token at '\"rh71-node2\"\n      ]\n    }\n  ]\n}'"
      ]],
      $logger.log
    )
    assert_equal(fixture_empty_config, cfg.text)
  end

  def test_parse_format1_empty()
    text = '[]'
    cfg = PCSConfig.new(text)
    assert_equal(0, cfg.clusters.length)
    assert_equal(
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
    assert_equal(
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
    assert_equal(fixture_empty_config, cfg.text)
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
    assert_equal(text, cfg.text)
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
    assert_equal(out_text, cfg.text)
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
    assert_equal(
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
    assert_equal(out_text, cfg.text)

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

    assert(cfg.is_node_in_use('rh71-node1'))
    assert(cfg.is_node_in_use('rh67-node3'))
    assert(! cfg.is_node_in_use('rh71-node3'))

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


class TestTokens < Test::Unit::TestCase
  def setup
    $logger = MockLogger.new
    FileUtils.cp(File.join(CURRENT_DIR, 'tokens'), CFG_PCSD_TOKENS)
  end

  def fixture_empty_config()
    return(
'{
  "format_version": 2,
  "data_version": 0,
  "tokens": {
  }
}'
    )
  end

  def test_parse_nil()
    text = nil
    cfg = PCSTokens.new(text)
    assert_equal(0, cfg.tokens.length)
    assert_equal([], $logger.log)
    assert_equal(fixture_empty_config(), cfg.text)
  end

  def test_parse_empty()
    text = ''
    cfg = PCSTokens.new(text)
    assert_equal(0, cfg.tokens.length)
    assert_equal([], $logger.log)
    assert_equal(fixture_empty_config(), cfg.text)
  end

  def test_parse_whitespace()
    text = "  \n  "
    cfg = PCSTokens.new(text)
    assert_equal(0, cfg.tokens.length)
    assert_equal([], $logger.log)
    assert_equal(fixture_empty_config(), cfg.text)
  end

  def test_parse_format1()
    text = '{}'
    cfg = PCSTokens.new(text)
    assert_equal(0, cfg.tokens.length)

    text = '{"rh7-1": "token-rh7-1", "rh7-2": "token-rh7-2"}'
    cfg = PCSTokens.new(text)
    assert_equal(2, cfg.tokens.length)
    assert_equal('token-rh7-1', cfg.tokens['rh7-1'])
    assert_equal(
'{
  "format_version": 2,
  "data_version": 0,
  "tokens": {
    "rh7-1": "token-rh7-1",
    "rh7-2": "token-rh7-2"
  }
}',
      cfg.text
    )
  end

  def test_parse_format2()
    text =
'{
  "format_version": 2,
  "tokens": {}
}'
    cfg = PCSTokens.new(text)
    assert_equal(2, cfg.format_version)
    assert_equal(0, cfg.data_version)
    assert_equal(0, cfg.tokens.length)
    assert_equal(
'{
  "format_version": 2,
  "data_version": 0,
  "tokens": {
  }
}',
      cfg.text
    )

    text =
'{
  "format_version": 2,
  "data_version": 9,
  "tokens": {
    "rh7-1": "token-rh7-1",
    "rh7-2": "token-rh7-2"
  }
}'
    cfg = PCSTokens.new(text)
    assert_equal(2, cfg.format_version)
    assert_equal(9, cfg.data_version)
    assert_equal(2, cfg.tokens.length)
    assert_equal('token-rh7-1', cfg.tokens['rh7-1'])
    assert_equal(text, cfg.text)
  end

  def test_update()
    cfg = PCSTokens.new(File.open(CFG_PCSD_TOKENS).read)
    assert_equal(
      {
        'rh7-1' => '2a8b40aa-b539-4713-930a-483468d62ef4',
        'rh7-2' => '76174e2c-09e8-4435-b318-5c6b8250a22c',
        'rh7-3' => '55844951-9ae5-4103-bb4a-64f9c1ea0a71',
      },
      cfg.tokens
    )

    cfg.tokens.delete('rh7-2')
    assert_equal(
      {
        'rh7-1' => '2a8b40aa-b539-4713-930a-483468d62ef4',
        'rh7-3' => '55844951-9ae5-4103-bb4a-64f9c1ea0a71',
      },
      cfg.tokens
    )

    cfg.tokens['rh7-2'] = '76174e2c-09e8-4435-b318-5c6b8250a22c'
    assert_equal(
      {
        'rh7-1' => '2a8b40aa-b539-4713-930a-483468d62ef4',
        'rh7-3' => '55844951-9ae5-4103-bb4a-64f9c1ea0a71',
        'rh7-2' => '76174e2c-09e8-4435-b318-5c6b8250a22c',
      },
      cfg.tokens
    )
    assert_equal(
'{
  "format_version": 2,
  "data_version": 9,
  "tokens": {
    "rh7-1": "2a8b40aa-b539-4713-930a-483468d62ef4",
    "rh7-2": "76174e2c-09e8-4435-b318-5c6b8250a22c",
    "rh7-3": "55844951-9ae5-4103-bb4a-64f9c1ea0a71"
  }
}',
      cfg.text
    )
  end
end
