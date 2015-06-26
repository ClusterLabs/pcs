CURRENT_DIR = File.expand_path(File.dirname(__FILE__))
CFG_COROSYNC_CONF = File.join(CURRENT_DIR, "corosync.conf.tmp")
CFG_CLUSTER_CONF = File.join(CURRENT_DIR, "cluster.conf.tmp")
CFG_PCSD_SETTINGS = File.join(CURRENT_DIR, "pcs_settings.conf.tmp")
CFG_PCSD_USERS = File.join(CURRENT_DIR, "pcs_users.conf.tmp")
CFG_PCSD_TOKENS = File.join(CURRENT_DIR, 'tokens.tmp')

CFG_SYNC_CONTROL = File.join(CURRENT_DIR, 'cfgsync_ctl.tmp')

class MockLogger
  attr_reader :log

  def initialize
    @log = []
  end

  def clean
    @log = []
  end

  ['fatal', 'error', 'warn', 'info', 'debug'].each { |level|
    define_method(level) { |message|
      @log << [level, message]
      return self
    }
  }
end
