require 'test/unit'
require 'fileutils'

CURRENT_DIR = File.expand_path(File.dirname(__FILE__))
CFG_COROSYNC_CONF = File.join(CURRENT_DIR, "corosync.conf.tmp")
CFG_CLUSTER_CONF = File.join(CURRENT_DIR, "cluster.conf.tmp")
CFG_PCSD_SETTINGS = File.join(CURRENT_DIR, "pcs_settings.conf.tmp")
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

    cfg.text = '<cluster config_version="4" name="test1"/>'
    assert_equal(4, cfg.version)
    assert_equal("a49b848fc173ddb0821009170a653561fa1d82a6", cfg.hash)
  end

  def test_file()
    cfg = Cfgsync::ClusterConf.from_file()
    assert_equal(9, cfg.version)
    assert_equal("198bda4b748ef646de867cb850cd3ad208c36d8b", cfg.hash)
  end
end
