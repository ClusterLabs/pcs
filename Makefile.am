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
			  pylintrc \
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
define build_python_bundle
	cd $(1) && \
	PYTHONPATH=$(2)/packages/ \
	LC_ALL=C.utf8 \
	$(PYTHON) setup.py install --install-lib /packages/ --root $(2)
endef

PYAGENTX_URI="https://github.com/ondrejmular/pyagentx/archive/v${PYAGENTX_VERSION}.tar.gz"

stamps/download_pyagentx:
if ENABLE_DOWNLOAD
	if [ ! -f ${abs_top_builddir}/rpm/pyagentx-${PYAGENTX_VERSION}.tar.gz ]; then \
		$(WGET) -q -O ${abs_top_builddir}/rpm/pyagentx-${PYAGENTX_VERSION}.tar.gz ${PYAGENTX_URI}; \
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
		$(TAR) xvz -C ${abs_top_builddir}/${PCS_BUNDLED_DIR_LOCAL}/src -f $$i; \
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
	echo 'BUNDLE_DISABLE_SHARED_GEMS: "true"' >> .bundle/config
	echo 'BUNDLE_PATH: "$(PCSD_BUNDLED_DIR_ROOT_LOCAL)"' >> .bundle/config
	echo 'BUNDLE_CACHE_PATH: "$(PCSD_BUNDLED_CACHE_DIR)"' >> .bundle/config
	echo 'BUNDLE_BUILD: \"$(ruby_LIBS)\"' >> .bundle/config
	echo 'BUNDLE_TIMEOUT: 30' >> .bundle/config
	echo 'BUNDLE_RETRY: 30' >> .bundle/config
	echo 'BUNDLE_JOBS: 1' >> .bundle/config
	$(BUNDLE)
	cp -rp $(PCSD_BUNDLED_DIR_LOCAL)/* $(PCSD_BUNDLED_DIR_ROOT_LOCAL)/
	rm -rf $$(realpath $(PCSD_BUNDLED_DIR_LOCAL)/../)
	rm -rf .bundle Gemfile.lock
else
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

# testing

if CONCISE_TESTS
python_test_options =
else
python_test_options = -v --vanilla
endif

pylint:
if DEV_TESTS
if PARALLEL_PYLINT
pylint_options = --jobs=0
else
pylint_options =
endif
	export PYTHONPATH=${abs_top_builddir}/${PCS_BUNDLED_DIR_LOCAL}/packages && \
		$(TIME) $(PYTHON) -m pylint --rcfile pylintrc --persistent=n --reports=n --score=n --disable similarities ${pylint_options} ${PCS_PYTHON_PACKAGES}
endif

isort_check: pyproject.toml
if DEV_TESTS
	export PYTHONPATH=${abs_top_builddir}/${PCS_BUNDLED_DIR_LOCAL}/packages && \
		$(TIME) $(PYTHON) -m isort --check-only ${PCS_PYTHON_PACKAGES}
endif

isort: pyproject.toml
if DEV_TESTS
	export PYTHONPATH=${abs_top_builddir}/${PCS_BUNDLED_DIR_LOCAL}/packages && \
		$(TIME) $(PYTHON) -m isort ${PCS_PYTHON_PACKAGES}
endif

black_check: pyproject.toml
if DEV_TESTS
	export PYTHONPATH=${abs_top_builddir}/${PCS_BUNDLED_DIR_LOCAL}/packages && \
		$(TIME) $(PYTHON) -m black --config pyproject.toml --check ${PCS_PYTHON_PACKAGES}
endif

black: pyproject.toml
if DEV_TESTS
	export PYTHONPATH=${abs_top_builddir}/${PCS_BUNDLED_DIR_LOCAL}/packages && \
		$(PYTHON) -m black --config pyproject.toml ${PCS_PYTHON_PACKAGES}
endif

mypy:
if DEV_TESTS
	export PYTHONPATH=${abs_top_builddir}/${PCS_BUNDLED_DIR_LOCAL}/packages && \
		$(TIME) $(PYTHON) -m mypy --config-file mypy.ini --package pcs --package pcs_test
endif

RUN_TYPOS=$(TYPOS) --color never --format brief | sed -e 's/:[0-9]\+:[0-9]\+:/:/' | $(SORT)
.PHONY: typos_check
typos_check:
if TYPOS_CHECK
	$(RUN_TYPOS) > typos_new
	$(DIFF) typos_known typos_new
endif

.PHONY: typos_known
typos_known:
if TYPOS_CHECK
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
		$(RUBY) \
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

check-local: check-local-deps test-tree-prep typos_check pylint isort_check black_check mypy tests_tier0 tests_tier1 pcsd-tests test-tree-clean

clean-local: test-tree-clean
	$(PYTHON) setup.py clean
	rm -rf Gemfile.lock .bundle pcs_test/resources/temp
	rm -rf $(PACKAGE_NAME)-$(VERSION).tar.* rpm/*tar* rpm/*.gem rpm/*.rpm
	rm -rf stamps/*

# this will get rid of "libtoolized" m4 files
distclean-local:
	rm -rf Gemfile
	rm -rf .mypy_cache
	rm -rf rpm/requirements.txt rpm/Gemfile rpm/pcs-*
	rm -rf stamps
	rm -rf ${abs_top_builddir}/${PCS_BUNDLED_DIR_LOCAL} ${abs_top_builddir}/${PCSD_BUNDLED_DIR_ROOT_LOCAL}
	rm -rf $(filter-out \
	         $(top_builddir)/m4/ac_compare_versions.m4 \
	         $(top_builddir)/m4/ac_pip_module.m4 \
		 $(top_builddir)/m4/ac_ruby_gem.m4 \
		 $(top_builddir)/m4/ax_prog_date.m4, \
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

if ENABLE_WEBUI
spec_config_extra_flags = "--enable-webui"
else
spec_config_extra_flags = ""
endif

## make rpm/srpm section.
$(SPEC): $(SPEC).in .version config.status stamps/download_python_deps stamps/download_rpm_ruby_deps
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
			-e "s#%glo.*alpha.*##g" \
			-e "s#%glo.*numcomm.*##g" \
			-e "s#@dirty@#$$dirty#g" \
			-e "s#@date@#$$date#g" \
			-e "s#@pcs_bundled_dir@#${PCS_BUNDLED_DIR_LOCAL}#g" \
		$(abs_srcdir)/$@.in > $@-t; \
	else \
		sed \
			-e "s#@version@#$$rpmver#g" \
			-e "s#@alphatag@#$$alphatag#g" \
			-e "s#@numcomm@#$$numcomm#g" \
			-e "s#@dirty@#$$dirty#g" \
			-e "s#@date@#$$date#g" \
			-e "s#@pcs_bundled_dir@#${PCS_BUNDLED_DIR_LOCAL}#g" \
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
	pybundle="`for i in $$pylist; do echo $$i | grep -v ^dataclasses- | sed 's/\(.*\)-\(.*\)/Provides: bundled(\1) = \2/'; done`" && \
	$(AWK) -i inplace -v r="$$pybundle" '{gsub(/@pybundle@/,r)}1' $@-t; \
	pycache="`echo $(MKDIR_P) $(PCS_BUNDLED_DIR_LOCAL)/src; base=41; for i in $$pylist pyagentx; do echo 'cp -f %SOURCE'$$base' rpm/' && let "base=base+1"; done`" && \
	$(AWK) -i inplace -v r="$$pycache" '{gsub(/@pycache@/,r)}1' $@-t; \
	gemlist="`for i in $$($(FIND) rpm/ -type f -name '*.gem'); do echo $$i | sed -e 's#rpm/##g' -e 's#.gem##g'; done`" && \
	gemsrc="`base=80; for i in $$gemlist; do echo 'Source'$$base': '$$i'.gem' && let "base=base+1"; done`" && \
	$(AWK) -i inplace -v r="$$gemsrc" '{gsub(/@gemsrc@/,r)}1' $@-t; \
	gembundle="`for i in $$gemlist; do echo $$i | sed 's/\(.*\)-\(.*\)/Provides: bundled(\1) = \2/'; done`" && \
	$(AWK) -i inplace -v r="$$gembundle" '{gsub(/@gembundle@/,r)}1' $@-t; \
	gemcache="`echo $(MKDIR_P) $(PCSD_BUNDLED_CACHE_DIR); base=80; for i in $$gemlist; do echo 'cp -f %SOURCE'$$base' $(PCSD_BUNDLED_CACHE_DIR)' && let "base=base+1"; done`" && \
	$(AWK) -i inplace -v r="$$gemcache" '{gsub(/@gemcache@/,r)}1' $@-t;
	$(AWK) -i inplace -v r="${spec_config_extra_flags}" '{gsub(/@spec_config_extra_flags@/,r)}1' $@-t;
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
