#!/usr/bin/ruby
require 'auth.rb'
require 'highline/import'
require 'optparse'

$user_pass_file = "/var/lib/pcsd/pcs_users.conf"

options = {}
opts = OptionParser.new 
opts.banner = "Usage: pcs_passwd <user> [-p password] [-f pcs password file]"

opts.on("-h", "--help", "Print this usage text") do |o|
  puts opts
  exit
end

opts.on("-p", "--password PASSWORD", "Password to assign user") do |o|
  options[:password] = o
end

opts.on("-f", "--file FILENAME", "Use specified password file") do |o|
  options[:file] = o
end

begin
  opts.parse!
rescue OptionParser::InvalidOption => e
  puts "Error: " + e.to_s()
  puts opts
  exit(1)
end

if ARGV.length == 1
  user = ARGV[0]
  $user_pass_file = options[:file] if options[:file]
  if options[:password]
    password = options[:password]
  else
    password = ask("Password: ") { |q| q.echo = false }
  end
else
  puts "Error: invalid command line"
  puts opts
  exit(1)
end

PCSAuth.createUser(user, password)

