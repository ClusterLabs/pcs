#!/usr/bin/ruby
require 'auth.rb'
require 'highline/import'
USER_FILE = "/var/lib/pcs-gui/pcs_users.conf"

def usage()
  puts "Usage: pcs_passwd <accountName> [pcs password file]"
end

if ARGV.length == 2
  USER_FILE = ARGV[1]
elsif ARGV.length != 1
  usage()
  exit
end

password = ask("Password: ") { |q| q.echo = false }
PCSAuth.createUser(ARGV[0], password)

