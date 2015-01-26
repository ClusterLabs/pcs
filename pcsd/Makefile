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
	gem install --no-rdoc --no-ri -l -i vendor/bundle/ruby vendor/cache/rack-1.5.2.gem vendor/cache/open4-1.3.4.gem vendor/cache/highline-1.6.20.gem vendor/cache/rack-test-0.6.2.gem vendor/cache/backports-3.6.4.gem vendor/cache/multi_json-1.10.1.gem vendor/cache/tilt-1.4.1.gem vendor/cache/rack-protection-1.5.3.gem vendor/cache/sinatra-1.4.5.gem vendor/cache/rhel6-only/json-1.8.1.gem vendor/cache/rhel6-only/rpam-ruby19-feist-1.2.1.1.gem vendor/cache/rhel6-only/json-1.8.1.gem vendor/cache/monkey-lib-0.5.4.gem vendor/cache/sinatra-contrib-1.4.2.gem vendor/cache/eventmachine-1.0.3.gem vendor/cache/sinatra-sugar-0.5.1.gem

get_gems:
	bundle package

