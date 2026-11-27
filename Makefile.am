EXTRA_DIST		= \
			  autogen.sh \
			  CHANGELOG.md \
			  CONTRIBUTING.md \
			  dev_requirements.txt \
			  .gitlab-ci.yml \
			  make/gitlog-to-changelog \
			  make/git-version-gen \
			  make/release.mk \
			  MANIFEST.in \
			  mypy.ini \
			  pcs.pc.in \
			  pyproject.toml \
			  rpm/pcs.spec.in \
			  scripts/pcsd.sh.in \
			  .version

AUTOMAKE_OPTIONS	= foreign

MAINTAINERCLEANFILES	= \
			  aclocal.m4 \
			  autoconf \
			  autoheader \
			  automake \
			  autoscan.log \
			  compile \
			  config.guess \
			  config.sub \
			  configure \
			  configure.scan \
			  depcomp \
			  Gemfile \
			  Gemfile.lock \
			  install-sh \
			  libtool \
			  libtoolize \
			  ltmain.sh \
			  Makefile.in \
			  missing \
			  rpm/requirements.txt

SPEC			= rpm/$(PACKAGE_NAME).spec

# Options passed to configure inside the spec file %build section controlling
# how dependencies are bundled during rpm build. Overridable on the command
# line, e.g. make rpm/pcs.spec SPEC_CONFIGURE_BUNDLE_OPTIONS="--enable-local-build"
SPEC_CONFIGURE_BUNDLE_OPTIONS ?= --enable-local-build --enable-individual-bundling --enable-use-local-cache-only

TARFILES		= $(PACKAGE_NAME)-$(VERSION).tar.bz2 \
			  $(PACKAGE_NAME)-$(VERSION).tar.gz \
			  $(PACKAGE_NAME)-$(VERSION).tar.xz

ACLOCAL_AMFLAGS		= -I m4

SUBDIRS			= pcs pcsd pcs_test data

PCS_PYTHON_PACKAGES = pcs/ pcs_test/
# dependency management

# 1 - sources directory - with python package sources
# 2 - destination directory - python package will be installed into the
#     `packages` subdirectory of this destination directory
# || exit 1 - avoids masking failures in bash for loops
define build_python_bundle
	cd $(1) && \
	PYTHONPATH=$(2)/packages/ \
	LC_ALL=C.utf8 \
	$(PYTHON) setup.py install --install-lib /packages/ --root $(2) || exit 1
endef

PYAGENTX_URI="https://github.com/ondrejmular/pyagentx/archive/v${PYAGENTX_VERSION}.tar.gz"

stamps/download_pyagentx:
if ENABLE_DOWNLOAD
	if [ ! -f ${abs_top_builddir}/rpm/pyagentx-${PYAGENTX_VERSION}.tar.gz ]; then \
		$(WGET) -O ${abs_top_builddir}/rpm/pyagentx-${PYAGENTX_VERSION}.tar.gz ${PYAGENTX_URI}; \
	fi
endif
	touch $@

if PIP_HAS_ISOLATION
pipopts	= --no-build-isolation
endif

stamps/download_python_deps: rpm/requirements.txt stamps/download_pyagentx dev_requirements.txt
if ENABLE_DOWNLOAD
	PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring $(PIP) download --disable-pip-version-check --no-deps $(pipopts) --dest rpm/ --no-binary :all: -r rpm/requirements.txt
endif
	touch $@

stamps/install_python_devel_deps: dev_requirements.txt
if DEV_TESTS
	PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring $(PIP) install --upgrade -r $<
endif
	touch $@

if ENABLE_DOWNLOAD
stamps/untar_python_src: stamps/download_python_deps
else
stamps/untar_python_src:
endif
	$(MKDIR_P) ${abs_top_builddir}/$(PCS_BUNDLED_DIR_LOCAL)/src/
	src=`ls -1 ${abs_top_builddir}/rpm/*.tar.gz ${abs_top_srcdir}/rpm/*.tar.gz 2>/dev/null || true | sort -u | grep -v pcs- || true` && \
	for i in $$src; do \
		$(TAR) xvz -C ${abs_top_builddir}/${PCS_BUNDLED_DIR_LOCAL}/src -f $$i || exit 1; \
	done;
	touch $@

stamps/install_python_embedded_mods_local: stamps/untar_python_src
if LOCAL_BUILD
	for i in ${abs_top_builddir}/$(PCS_BUNDLED_DIR_LOCAL)/src/*; do \
		$(call build_python_bundle,$$i,/${abs_top_builddir}/$(PCS_BUNDLED_DIR_LOCAL)); \
	done;
endif
	touch $@

install_python_embedded_mods:
if LOCAL_BUILD
	for i in ${abs_top_builddir}/$(PCS_BUNDLED_DIR_LOCAL)/src/*; do \
		$(call build_python_bundle,$$i,$(or ${DESTDIR}, /)/$(PCS_BUNDLED_DIR)); \
	done;
endif

stamps/install_ruby_deps_local:
if LOCAL_BUILD
if INSTALL_EMBEDDED_GEMS
if ENABLE_DOWNLOAD
	rm -rf .bundle Gemfile.lock
	$(MKDIR_P) .bundle
	echo '---' > .bundle/config
if INDIVIDUAL_BUNDLING
else
# Vendor every gem into pcsd/vendor/bundle instead of using system gems.
# BUNDLE_PATH makes bundler install all gems there, including ones also
# installed system-wide, producing a self-contained bundle;
# BUNDLE_DISABLE_SHARED_GEMS states that explicitly.
#
# BUNDLE_PATH is essential: without it bundler shares system gems, and then
# a plain `bundle install` silently references a system-installed gem
# instead of vendoring it (incomplete bundle). `bundle install --redownload`
# does not help either: although --redownload is meant to force downloading
# every gem, a gem already present system-wide is not downloaded (contrary
# to what --redownload promises), so the install then fails because its .gem
# file is missing.
	echo 'BUNDLE_DISABLE_SHARED_GEMS: "true"' >> .bundle/config
	echo 'BUNDLE_PATH: "$(PCSD_BUNDLED_DIR_ROOT_LOCAL)"' >> .bundle/config
	echo 'BUNDLE_CACHE_PATH: "$(PCSD_BUNDLED_CACHE_DIR)"' >> .bundle/config
endif
	echo 'BUNDLE_TIMEOUT: 30' >> .bundle/config
	echo 'BUNDLE_RETRY: 30' >> .bundle/config
	echo 'BUNDLE_JOBS: 1' >> .bundle/config
	echo 'BUNDLE_FORCE_RUBY_PLATFORM: "true"' >> .bundle/config
if INDIVIDUAL_BUNDLING
# Individual bundling reuses system gems and bundles only the missing ones,
# so BUNDLE_PATH / vendoring isolation (see the full local build above) is
# intentionally NOT set here - it would vendor a private copy of every gem.
# Bundler has no single option for reusing system gems, so we achieve it by
# pinning the system gems to their installed versions in the Gemfile (done in
# configure.ac); otherwise bundler resolves them to another version and
# downloads it. GEM_HOME/GEM_PATH point bundler at the system gem locations
# plus our vendor dir.
#
# Do NOT add --prefer-local: it makes bundler avoid fetching gems missing
# locally and skews resolution - a missing transitive gem makes it backtrack
# to an ancient version that does not need it (observed: sinatra 1.0 because
# its transitive mustermann dependency was not installed). A plain
# `bundle install` resolves against the remote index and picks newest.
	GEM_HOME="${abs_top_builddir}/${PCSD_BUNDLED_DIR_ROOT_LOCAL}" \
		GEM_PATH="$$GEM_HOME:$$(gem env path)" \
		$(BUNDLE) install
else
	$(BUNDLE) install
	cp -rp $(PCSD_BUNDLED_DIR_LOCAL)/* $(PCSD_BUNDLED_DIR_ROOT_LOCAL)/
	rm -rf $$(realpath $(PCSD_BUNDLED_DIR_LOCAL)/../)
endif
# Remove .bundle so that `bundle exec` (used by pcsd-tests) does not read
# BUNDLE_PATH and instead resolves the gems through GEM_HOME against the
# flattened pcsd/vendor/bundle layout. Gemfile.lock is kept.
	rm -rf .bundle
else
# No bundle resolution happens in a cache-only build, so remove any Gemfile.lock
# left over from a previous full-local/individual build in the same tree. Its
# presence is used (in the $(SPEC) rule) to decide how to generate the
# "Provides: bundled(...)" lines, so a stale one would mislead that detection.
	rm -f Gemfile.lock
	with_cflags=""; \
	if test "x$(ruby_CFLAGS)" != "x"; then \
		with_cflags='--with-cflags=$(ruby_CFLAGS)'; \
	fi; \
	gem_files=`$(FIND) "$(PCSD_BUNDLED_CACHE_DIR)" -type f -name '*.gem'` && \
	if test "x$${gem_files}" != "x"; then \
		$(GEM) install \
			--force --verbose --no-document --local --no-user-install \
			-i "$(PCSD_BUNDLED_DIR_ROOT_LOCAL)" \
			$${gem_files} \
			-- \
			"$${with_cflags}" \
			'--with-ldflags=$(ruby_LIBS)'; \
	fi
endif
endif
	touch $@
endif

stamps/download_rpm_ruby_deps: stamps/install_ruby_deps_local
if ENABLE_DOWNLOAD
	cp ${PCSD_BUNDLED_CACHE_DIR}/*.gem rpm/ || true
endif
	touch $@

install-exec-local: install_python_embedded_mods stamps/install_ruby_deps_local
	$(MKDIR_P) $(or ${DESTDIR}, /)/$(PYTHON_SITELIB)/pcs/
	$(PYTHON) setup.py install --root=$(or ${DESTDIR}, /) ${EXTRA_SETUP_OPTS} --record $(or ${DESTDIR}, /)/$(PYTHON_SITELIB)/pcs/deinstall.txt \
		--install-scripts $(SBINDIR) --install-purelib $(PYTHON_SITELIB) --install-platlib $(PYTHON_SITELIB)
	$(MKDIR_P) ${DESTDIR}/$(LIB_DIR)/pcs
	mv ${DESTDIR}/$(SBINDIR)/pcs_internal ${DESTDIR}/$(LIB_DIR)/pcs/pcs_internal
	mv ${DESTDIR}/$(SBINDIR)/pcs_snmp_agent ${DESTDIR}/$(LIB_DIR)/pcs/pcs_snmp_agent

uninstall-local:
	rm -rf $(or ${DESTDIR}, /)/$(PCS_BUNDLED_DIR)
	mv ${DESTDIR}/$(LIB_DIR)/pcs/pcs_internal ${DESTDIR}/$(SBINDIR)/pcs_internal || :
	mv ${DESTDIR}/$(LIB_DIR)/pcs/pcs_snmp_agent ${DESTDIR}/$(SBINDIR)/pcs_snmp_agent || :
	for i in $(shell cat $(or ${DESTDIR}, /)/$(PYTHON_SITELIB)/pcs/deinstall.txt); do \
		rm -rf $(or ${DESTDIR}, /)/$${i}; \
	done
	rm -rf $(or ${DESTDIR}, /)/$(PYTHON_SITELIB)/pcs/deinstall.txt
	rmdir ${DESTDIR}/$(LIB_DIR)/pcs

dist_doc_DATA	= README.md CHANGELOG.md

pkgconfigdir = $(LIB_DIR)/pkgconfig
pkgconfig_DATA = pcs.pc

# testing

if CONCISE_TESTS
python_test_options =
else
python_test_options = -v --vanilla
endif

ruff_format_check: pyproject.toml
if DEV_TESTS
	$(TIME) ruff --config pyproject.toml format --check ${PCS_PYTHON_PACKAGES}
endif

ruff_format: pyproject.toml
if DEV_TESTS
	$(TIME) ruff --config pyproject.toml check --select I --fix ${PCS_PYTHON_PACKAGES}
	$(TIME) ruff --config pyproject.toml format ${PCS_PYTHON_PACKAGES}
endif

ruff_isort_check: pyproject.toml
if DEV_TESTS
	$(TIME) ruff --config pyproject.toml check --select I ${PCS_PYTHON_PACKAGES}
endif

ruff_isort: pyproject.toml
if DEV_TESTS
	$(TIME) ruff --config pyproject.toml check --select I --fix ${PCS_PYTHON_PACKAGES}
endif

ruff_lint: pyproject.toml
if DEV_TESTS
	$(TIME) ruff --config pyproject.toml check ${PCS_PYTHON_PACKAGES}
endif

mypy:
if DEV_TESTS
	export PYTHONPATH=${abs_top_builddir}/${PCS_BUNDLED_DIR_LOCAL}/packages && \
		$(TIME) $(PYTHON) -m mypy --config-file mypy.ini --package pcs --package pcs_test
endif

RUN_TYPOS=typos --color never --format brief | sed -e 's/:[0-9]\+:[0-9]\+:/:/' | $(SORT)
.PHONY: typos_check
typos_check:
if DEV_TESTS
	$(RUN_TYPOS) > typos_new
	$(DIFF) typos_known typos_new
endif

# Report python modules installed in the bundle (e.g. runtime dependencies
# pulled in by pip) which are not declared in rpm/requirements.txt and thus get
# no rpm Source and bundled() Provides. Declare them with PCS_CHECK_PYMOD in
# configure.ac. Exits with non-zero status if any is found, it is up to the
# caller to treat that as an error or a warning. Not run by the build itself.
# Override BUNDLED_PYTHON_PACKAGES_DIR to check an installed bundle, e.g.
# make bundled_python_deps_check \
#   BUNDLED_PYTHON_PACKAGES_DIR=$DESTDIR/usr/lib64/pcs/pcs_bundled/packages
BUNDLED_PYTHON_PACKAGES_DIR ?= ${abs_top_builddir}/$(PCS_BUNDLED_DIR_LOCAL)/packages
# normalize python package names the way pip does (PEP 503)
NORMALIZE_PYNAME = tr 'A-Z' 'a-z' | sed -E -e 's/[-_.]+/-/g'
.PHONY: bundled_python_deps_check
bundled_python_deps_check:
	@if ! test -d "$(BUNDLED_PYTHON_PACKAGES_DIR)"; then \
		echo "Bundled python packages directory $(BUNDLED_PYTHON_PACKAGES_DIR) not found"; \
		exit 1; \
	fi; \
	declared="`{ sed -E -e 's/[<>=!~;[ ].*//' ${abs_top_builddir}/rpm/requirements.txt 2>/dev/null; echo pyagentx; } \
		| $(NORMALIZE_PYNAME) | $(SORT) -u`"; \
	undeclared="`ls "$(BUNDLED_PYTHON_PACKAGES_DIR)" \
		| sed -n -E -e 's/^(.*)-[^-]+\.dist-info$$/\1/p' \
		| $(NORMALIZE_PYNAME) | $(SORT) -u \
		| $(AWK) -v d="$$declared" 'BEGIN { n = split(d, a, "\n"); for (i = 1; i <= n; i++) known[a[i]] = 1 } !($$0 in known)'`"; \
	if test -n "$$undeclared"; then \
		echo "Python modules bundled but not declared in rpm/requirements.txt (add them with PCS_CHECK_PYMOD):"; \
		echo "$$undeclared" | sed -e 's/^/  /'; \
		exit 1; \
	fi; \
	echo "All bundled python modules are declared"

.PHONY: typos_known
typos_known:
if DEV_TESTS
	$(RUN_TYPOS) > typos_known
endif

tests_tier0:
	export PYTHONPATH=${abs_top_builddir}/${PCS_BUNDLED_DIR_LOCAL}/packages && \
		$(PYTHON) ${abs_builddir}/pcs_test/suite.py ${python_test_options} --tier0

tests_tier1:
if EXECUTE_TIER1_TESTS
	export PYTHONPATH=${abs_top_builddir}/${PCS_BUNDLED_DIR_LOCAL}/packages && \
		$(PYTHON) ${abs_builddir}/pcs_test/suite.py $(python_test_options) --tier1
endif

pcsd-tests:
	GEM_HOME=${abs_top_builddir}/${PCSD_BUNDLED_DIR_ROOT_LOCAL} \
		$(BUNDLE) exec $(RUBY) \
		-I${abs_top_builddir}/pcsd \
		-I${abs_top_builddir}/pcsd/test \
		${abs_top_builddir}/pcsd/test/test_all_suite.rb

if LOCAL_BUILD
check-local-deps: stamps/install_python_embedded_mods_local stamps/install_ruby_deps_local stamps/install_python_devel_deps
else
check-local-deps:
endif

all: check-local-deps

test-tree-prep:
	if [ "${abs_top_builddir}" != "${abs_top_srcdir}" ]; then \
		echo "Generating builddir symlinks for testing"; \
		src_realpath=$(shell realpath ${abs_top_srcdir}); \
		for i in `find "$$src_realpath/" -type d | \
			grep -v "${abs_top_builddir}" | \
			sed -e 's#^'$$src_realpath'/##g'`; do \
			$(MKDIR_P) ${abs_top_builddir}/$${i}; \
		done; \
		find "$$src_realpath/" -type f | { while read src; do \
			process=no; \
			copy=no; \
			case $$src in \
				${abs_top_builddir}*) \
					;; \
				*Makefile.*|*.in) \
					;; \
				*pcs_test/resources/*.conf) \
					copy=yes; \
					;; \
				*pcs_test/resources/qdevice-certs*) \
					copy=yes; \
					;; \
				*pcsd/test/*.conf*) \
					copy=yes; \
					;; \
				*) \
					process=yes; \
					;; \
			esac ; \
			dst=`echo $$src | sed -e 's#^'$$src_realpath'/##g'`; \
			if [ $${process} == yes ]; then \
				rm -f ${abs_top_builddir}/$$dst; \
				$(LN_S) $$src ${abs_top_builddir}/$$dst; \
			fi; \
			if [ $${copy} == yes ]; then \
				rm -f ${abs_top_builddir}/$$dst; \
				cp $$src ${abs_top_builddir}/$$dst; \
				chmod u+w ${abs_top_builddir}/$$dst; \
			fi; \
		done; }; \
	fi

test-tree-clean:
	if [ "${abs_top_builddir}" != "${abs_top_srcdir}" ]; then \
		echo "Cleaning symlinks for testing" ; \
		find "${abs_top_builddir}/" -type l -delete; \
		find ${abs_top_builddir} -type d -name qdevice-certs -exec rm -rf {} \; 2>/dev/null || : ;\
		find ${abs_top_builddir} -type f -name "*.conf*" -exec rm -rf {} \; 2>/dev/null || : ;\
		find "${abs_top_builddir}/" -type d -empty -delete; \
	fi
	find ${abs_top_builddir} -type d -name __pycache__ -exec rm -rf {} \; 2>/dev/null || :

check-local: check-local-deps test-tree-prep typos_check ruff_lint ruff_isort_check ruff_format_check mypy tests_tier0 tests_tier1 pcsd-tests test-tree-clean

clean-local: test-tree-clean
	$(PYTHON) setup.py clean
	rm -rf Gemfile.lock .bundle pcs_test/resources/temp
	rm -rf $(PACKAGE_NAME)-$(VERSION).tar.* rpm/*tar* rpm/*.gem rpm/*.rpm
	rm -rf stamps/*

# this will get rid of "libtoolized" m4 files
distclean-local:
	rm -rf Gemfile
	rm -rf .mypy_cache
	rm -rf rpm/requirements.txt rpm/py_buildrequires.txt rpm/py_requires.txt rpm/bundle_buildrequires.txt rpm/gem_requirements.txt rpm/gem_requirements_default.txt rpm/gem_requires.txt rpm/Gemfile rpm/pcs-*
	rm -rf stamps
	rm -rf ${abs_top_builddir}/${PCS_BUNDLED_DIR_LOCAL} ${abs_top_builddir}/${PCSD_BUNDLED_DIR_ROOT_LOCAL}
	rm -rf $(filter-out \
	         $(top_builddir)/m4/ac_compare_versions.m4 \
	         $(top_builddir)/m4/ac_pip_module.m4 \
		 $(top_builddir)/m4/ac_ruby_gem.m4 \
		 $(top_builddir)/m4/ax_prog_date.m4 \
		 $(top_builddir)/m4/pcs_buildreq.m4, \
		 $(wildcard $(top_builddir)/m4/*.m4))

# release/versioning
BUILT_SOURCES	= .version
.version:
	echo $(VERSION) > $@-t && mv $@-t $@

dist-hook: gen-ChangeLog
	echo $(VERSION) > $(distdir)/.tarball-version
	echo $(SOURCE_EPOCH) > $(distdir)/source_epoch

gen_start_date = 2000-01-01
.PHONY: gen-ChangeLog
gen-ChangeLog:
	if test -d $(abs_srcdir)/.git; then				\
		LC_ALL=C $(top_srcdir)/make/gitlog-to-changelog		\
			--since=$(gen_start_date) > $(distdir)/cl-t;	\
		rm -f $(distdir)/ChangeLog;				\
		mv $(distdir)/cl-t $(distdir)/ChangeLog;		\
	fi

## make rpm/srpm section.

# awk program generating the rpm "Provides: bundled(rubygem-<gem>) = <version>"
# lines (the rubygem-<gem> package name form, as used by Fedora rubygems)
# from Gemfile.lock. It prints one Provides for every gem resolved in the
# Gemfile.lock "GEM/specs:" section, except gems listed in the
# rpm/gem_requirements*.txt files - those are used from the system and are
# already emitted as "Requires: rubygem(<gem>)". The requirements files must be
# passed to awk before Gemfile.lock so the skip set is complete when parsing it.
define GEMBUNDLE_AWK
# collect system gems to skip (requirements files hold one bare name per line)
	FILENAME ~ /gem_requirements/ { skip[$$1] = 1; next }
# track the GEM/specs: section of Gemfile.lock
	/^GEM$$/ { in_gem = 1; next }
	/^[A-Za-z]/ { in_gem = 0 }
	in_gem && /^  specs:/ { in_specs = 1; next }
# Every resolved gem (direct or transitive) is a 4-space line carrying its
# exact version. The 6-space lines under it are that gem's dependency
# declarations (name + version constraint, not a resolved version) and only
# repeat gems that already have their own 4-space line, so match 4 spaces only.
	in_gem && in_specs && /^    [^ ]/ {
		line = $$0
		sub(/^    /, "", line)
		name = line; sub(/ .*/, "", name)
		version = line; sub(/^[^(]*\(/, "", version); sub(/\).*/, "", version)
		if (!(name in skip)) print "Provides: bundled(rubygem-" name ") = " version
	}
endef
export GEMBUNDLE_AWK

# awk program generating the rpm "Provides: bundled(python3dist(<module>)) =
# <version>" lines for the bundled python modules, module names normalized the
# way rpm python3dist() names are (lowercase, runs of "-", "_", "." become "-").
# It is fed the rpm/py_buildrequires.txt file first (one
# "python3dist(<name>) ..." per line) to build the set of modules used
# from the system, then the bundled tarball basenames ("<name>-<version>") on
# stdin ("-"); it prints a Provides for every bundled module except the system
# ones (already emitted as "Requires: python3dist(<module>)") and dataclasses.
define PYBUNDLE_AWK
# collect system modules to skip from py_buildrequires.txt
	FILENAME != "-" {
		line = $$0
		sub(/^python3dist\(/, "", line)
		sub(/\).*/, "", line)
		line = tolower(line); gsub(/[-_.]+/, "-", line)
		skip[line] = 1
		next
	}
# remaining input lines are bundled tarball basenames: <name>-<version>
	/^dataclasses-/ { next }
	NF {
		name = $$0; sub(/-[^-]*$$/, "", name)
		version = $$0; sub(/^.*-/, "", version)
		name = tolower(name); gsub(/[-_.]+/, "-", name)
		if (!(name in skip)) print "Provides: bundled(python3dist(" name ")) = " version
	}
endef
export PYBUNDLE_AWK

# Track the values of make variables that only affect $(SPEC) from inside its
# recipe (SPEC_CONFIGURE_BUNDLE_OPTIONS, CI_BRANCH) in stamp files so that
# $(SPEC) can depend on them as normal file prerequisites. Each stamp recipe
# runs on every make invocation (it depends on the phony FORCE target), but it
# only rewrites the stamp file - bumping its timestamp - when the value actually
# changes. That way changing one of these variables on the command line forces
# the spec to be regenerated, while repeated builds with unchanged values do
# not.
.PHONY: FORCE
FORCE:

stamps/spec_configure_bundle_options: FORCE
	@if [ ! -f $@ ] || [ "`cat $@`" != "$(SPEC_CONFIGURE_BUNDLE_OPTIONS)" ]; then \
		echo "$(SPEC_CONFIGURE_BUNDLE_OPTIONS)" > $@; \
	fi

stamps/spec_ci_branch: FORCE
	@if [ ! -f $@ ] || [ "`cat $@`" != "$(CI_BRANCH)" ]; then \
		echo "$(CI_BRANCH)" > $@; \
	fi

$(SPEC): $(SPEC).in .version config.status stamps/download_python_deps stamps/download_rpm_ruby_deps stamps/spec_configure_bundle_options stamps/spec_ci_branch
	rm -f $@-t $@
	date="`LC_ALL=C $(UTC_DATE_AT)$(SOURCE_EPOCH) "+%a %b %d %Y"`" && \
	gvgver="`cd $(abs_srcdir); make/git-version-gen --fallback $(VERSION) .tarball-version .gitarchivever`" && \
	if [ "$$gvgver" = "`echo $$gvgver | sed 's/-/./'`" ];then \
		rpmver="$$gvgver" && \
		alphatag="" && \
		dirty="" && \
		numcomm="0"; \
	else \
		gitver="`echo $$gvgver | sed 's/\(.*\)+/\1-/'`" && \
		rpmver=`echo $$gitver | sed 's/-.*//g'` && \
		alphatag=`echo $$gvgver | sed 's/[^-]*-\([^-]*\).*/\1/'` && \
		numcomm=`echo $$gitver | sed 's/[^-]*-\([^-]*\).*/\1/'` && \
		dirty="" && \
		if [ "`echo $$gitver | sed 's/^.*-dirty$$//g'`" = "" ];then \
			dirty="dirty"; \
		fi \
	fi && \
	if [ -n "$$dirty" ]; then dirty="dirty"; else dirty=""; fi && \
	if [ "$$numcomm" = "0" ]; then \
		sed \
			-e "s#@version@#$$rpmver#g" \
			-e "s#%global\s\+alphatag.*##g" \
			-e "s#%global\s\+numcomm.*##g" \
			-e "s#@dirty@#$$dirty#g" \
			-e "s#@date@#$$date#g" \
			-e "s#@pcs_bundled_dir@#${PCS_BUNDLED_DIR_LOCAL}#g" \
			-e "s#@specconfigurebundleoptions@#$(SPEC_CONFIGURE_BUNDLE_OPTIONS)#g" \
		$(abs_srcdir)/$@.in > $@-t; \
	else \
		sed \
			-e "s#@version@#$$rpmver#g" \
			-e "s#@alphatag@#$$alphatag#g" \
			-e "s#@numcomm@#$$numcomm#g" \
			-e "s#@dirty@#$$dirty#g" \
			-e "s#@date@#$$date#g" \
			-e "s#@pcs_bundled_dir@#${PCS_BUNDLED_DIR_LOCAL}#g" \
			-e "s#@specconfigurebundleoptions@#$(SPEC_CONFIGURE_BUNDLE_OPTIONS)#g" \
		$(abs_srcdir)/$@.in > $@-t; \
	fi; \
	if [ -z "$(CI_BRANCH)" ]; then \
		sed -i -e "s#%glo.*cibranch.*##g" $@-t; \
	else \
		sed -i -e "s#@cibranch@#$(CI_BRANCH)#g" $@-t; \
	fi && \
	if [ -z "$$dirty" ]; then sed -i -e "s#%glo.*dirty.*##g" $@-t; fi && \
	sed -i -e "s#@pyagentx_version@#${PYAGENTX_VERSION}#g" $@-t && \
	pylist="`ls rpm/*.tar.gz | grep -v ^rpm/pyagentx- | grep -v ^rpm/pcs- | sed -e 's#rpm/##g' -e 's#.tar.gz##'`" && \
	pysrc="`base=42; for i in $$pylist; do echo 'Source'$$base': '$$i'.tar.gz' && let "base=base+1"; done`" && \
	$(AWK) -i inplace -v r="$$pysrc" '{gsub(/@pysrc@/,r)}1' $@-t; \
	pybreqfile=rpm/py_buildrequires.txt; test -f $$pybreqfile || pybreqfile=/dev/null; \
	pybundle="`echo "$$pylist" | tr ' ' '\n' | $(AWK) "$$PYBUNDLE_AWK" $$pybreqfile -`" && \
	$(AWK) -i inplace -v r="$$pybundle" '{gsub(/@pybundle@/,r)}1' $@-t; \
	pycache="`echo $(MKDIR_P) $(PCS_BUNDLED_DIR_LOCAL)/src; base=41; for i in $$pylist pyagentx; do echo 'cp -f %SOURCE'$$base' rpm/' && let "base=base+1"; done`" && \
	$(AWK) -i inplace -v r="$$pycache" '{gsub(/@pycache@/,r)}1' $@-t; \
	gemlist="`for i in $$($(FIND) rpm/ -type f -name '*.gem'); do echo $$i | sed -e 's#rpm/##g' -e 's#.gem##g'; done`" && \
	gemsrc="`base=80; for i in $$gemlist; do echo 'Source'$$base': '$$i'.gem' && let "base=base+1"; done`" && \
	$(AWK) -i inplace -v r="$$gemsrc" '{gsub(/@gemsrc@/,r)}1' $@-t; \
	gemreqfiles=""; \
	for f in rpm/gem_requirements_default.txt rpm/gem_requirements.txt; do \
		test -f $$f && gemreqfiles="$$gemreqfiles $$f"; \
	done; \
	if test -f Gemfile.lock; then \
		gembundle="$$($(AWK) "$$GEMBUNDLE_AWK" $$gemreqfiles Gemfile.lock)"; \
	else \
		gembundle="$$($(FIND) $(PCSD_BUNDLED_CACHE_DIR) rpm/ -type f -name '*.gem' 2>/dev/null \
			| sed -e 's#.*/##' -e 's#\.gem$$##' -e 's/\(.*\)-\(.*\)/Provides: bundled(rubygem-\1) = \2/' \
			| sort -u)"; \
	fi && \
	$(AWK) -i inplace -v r="$$gembundle" '{gsub(/@gembundle@/,r)}1' $@-t; \
	gemcache="`echo $(MKDIR_P) $(PCSD_BUNDLED_CACHE_DIR); base=80; for i in $$gemlist; do echo 'cp -f %SOURCE'$$base' $(PCSD_BUNDLED_CACHE_DIR)' && let "base=base+1"; done`" && \
	$(AWK) -i inplace -v r="$$gemcache" '{gsub(/@gemcache@/,r)}1' $@-t;
	gemreqlist="`for f in rpm/gem_requirements_default.txt rpm/gem_requirements.txt; do test -f $$f && cat $$f; done`" && \
		gembuildreqs="`for i in $$gemreqlist; do echo 'BuildRequires: rubygem('$$i')'; done`" && \
		$(AWK) -i inplace -v r="$$gembuildreqs" '{gsub(/@gembuildreqs@/,r)}1' $@-t; \
		gemrequires="`test -f rpm/gem_requires.txt && sed -e 's/^\(.*\)$$/Requires: rubygem(\1)/' rpm/gem_requires.txt || true`" && \
		$(AWK) -i inplace -v r="$$gemrequires" '{gsub(/@gemrequires@/,r)}1' $@-t;
	bundlebuildreqs="`test -f rpm/bundle_buildrequires.txt && sed -e 's/^/BuildRequires: /' rpm/bundle_buildrequires.txt || true`" && \
		$(AWK) -i inplace -v r="$$bundlebuildreqs" '{gsub(/@bundlebuildreqs@/,r)}1' $@-t;
	pybuildreqs="`test -f rpm/py_buildrequires.txt && sed -e 's/^/BuildRequires: /' rpm/py_buildrequires.txt || true`" && \
		$(AWK) -i inplace -v r="$$pybuildreqs" '{gsub(/@pybuildreqs@/,r)}1' $@-t; \
		pyrequires="`test -f rpm/py_requires.txt && sed -e 's/^/Requires: /' rpm/py_requires.txt || true`" && \
		$(AWK) -i inplace -v r="$$pyrequires" '{gsub(/@pyrequires@/,r)}1' $@-t;
	chmod a-w $@-t
	mv $@-t $@
	rm -f $@-t*

$(TARFILES):
	$(MAKE) dist
	cp $(TARFILES) $(abs_top_builddir)/rpm

RPMBUILDOPTS    = --define "_sourcedir $(abs_top_builddir)/rpm" \
		  --define "_specdir $(abs_top_builddir)/rpm" \
		  --define "_builddir $(abs_top_builddir)/rpm" \
		  --define "_srcrpmdir $(abs_top_builddir)/rpm" \
		  --define "_rpmdir $(abs_top_builddir)/rpm"

srpm: clean
	$(MAKE) $(SPEC) $(TARFILES)
	rpmbuild $(RPMBUILDOPTS) --nodeps -bs $(SPEC)

rpm: clean
	$(MAKE) $(SPEC) $(TARFILES)
	rpmbuild $(RPMBUILDOPTS) -ba $(SPEC)

clean-generic:
	rm -rf $(SPEC) $(TARFILES) $(PACKAGE_NAME)-$(VERSION) *.rpm
