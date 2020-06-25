FFI_VERSION="1.13.1"
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
	vendor/cache/backports-3.17.2.gem \
	vendor/cache/ethon-0.12.0.gem \
	vendor/cache/ffi-${FFI_VERSION}.gem \
	vendor/cache/json-2.3.0.gem \
	vendor/cache/mustermann-1.1.1.gem \
	vendor/cache/open4-1.3.4.gem \
	vendor/cache/rack-2.2.3.gem \
	vendor/cache/rack-protection-2.0.8.1.gem \
	vendor/cache/rack-test-1.1.0.gem \
	vendor/cache/ruby2_keywords-0.0.2.gem \
	vendor/cache/sinatra-2.0.8.1.gem \
	vendor/cache/tilt-2.0.10.gem \
	vendor/cache/eventmachine-1.2.7.gem \
	vendor/cache/daemons-1.3.1.gem \
	vendor/cache/thin-1.7.2.gem \
	-- '--with-ldflags="-Wl,-z,now -Wl,-z,relro"'

get_gems:
	bundle package

clean:
	rm -rfv vendor/
