require 'test/unit'
require 'fileutils'

require 'pcsd_test_utils.rb'
require 'cfgsync.rb'


class TestCfgsync < Test::Unit::TestCase
  def test_compare_version()
    cfg1 = Cfgsync::ClusterConf.from_text(
      '<cluster config_version="1" name="test1"/>'
    )
    cfg2 = Cfgsync::ClusterConf.from_text(
      '<cluster config_version="1" name="test1"/>'
    )
    cfg3 = Cfgsync::ClusterConf.from_text(
      '<cluster config_version="2" name="test1"/>'
    )
    cfg4 = Cfgsync::ClusterConf.from_text(
      '<cluster config_version="2" name="test2"/>'
    )

    assert(cfg1 == cfg2)
    assert(cfg1 < cfg3)
    assert(cfg1 < cfg4)
    assert(cfg3 > cfg1)
    assert_equal("0ebab34c8034fd1cb268d1170de935a183d156cf", cfg3.hash)
    assert_equal("0f22e8a496ae00815d8bcbf005fd7b645ba9f617", cfg4.hash)
    assert(cfg3 < cfg4)

    newest = [cfg1, cfg2, cfg3, cfg4].shuffle!.max
    assert_equal(2, newest.version)
    assert_equal('0f22e8a496ae00815d8bcbf005fd7b645ba9f617', newest.hash)
  end
end


class TestClusterConf < Test::Unit::TestCase
  def setup()
    FileUtils.cp(File.join(CURRENT_DIR, "cluster.conf"), CFG_CLUSTER_CONF)
  end

  def test_basics()
    assert_equal("cluster.conf", Cfgsync::ClusterConf.name)
    text = '<cluster config_version="3" name="test1"/>'

    cfg = Cfgsync::ClusterConf.from_text(text)
    assert_equal(text, cfg.text)
    assert_equal(3, cfg.version)
    assert_equal("1c0ff62f0749bea0b877599a02f6557573f286e2", cfg.hash)

    cfg.version = 4
    assert_equal(4, cfg.version)
    assert_equal('589e22aaff926907cc1f4db48eeeb5e269e41c39', cfg.hash)

    cfg.text = "<cluster config_version='4' name='test1'/>"
    assert_equal(4, cfg.version)
    assert_equal('589e22aaff926907cc1f4db48eeeb5e269e41c39', cfg.hash)
  end

  def test_file()
    cfg = Cfgsync::ClusterConf.from_file()
    assert_equal(9, cfg.version)
    assert_equal("198bda4b748ef646de867cb850cd3ad208c36d8b", cfg.hash)
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
    assert_equal('cd8faaf2367ceafba281387fb9dfe70eba51769c', cfg.hash)
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
  def setup()
    FileUtils.cp(File.join(CURRENT_DIR, "pcs_settings.conf"), CFG_PCSD_SETTINGS)
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
  ]
}
    '

    cfg = Cfgsync::PcsdSettings.from_text(text)
    assert_equal(text, cfg.text)
    assert_equal(3, cfg.version)
    assert_equal("42eeb92e14b34886d92ca628ba515cc67c97b5f0", cfg.hash)

    cfg.version = 4
    assert_equal(4, cfg.version)
    assert_equal('efe28c6d63dbce02da1a414ddb68fa1fc4f89c2e', cfg.hash)

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
    cfg = Cfgsync::PcsdSettings.from_file()
    assert_equal(9, cfg.version)
    assert_equal("ac032803c5190d735cd94a702d42c5c6358013b8", cfg.hash)
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
      return @configs_cluster
    end

    def set_configs_cluster(configs)
      @configs_cluster = configs
      return self
    end

    def find_newest_config_test(config_list)
      return self.find_newest_config(config_list)
    end
  end

  def test_find_newest_config()
    cfg1 = Cfgsync::ClusterConf.from_text(
      '<cluster config_version="1" name="test1"/>'
    )
    cfg2 = Cfgsync::ClusterConf.from_text(
      '<cluster config_version="1" name="test1"/>'
    )
    cfg3 = Cfgsync::ClusterConf.from_text(
      '<cluster config_version="2" name="test1"/>'
    )
    cfg4 = Cfgsync::ClusterConf.from_text(
      '<cluster config_version="2" name="test2"/>'
    )
    assert(cfg1 == cfg2)
    assert(cfg1 < cfg3)
    assert(cfg1 < cfg4)
    assert(cfg3 < cfg4)
    fetcher = ConfigFetcherMock.new(nil, nil, nil)

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
    cfg1 = Cfgsync::ClusterConf.from_text(
      '<cluster config_version="1" name="test1"/>'
    )
    cfg2 = Cfgsync::ClusterConf.from_text(
      '<cluster config_version="1" name="test1"/>'
    )
    cfg3 = Cfgsync::ClusterConf.from_text(
      '<cluster config_version="2" name="test1"/>'
    )
    cfg4 = Cfgsync::ClusterConf.from_text(
      '<cluster config_version="2" name="test2"/>'
    )
    assert(cfg1 == cfg2)
    assert(cfg1 < cfg3)
    assert(cfg1 < cfg4)
    assert(cfg3 < cfg4)
    cfg_name = Cfgsync::ClusterConf.name
    fetcher = ConfigFetcherMock.new([Cfgsync::ClusterConf], nil, nil)

    # local config is synced
    fetcher.set_configs_local({cfg_name => cfg1})

    fetcher.set_configs_cluster({
      'node1' => {'configs' => {cfg_name => cfg1}},
    })
    assert_equal([[], []], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {'configs' => {cfg_name => cfg2}},
    })
    assert_equal([[], []], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {'configs' => {cfg_name => cfg1}},
      'node2' => {'configs' => {cfg_name => cfg2}},
    })
    assert_equal([[], []], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {'configs' => {cfg_name => cfg1}},
      'node2' => {'configs' => {cfg_name => cfg2}},
      'node3' => {'configs' => {cfg_name => cfg2}},
    })
    assert_equal([[], []], fetcher.fetch())

    # local config is older
    fetcher.set_configs_local({cfg_name => cfg1})

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
    })
    assert_equal([[cfg3], []], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
    })
    assert_equal([[cfg4], []], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
      'node3' => {cfg_name => cfg3},
    })
    assert_equal([[cfg3], []], fetcher.fetch())

    # local config is newer
    fetcher.set_configs_local({cfg_name => cfg3})

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg1},
    })
    assert_equal([[], [cfg3]], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg1},
      'node2' => {cfg_name => cfg1},
    })
    assert_equal([[], [cfg3]], fetcher.fetch())

    # local config is the same version
    fetcher.set_configs_local({cfg_name => cfg3})

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
    })
    assert_equal([[], []], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg4},
    })
    assert_equal([[cfg4], []], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
    })
    assert_equal([[cfg4], []], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
      'node3' => {cfg_name => cfg3},
    })
    assert_equal([[], []], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
      'node3' => {cfg_name => cfg4},
    })
    assert_equal([[cfg4], []], fetcher.fetch())

    # local config is the same version
    fetcher.set_configs_local({cfg_name => cfg4})

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
    })
    assert_equal([[cfg3], []], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg4},
    })
    assert_equal([[], []], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
    })
    assert_equal([[], []], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
      'node3' => {cfg_name => cfg3},
    })
    assert_equal([[cfg3], []], fetcher.fetch())

    fetcher.set_configs_cluster({
      'node1' => {cfg_name => cfg3},
      'node2' => {cfg_name => cfg4},
      'node3' => {cfg_name => cfg4},
    })
    assert_equal([[], []], fetcher.fetch())
  end
end
