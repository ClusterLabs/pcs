this_dir := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
parent_dir := $(shell dirname $(this_dir))

test:
	ruby -I$(parent_dir) -I$(this_dir) test_all_suite.rb
