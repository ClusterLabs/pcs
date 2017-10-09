FFI_VERSION="1.9.18"
FFI_C_DIR=vendor/bundle/ruby/gems/ffi-${FFI_VERSION}/ext/ffi_c

build_gems: get_gems
	bundle install --local --deployment
	#ffi makes symlink with absolute path. Let's change it to relative path.
	for fname in `ls ${FFI_C_DIR}/libffi-*/include/ffitarget.h`; do \
		if [[ -L "$$fname" ]]; then \
			target=$$(readlink $$fname | sed "s~.*/${FFI_C_DIR}\(/libffi/src/[^/]\+/ffitarget.h\)~../..\1~"); \
			rm $$fname; \
			ln -s $$target $$fname; \
		fi; \
	done;

# RHEL6 needs special rpam-ruby19 gem to work with 1.8.7
# also bundler is not available on RHEL6 in rpm
build_gems_rhel6:
	mkdir -p vendor/bundle/ruby
	gem install --verbose --no-rdoc --no-ri -l -i vendor/bundle/ruby \
	vendor/cache/backports-3.6.8.gem \
	vendor/cache/ethon-0.9.1.gem \
	vendor/cache/ffi-${FFI_VERSION}.gem \
	vendor/cache/json-2.0.3.gem \
	vendor/cache/multi_json-1.12.1.gem \
	vendor/cache/open4-1.3.4.gem \
	vendor/cache/orderedhash-0.0.6.gem \
	vendor/cache/rack-1.6.4.gem \
	vendor/cache/rack-protection-1.5.3.gem \
	vendor/cache/rack-test-0.6.3.gem \
	vendor/cache/rpam-ruby19-feist-1.2.1.1.gem \
	vendor/cache/sinatra-1.4.8.gem \
	vendor/cache/sinatra-contrib-1.4.7.gem \
	vendor/cache/tilt-2.0.6.gem \
	-- '--with-ldflags="-Wl,-z,now -Wl,-z,relro"'

get_gems:
	bundle package

clean:
	rm -rfv vendor/
