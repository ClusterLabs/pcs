REL_INFO := $(shell grep -q -i "release 6" /etc/redhat-release ; echo $$?)

ifeq (${REL_INFO},1)
  build_gems: build_gems_normal
else
  build_gems: build_gems_rhel6
endif

build_gems_normal:
	bundle install --local --deployment

# RHEL6 needs special rpam-ruby19 gem to work with 1.8.7
build_gems_rhel6:
	mkdir -p vendor/bundle/ruby
	find vendor/cache -type f | grep -v rpam-ruby19-1 | xargs gem install --no-rdoc --no-ri -i vendor/bundle/ruby

get_gems:
	bundle package

