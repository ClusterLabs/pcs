require 'test/unit'
require 'fileutils'

require 'pcsd_test_utils.rb'
require 'cfgsync.rb'
require 'config.rb'


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
