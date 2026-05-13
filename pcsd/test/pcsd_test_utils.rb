CURRENT_DIR = File.expand_path(File.dirname(__FILE__))

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
