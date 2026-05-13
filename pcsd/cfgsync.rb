require 'fileutils'
require 'rexml/document'
require 'digest/sha1'

require 'settings.rb'
require 'config.rb'
require 'corosyncconf.rb'

CFG_SYNC_CONTROL = File.join(PCSD_VAR_LOCATION, 'cfgsync_ctl') unless defined? CFG_SYNC_CONTROL

module Cfgsync
  class Config
    include Comparable

    # set @name, @file_path, @file_perm in ancestors
    class << self
      attr_reader :name, :file_path, :file_perm
    end

    def self.from_text(text)
      return self.new(text)
    end

    def self.from_file(default=nil)
      begin
        return self.on_file_missing(default) if not File::exist?(@file_path)
        file = nil
        file = File.open(@file_path, File::RDONLY)
        file.flock(File::LOCK_SH)
        return self.from_text(file.read())
      rescue => e
        return self.on_file_read_error(e, default)
      ensure
        unless file.nil?
          file.flock(File::LOCK_UN)
          file.close()
        end
      end
    end

    def self.exist?()
      return File::exist?(@file_path)
    end

    def self.backup()
      begin
        FileUtils.cp(@file_path, @file_path + "." + Time.now.to_i.to_s)
      rescue => e
        $logger.debug("Exception when backing up config '#{self.name}': #{e}")
        return
      end
      begin
        self.remove_old_backups()
      rescue => e
        $logger.debug("Exception when removing old backup files: #{e}")
      end
    end

    def self.remove_old_backups()
      backup_files = []
      Dir.glob(@file_path + '.*') { |path|
        if File.file?(path)
          match = path.match(/^#{@file_path}\.(\d+)$/)
          if match
            backup_files << [match[1].to_i(), path]
          end
        end
      }
      backup_count = Cfgsync::file_backup_count()
      to_delete = backup_files.sort()[0..-(backup_count + 1)]
      return if not to_delete
      to_delete.each { |timestamp, path|
        File.delete(path)
      }
    end

    def text()
      return @text
    end

    def text=(text)
      @text = text
      self.clean_cache()
      return self
    end

    def hash()
      return @hash ||= self.get_hash()
    end

    def version()
      return @version ||= self.get_version().to_i()
    end

    def version=(new_version)
      self.text = self.set_version(new_version)
      return self
    end

    def save()
      begin
        file = nil
        file = File.open(self.class.file_path, 'w', self.class.file_perm)
        file.flock(File::LOCK_EX)
        file.write(self.text)
        $logger.info(
          "Saved config '#{self.class.name}' version #{self.version} #{self.hash} to '#{self.class.file_path}'"
        )
      rescue => e
        $logger.error(
          "Cannot save config '#{self.class.name}': #{e.message}"
        )
        raise
      ensure
        unless file.nil?
          file.flock(File::LOCK_UN)
          file.close()
        end
      end
    end

    def <=>(other)
      if self.version == other.version
        return self.hash <=> other.hash
      else
        return self.version <=> other.version
      end
    end

    protected

    def self.on_file_missing(default)
      $logger.warn(
        "Cannot read config '#{@name}' from '#{@file_path}': No such file"
      )
      return self.from_text(default) if default
      raise SystemCallError.new(@file_path, Errno::ENOENT::Errno)
    end

    def self.on_file_read_error(exception, default)
      $logger.warn(
        "Cannot read config '#{@name}' from '#{@file_path}': #{exception.message}"
      )
      return self.from_text(default) if default
      raise exception
    end

    def initialize(text)
      self.text = text
    end

    def clean_cache()
      @hash = nil
      @version = nil
      return self
    end

    def get_hash()
      return Digest::SHA1.hexdigest(self.text || '')
    end
  end


  def self.get_integer_value(value, default, minimum)
    return default if value.nil?
    if value.respond_to?(:match)
      return default if not value.match(/\A\s*[+-]?\d+\Z/)
    end
    return default if not value.respond_to?(:to_i)
    numeric = value.to_i()
    return minimum if numeric < minimum
    return numeric
  end

  def self.file_backup_count()
    begin
      file = nil
      file = File.open(CFG_SYNC_CONTROL, File::RDONLY)
      file.flock(File::LOCK_SH)
      parsed_file = JSON.parse(file.read())
      return get_integer_value(parsed_file["file_backup_count"], 50, 0)
    rescue => e
      $logger.debug("Cannot read config '#{CFG_SYNC_CONTROL}': #{e.message}")
      return 50 # default
    ensure
      unless file.nil?
        file.flock(File::LOCK_UN)
        file.close()
      end
    end
  end

end
