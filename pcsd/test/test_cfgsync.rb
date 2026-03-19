require 'test/unit'
require 'fileutils'

require 'pcsd_test_utils.rb'
require 'cfgsync.rb'
require 'config.rb'


class TestCfgsync < Test::Unit::TestCase
  def test_compare_version()
    cfg1 = Cfgsync::PcsdSettings.from_text(
      '{"data_version": 1, "format_version": 2}'
    )
    cfg2 = Cfgsync::PcsdSettings.from_text(
      '{"data_version": 1, "format_version": 2}'
    )
    cfg3 = Cfgsync::PcsdSettings.from_text(
      '{"data_version": 2, "format_version": 2}'
    )
    cfg4 = Cfgsync::PcsdSettings.from_text(
      '{"data_version": 2, "clusters": [], "format_version": 2}'
    )

    assert(cfg1 == cfg2)
    assert(cfg1 < cfg3)
    assert(cfg1 < cfg4)
    assert(cfg3 > cfg1)
    assert_equal("e28c7dfa675fdba4c55b8e3e7a854a252426514f", cfg3.hash)
    assert_equal("21ceb5ff1c8b35b9b79adabcfdac30849666a6f7", cfg4.hash)
    assert(cfg3 > cfg4)

    newest = [cfg1, cfg2, cfg3, cfg4].shuffle!.max
    assert_equal(2, newest.version)
    assert_equal('e28c7dfa675fdba4c55b8e3e7a854a252426514f', newest.hash)
  end
end


class TestCorosyncConf < Test::Unit::TestCase
  def setup()
    FileUtils.cp(File.join(CURRENT_DIR, 'corosync.conf'), CFG_COROSYNC_CONF)
  end

  def test_basics()
    assert_equal('corosync.conf', Cfgsync::CorosyncConf.name)
    text = '
totem {
    version: 2
    cluster_name: test99
    config_version: 3
}
'
    cfg = Cfgsync::CorosyncConf.from_text(text)
    assert_equal(3, cfg.version)
    assert_equal('570c9f0324f1dec73a632fa9ae4a0dd53ebf8bc7', cfg.hash)

    cfg.version = 4
    assert_equal(4, cfg.version)
    assert_equal('efe2fc7d92ddf17ba1f14f334004c7c1933bb1e3', cfg.hash)

    cfg.text = "\
totem {
    version: 2
    cluster_name: test99
    config_version: 4
}
"
    assert_equal(4, cfg.version)
    assert_equal('efe2fc7d92ddf17ba1f14f334004c7c1933bb1e3', cfg.hash)
  end

  def test_file()
    cfg = Cfgsync::CorosyncConf.from_file()
    assert_equal(9, cfg.version)
    assert_equal('3711fd79c5972b21877a477d0d88c9eeb0d10a22', cfg.hash)
  end

  def test_version()
    text = '
totem {
    version: 2
    cluster_name: test99
}
'
    cfg = Cfgsync::CorosyncConf.from_text(text)
    assert_equal(0, cfg.version)

    text = '
totem {
    version: 2
    cluster_name: test99
    config_version: 3
    config_version: 4
}
'
    cfg = Cfgsync::CorosyncConf.from_text(text)
    assert_equal(4, cfg.version)

    text = '
totem {
    version: 2
    cluster_name: test99
    config_version: foo
}
'
    cfg = Cfgsync::CorosyncConf.from_text(text)
    assert_equal(0, cfg.version)

    text = '
totem {
    version: 2
    cluster_name: test99
    config_version: 1foo
}
'
    cfg = Cfgsync::CorosyncConf.from_text(text)
    assert_equal(1, cfg.version)
  end
end


class TestPcsdSettings < Test::Unit::TestCase
  def teardown()
    FileUtils.rm(CFG_PCSD_SETTINGS, :force => true)
  end

  def test_basics()
    assert_equal("pcs_settings.conf", Cfgsync::PcsdSettings.name)
    text = '
{
  "format_version": 2,
  "data_version": 3,
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
}
    '

    cfg = Cfgsync::PcsdSettings.from_text(text)
    assert_equal(text, cfg.text)
    assert_equal(3, cfg.version)
    assert_equal('b35f951a228ac0734d4c1e45fe73c03b18bca380', cfg.hash)

    # rubygem-json shipped with ruby 3.4 changed the way JSON.pretty_generate
    # works a bit. This results in different strings produced by the gem in
    # ruby older that 3.4 compared to ruby 3.4+. By examining the output of
    # JSON.pretty_generate, we can figure out which version of the gem we run
    # against and use the correct hash for the produced string.
    # https://bugzilla.redhat.com/show_bug.cgi?id=2331005
    old_rubygem = JSON.pretty_generate([]) == "[\n\n]"
    if old_rubygem
      expected_hash = '50939a7d12d2411020f9fb42b0c411add2db39ca'
    else
      expected_hash = '47fdd9bd32d9771f66685664cb0e7d20c4609f25'
    end

    cfg.version = 4
    assert_equal(4, cfg.version)
    assert_equal(expected_hash, cfg.hash)

    cfg.text = '{
  "format_version": 2,
  "data_version": 4,
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
    assert_equal(4, cfg.version)
    assert_equal('efe28c6d63dbce02da1a414ddb68fa1fc4f89c2e', cfg.hash)
  end

  def test_file()
    FileUtils.cp(File.join(CURRENT_DIR, "pcs_settings.conf"), CFG_PCSD_SETTINGS)
    cfg = Cfgsync::PcsdSettings.from_file()
    assert_equal(9, cfg.version)
    assert_equal("ac032803c5190d735cd94a702d42c5c6358013b8", cfg.hash)
  end

  def test_file_missing()
    cfg = Cfgsync::PcsdSettings.from_file()
    assert_equal(0, cfg.version)
    assert_equal('da39a3ee5e6b4b0d3255bfef95601890afd80709', cfg.hash)
  end
end


class TestPcsdKnownHosts < Test::Unit::TestCase
  def teardown()
    FileUtils.rm(CFG_PCSD_KNOWN_HOSTS, :force => true)
  end

  def test_basics()
    assert_equal('known-hosts', Cfgsync::PcsdKnownHosts.name)
    template =
'{
  "format_version": 1,
  "data_version": %d,
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

    text = template % 2
    cfg = Cfgsync::PcsdKnownHosts.from_text(text)
    assert_equal(text, cfg.text)
    assert_equal(2, cfg.version)
    assert_equal('b34d5dde2727156d3a0f652e83aa1ed1c14104f5', cfg.hash)

    cfg.version = 3
    assert_equal(3, cfg.version)
    assert_equal('c55f29f635525d22f2935a2e26998f5ba468bbb0', cfg.hash)

    cfg.text = template % 4
    assert_equal(4, cfg.version)
    assert_equal('f9c01aa74cf6dee7eea447c6ffcf253d3bb5b660', cfg.hash)
  end

  def test_file()
    FileUtils.cp(File.join(CURRENT_DIR, 'known-hosts'), CFG_PCSD_KNOWN_HOSTS)
    cfg = Cfgsync::PcsdKnownHosts.from_file()
    assert_equal(5, cfg.version)
    assert_equal('dcf0e2f53084b3bc26451753b639d7c1e28ac1a7', cfg.hash)
  end

  def test_file_missing()
    cfg = Cfgsync::PcsdKnownHosts.from_file()
    assert_equal(0, cfg.version)
    assert_equal('da39a3ee5e6b4b0d3255bfef95601890afd80709', cfg.hash)
  end
end


class TestConfigFetcher < Test::Unit::TestCase
  class ConfigFetcherMock < Cfgsync::ConfigFetcher
    def get_configs_local()
      return @configs_local
    end

    def set_configs_local(configs)
      @configs_local = configs
      return self
    end

    def get_configs_cluster(nodes, cluster_name)
      return @configs_cluster, @node_connected
    end

    def set_configs_cluster(configs, node_connected=true)
      @configs_cluster = configs
      @node_connected = node_connected
      return self
    end

    def find_newest_config_test(config_list)
      return self.find_newest_config(config_list)
    end
  end

  def test_find_newest_config()
    cfg1 = Cfgsync::PcsdSettings.from_text(
      '{"data_version": 1, "format_version": 2}'
    )
    cfg2 = Cfgsync::PcsdSettings.from_text(
      '{"data_version": 1, "format_version": 2}'
    )
    cfg3 = Cfgsync::PcsdSettings.from_text(
      '{"data_version": 2, "clusters": [], "format_version": 2}'
    )
    cfg4 = Cfgsync::PcsdSettings.from_text(
      '{"data_version": 2, "format_version": 2}'
    )
    assert(cfg1 == cfg2)
    assert(cfg1 < cfg3)
    assert(cfg1 < cfg4)
    assert(cfg3 < cfg4)
    fetcher = ConfigFetcherMock.new({}, nil, nil, nil)

    # trivial case
    assert_equal(cfg1, fetcher.find_newest_config_test([cfg1]))
    # decide by version only
    assert_equal(cfg3, fetcher.find_newest_config_test([cfg1, cfg2, cfg3]))
    assert_equal(cfg3, fetcher.find_newest_config_test([cfg1, cfg1, cfg3]))
    # in case of multiple configs with the same version decide by count
    assert_equal(cfg3, fetcher.find_newest_config_test([cfg3, cfg3, cfg4]))
    assert_equal(
      cfg3, fetcher.find_newest_config_test([cfg1, cfg3, cfg3, cfg4])
    )
    # if the count is the same decide by hash
    assert(cfg3 < cfg4)
    assert_equal(cfg4, fetcher.find_newest_config_test([cfg3, cfg4]))
    assert_equal(cfg4, fetcher.find_newest_config_test([cfg1, cfg3, cfg4]))
    assert_equal(
      cfg4, fetcher.find_newest_config_test([cfg3, cfg3, cfg4, cfg4])
    )
    assert_equal(
      cfg4, fetcher.find_newest_config_test([cfg1, cfg3, cfg3, cfg4, cfg4])
    )
  end

  def test_fetch()
    cfg1 = Cfgsync::PcsdSettings.from_text(
      '{"data_version": 1, "format_version": 2}'
    )
    cfg2 = Cfgsync::PcsdSettings.from_text(
      '{"data_version": 1, "format_version": 2}'
    )
    cfg3 = Cfgsync::PcsdSettings.from_text(
      '{"data_version": 2, "clusters": [], "format_version": 2}'
    )
    cfg4 = Cfgsync::PcsdSettings.from_text(
      '{"data_version": 2, "format_version": 2}'
    )
    assert(cfg1 == cfg2)
    assert(cfg1 < cfg3)
    assert(cfg1 < cfg4)
    assert(cfg3 < cfg4)
    cfg_name = Cfgsync::PcsdSettings.name
    fetcher = ConfigFetcherMock.new({}, [Cfgsync::PcsdSettings], nil, nil)

    # unable to connect to any nodes
    fetcher.set_configs_local({cfg_name => cfg1})

    fetcher.set_configs_cluster({}, false)
    assert_equal([[], [], false], fetcher.fetch())

    # local config is synced
    fetcher.set_configs_local({cfg_name => cfg1})

    fetcher.set_configs_cluster({
      'node1' => {'configs' => {cfg_name => cfg1}},
    })
    assert_equal([[], [], true], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {'configs' => {cfg_name => cfg2}},
    })
    assert_equal([[], [], true], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {'configs' => {cfg_name => cfg1}},
      'node2' => {'configs' => {cfg_name => cfg2}},
    })
    assert_equal([[], [], true], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {'configs' => {cfg_name => cfg1}},
      'node2' => {'configs' => {cfg_name => cfg2}},
      'node3' => {'configs' => {cfg_name => cfg2}},
    })
    assert_equal([[], [], true], fetcher.fetch())

    # local config is older
    fetcher.set_configs_local({cfg_name => cfg1})

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
    })
    assert_equal([[cfg3], [], true], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
    })
    assert_equal([[cfg4], [], true], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
      'node3' => {cfg_name => cfg3},
    })
    assert_equal([[cfg3], [], true], fetcher.fetch())

    # local config is newer
    fetcher.set_configs_local({cfg_name => cfg3})

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg1},
    })
    assert_equal([[], [cfg3], true], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg1},
      'node2' => {cfg_name => cfg1},
    })
    assert_equal([[], [cfg3], true], fetcher.fetch())

    # local config is the same version
    fetcher.set_configs_local({cfg_name => cfg3})

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
    })
    assert_equal([[], [], true], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg4},
    })
    assert_equal([[cfg4], [], true], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
    })
    assert_equal([[cfg4], [], true], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
      'node3' => {cfg_name => cfg3},
    })
    assert_equal([[], [], true], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
      'node3' => {cfg_name => cfg4},
    })
    assert_equal([[cfg4], [], true], fetcher.fetch())

    # local config is the same version
    fetcher.set_configs_local({cfg_name => cfg4})

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
    })
    assert_equal([[cfg3], [], true], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg4},
    })
    assert_equal([[], [], true], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
    })
    assert_equal([[], [], true], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
      'node3' => {cfg_name => cfg3},
    })
    assert_equal([[cfg3], [], true], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
      'node3' => {cfg_name => cfg4},
    })
    assert_equal([[], [], true], fetcher.fetch())
  end
end


class TestGetFailedNodesFromSyncResponses < Test::Unit::TestCase
  def test_no_responses()
    assert_equal(
      Cfgsync::get_failed_nodes_from_sync_responses({}),
      [[], []]
    )
  end

  def test_all_ok()
    assert_equal(
      Cfgsync::get_failed_nodes_from_sync_responses({
        'node1' => {
          'status' => 'ok',
          'result' => {
            'config_a' => 'accepted',
          }
        },
        'node2' => {
          'status' => 'ok',
          'result' => {
            'config_a' => 'rejected',
          }
        },
      }),
      [[], []]
    )
  end

  def test_ok_and_errors()
    assert_equal(
      Cfgsync::get_failed_nodes_from_sync_responses({
        'node1' => {
          'status' => 'ok',
          'result' => {
            'config_a' => 'accepted',
            'config_b' => 'accepted',
          }
        },
        'node2' => {
          'status' => 'ok',
          'result' => {
            'config_a' => 'rejected',
            'config_b' => 'not_supported',
          }
        },
        'node3' => {
          'status' => 'notauthorized',
        },
        'node4' => {
          'status' => 'error',
        },
      }),
      [["node3"], ["node2", "node4"]]
    )
  end
end
