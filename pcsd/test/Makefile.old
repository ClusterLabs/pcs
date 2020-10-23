this_dir := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
parent_dir := $(shell dirname $(this_dir))
gem_home := $(parent_dir)/vendor/bundle/ruby

test:
	GEM_HOME=$(gem_home) ruby -I$(parent_dir) -I$(this_dir) test_all_suite.rb
