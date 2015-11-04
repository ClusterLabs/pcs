build_gems: get_gems
	bundle install --local --deployment

# RHEL6 needs special rpam-ruby19 gem to work with 1.8.7
# also bundler is not available on RHEL6 in rpm
build_gems_rhel6:
	mkdir -p vendor/bundle/ruby
	gem install --verbose --no-rdoc --no-ri -l -i vendor/bundle/ruby vendor/cache/backports-3.6.4.gem vendor/cache/eventmachine-1.0.7.gem vendor/cache/json-1.8.3.gem vendor/cache/monkey-lib-0.5.4.gem vendor/cache/multi_json-1.11.1.gem vendor/cache/open4-1.3.4.gem vendor/cache/orderedhash-0.0.6.gem vendor/cache/rack-1.6.4.gem vendor/cache/rack-protection-1.5.3.gem vendor/cache/rack-test-0.6.3.gem vendor/cache/rpam-ruby19-feist-1.2.1.1.gem vendor/cache/tilt-1.4.1.gem vendor/cache/sinatra-1.4.6.gem vendor/cache/sinatra-contrib-1.4.4.gem vendor/cache/sinatra-sugar-0.5.1.gem -- '--with-ldflags="-Wl,-z,now -Wl,-z,relro"'

get_gems:
	bundle package

clean:
	rm -rfv vendor/
