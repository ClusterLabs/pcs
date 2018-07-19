FFI_VERSION="1.9.25"
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

build_gems_without_bundler:
	mkdir -p vendor/bundle/ruby
	gem install --verbose --no-rdoc --no-ri -l --ignore-dependencies -i vendor/bundle/ruby \
	vendor/cache/activesupport-5.2.0.gem \
	vendor/cache/backports-3.11.3.gem \
	vendor/cache/concurrent-ruby-1.0.5.gem \
	vendor/cache/ethon-0.11.0.gem \
	vendor/cache/ffi-${FFI_VERSION}.gem \
	vendor/cache/i18n-1.0.1.gem \
	vendor/cache/json-2.1.0.gem \
	vendor/cache/minitest-5.11.3.gem \
	vendor/cache/multi_json-1.13.1.gem \
	vendor/cache/musterman-1.0.2.gem \
	vendor/cache/open4-1.3.4.gem \
	vendor/cache/rack-2.0.5.gem \
	vendor/cache/rack-protection-2.0.3.gem \
	vendor/cache/rack-test-1.0.0.gem \
	vendor/cache/sinatra-2.0.3.gem \
	vendor/cache/sinatra-contrib-2.0.3.gem \
	vendor/cache/thread_safe-0.3.6.gem \
	vendor/cache/tilt-2.0.8.gem \
	vendor/cache/tzinfo-1.2.5.gem \
	-- '--with-ldflags="-Wl,-z,now -Wl,-z,relro"'

get_gems:
	bundle package

clean:
	rm -rfv vendor/
