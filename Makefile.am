EXTRA_DIST		= autogen.sh \
			  .version make/release.mk \
			  make/git-version-gen make/gitlog-to-changelog \
			  .eslintrc .gitlab-ci.yml \
			  MANIFEST.in .travis.yml pcs.spec.in \
			  mypy.ini pyproject.toml pylintrc \
			  test/fedora31/Dockerfile test/fedora32/Dockerfile test/centos8/Dockerfile

AUTOMAKE_OPTIONS	= foreign

MAINTAINERCLEANFILES	= Makefile.in aclocal.m4 configure depcomp \
			  config.guess config.sub missing install-sh \
			  autoheader automake autoconf libtool libtoolize \
			  ltmain.sh compile autoscan.log \
			  configure.scan requirements.txt Gemfile Gemfile.lock

SPEC			= $(PACKAGE_NAME).spec

TARFILES		= $(PACKAGE_NAME)-$(VERSION).tar.bz2 \
			  $(PACKAGE_NAME)-$(VERSION).tar.gz \
			  $(PACKAGE_NAME)-$(VERSION).tar.xz

ACLOCAL_AMFLAGS		= -I m4

SUBDIRS			= pcs pcsd pcs_test

# depedency management

# 1 - sources directory - with python package sources
# 2 - destination directory - python package will be installed into the
#     `packages` subdirectory of this destination directory
define build_python_bundle
	cd $(1) && \
	PYTHONPATH=$(2)/packages/ \
	LC_ALL=C.utf8 \
	$(PYTHON) setup.py install --install-lib /packages/ --root $(2)
endef

PYAGENTX_VERSION="0.4.pcs.2"
PYAGENTX_URI="https://github.com/ondrejmular/pyagentx/archive/v${PYAGENTX_VERSION}.tar.gz"

${abs_top_builddir}/$(PCS_BUNDLED_DIR_LOCAL)/src/pyagentx-${PYAGENTX_VERSION}:
if BUILD_PIPMOD_PYAGENTX
	if [ ! -d ${abs_top_builddir}/$(PCS_BUNDLED_DIR_LOCAL)/src/pyagentx-${PYAGENTX_VERSION} ]; then \
		$(MKDIR_P) ${abs_top_builddir}/$(PCS_BUNDLED_DIR_LOCAL)/src; \
		$(WGET) -qO- ${PYAGENTX_URI} | $(TAR) xvz -C ${abs_top_builddir}/${PCS_BUNDLED_DIR_LOCAL}/src; \
	fi
endif

# For running pcs_snmp_agent from a local (git clone) directory (without full
# pcs installation) it is necessary to have pyagentx installed in expected
# location inside the local directory.
install_python_pyagentx_local: ${abs_top_builddir}/$(PCS_BUNDLED_DIR_LOCAL)/src/pyagentx-${PYAGENTX_VERSION}
if BUILD_PIPMOD_PYAGENTX
	rm -rf ${abs_top_builddir}/$(PCS_BUNDLED_DIR_LOCAL)/packages/pyagentx*
	$(call build_python_bundle,${abs_top_builddir}/$(PCS_BUNDLED_DIR_LOCAL)/src/pyagentx-${PYAGENTX_VERSION},/${abs_top_builddir}/$(PCS_BUNDLED_DIR_LOCAL))
endif

install_python_pyagentx: ${abs_top_builddir}/$(PCS_BUNDLED_DIR_LOCAL)/src/pyagentx-${PYAGENTX_VERSION}
if BUILD_PIPMOD_PYAGENTX
	$(call build_python_bundle,${abs_top_builddir}/$(PCS_BUNDLED_DIR_LOCAL)/src/pyagentx-${PYAGENTX_VERSION},$(or ${DESTDIR}, /)/$(LIB_DIR)/$(PCS_BUNDLED_DIR))
endif

if LOCAL_BUILD
PIP_FLAGS		= --user
endif

install_python_pip_deps: requirements.txt
	mv setup.cfg setup.cfg.tmp
	$(PIP) install --upgrade $(PIP_FLAGS) --no-use-pep517 -r $< || $(PIP) install --upgrade $(PIP_FLAGS) -r $<
	mv setup.cfg.tmp setup.cfg
	touch setup.cfg

install_python_deps: install_python_pip_deps install_python_pyagentx_local

install-exec-local: check-local-deps install_python_pyagentx
	$(MKDIR_P) $(or ${DESTDIR}, /)/$(PYTHON_SITELIB)/pcs/
	$(PYTHON) setup.py install --root=$(or ${DESTDIR}, /) ${EXTRA_SETUP_OPTS} --record $(or ${DESTDIR}, /)/$(PYTHON_SITELIB)/pcs/deinstall.txt
	$(MKDIR_P) ${DESTDIR}/$(LIB_DIR)/pcs
	mv ${DESTDIR}/$(SBINDIR)/pcs_internal ${DESTDIR}/$(LIB_DIR)/pcs/pcs_internal
	mv ${DESTDIR}/$(SBINDIR)/pcs_snmp_agent ${DESTDIR}/$(LIB_DIR)/pcs/pcs_snmp_agent
	$(PYTHON) -m compileall -fl $(or ${DESTDIR}, /)/$(PYTHON_SITELIB)/pcs/settings.py

uninstall-local:
if BUILD_PIPMOD_PYAGENTX
	rm -rf $(or ${DESTDIR}, /)/$(LIB_DIR)/$(PCS_BUNDLED_DIR)
endif
	mv ${DESTDIR}/$(LIB_DIR)/pcs/pcs_internal ${DESTDIR}/$(SBINDIR)/pcs_internal || :
	mv ${DESTDIR}/$(LIB_DIR)/pcs/pcs_snmp_agent ${DESTDIR}/$(SBINDIR)/pcs_snmp_agent || :
	for i in $(shell cat $(or ${DESTDIR}, /)/$(PYTHON_SITELIB)/pcs/deinstall.txt); do \
		rm -rf $(or ${DESTDIR}, /)/$${i}; \
	done
	rm -rf $(or ${DESTDIR}, /)/$(PYTHON_SITELIB)/pcs/deinstall.txt
	rmdir ${DESTDIR}/$(LIB_DIR)/pcs

dist_doc_DATA	= README.md CHANGELOG.md

# testing
pylint:
if DEV_TESTS
	$(TIME) $(PYTHON) -m pylint --rcfile pylintrc --persistent=n --reports=n --score=n --disable similarities pcs pcs_test
endif

black_check: pyproject.toml
if DEV_TESTS
	$(TIME) $(PYTHON) -m black --config pyproject.toml --check .
endif

black: pyproject.toml
if DEV_TESTS
	$(PYTHON) -m black --config pyproject.toml .
endif

mypy:
if DEV_TESTS
	$(TIME) $(PYTHON) -m mypy -p pcs
endif

tests_tier0:
	$(PYTHON) ${abs_builddir}/pcs_test/suite.py -v --vanilla --tier0

tests_tier1:
if EXECUTE_TIER1_TESTS
	$(PYTHON) ${abs_builddir}/pcs_test/suite.py -v --vanilla --tier1
endif

install_ruby_deps:
	rm -rf .bundle Gemfile.lock
	$(MKDIR_P) .bundle
	echo '---' > .bundle/config
	echo 'BUNDLE_DISABLE_SHARED_GEMS: "true"' >> .bundle/config
	echo 'BUNDLE_PATH: "${PCSD_BUNDLED_DIR_ROOT_LOCAL}"' >> .bundle/config
	echo 'BUNDLE_BUILD: \"$(ruby_LIBS)\"' >> .bundle/config
	$(BUNDLE)
	rm -rf .bundle Gemfile.lock

pcsd-tests:
	GEM_HOME=${abs_top_builddir}/${PCSD_BUNDLED_DIR_LOCAL} \
		$(RUBY) \
		-I${abs_top_builddir}/pcsd \
		-I${abs_top_builddir}/pcsd/test \
		${abs_top_builddir}/pcsd/test/test_all_suite.rb

if LOCAL_BUILD
check-local-deps: install_python_deps install_ruby_deps
all: check-local-deps
else
check-local-deps:
endif

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

check-local: check-local-deps test-tree-prep pylint black_check mypy tests_tier0 tests_tier1 pcsd-tests test-tree-clean

BUILT_SOURCES = .version
.version:
	echo $(VERSION) > $@-t && mv $@-t $@

dist-hook: gen-ChangeLog
	echo $(VERSION) > $(distdir)/.tarball-version

gen_start_date = 2000-01-01
.PHONY: gen-ChangeLog
gen-ChangeLog:
	if test -d .git; then						\
		$(top_srcdir)/make/gitlog-to-changelog			\
			--since=$(gen_start_date) > $(distdir)/cl-t;	\
		rm -f $(distdir)/ChangeLog;				\
		mv $(distdir)/cl-t $(distdir)/ChangeLog;		\
	fi

clean-local: test-tree-clean
	$(PYTHON) setup.py clean
	rm -rf Gemfile.lock .bundle pcs_test/resources/temp

# this will get rid of "libtoolized" m4 files
distclean-local:
	rm -rf Gemfile requirements.txt
	rm -rf .mypy_cache
	rm -rf ${abs_top_builddir}/${PCS_BUNDLED_DIR_LOCAL} ${abs_top_builddir}/${PCSD_BUNDLED_DIR_ROOT_LOCAL}
	rm -rf $(filter-out \
	         $(top_builddir)/m4/ac_compare_versions.m4 \
	         $(top_builddir)/m4/ac_pip_module.m4 \
		 $(top_builddir)/m4/ac_ruby_gem.m4 \
		 $(top_builddir)/m4/ax_prog_date.m4, \
		 $(wildcard $(top_builddir)/m4/*.m4))

## make rpm/srpm section.
$(SPEC): $(SPEC).in
	rm -f $@-t $@
	date="$(shell LC_ALL=C date "+%a %b %d %Y")" && \
	specver="1" && \
	rcver="" && \
	dirty="" && \
	alphatag="" && \
	numcomm="" && \
	ver="$(VERSION)" && \
	if echo $$ver | grep -q -- "-dirty$$"; then \
		dirty="dirty" && \
		echo VERSION IS DIRTY && \
		ver=`echo $$ver | sed -e "s/-dirty$$//"`; \
	fi && \
	echo $$ver && \
	if echo $$ver | grep -q -- "-"; then \
		alphatag=`echo $$ver | sed -e "s/.*-//"` && \
		echo VERSION HAS ALPHATAG && \
		ver=`echo $$ver | sed -e "s/-.*//"`; \
	fi && \
	echo $$ver && \
	if [ -n "$$alphatag" ]; then \
		echo VERSION HAS NUMCOMMITS && \
		numcomm=`echo $$ver | sed -e 's/.*\.//'` && \
		ver=`echo $$ver | sed -e 's/.'$$numcomm'$$//'`; \
	fi && \
	if echo $$ver | grep -q "\.[[:digit:]]rc[[:digit:]]"; then \
		rpmver=`echo $$ver | sed -e "s/rc[[:digit:]].*//g"` && \
		rcver=`echo $$ver | sed -e "s/.*\(rc[[:digit:]]\).*/\1/g"` && \
		specver="0"; \
	else \
		rpmver=$$ver; \
	fi && \
	echo $$rpmver $$rcver && \
	sed \
		-e "s#@version@#$$rpmver#g" \
		-e "s#@alphatag@#$$alphatag#g" \
		-e "s#@numcomm@#$$numcomm#g" \
		-e "s#@dirty@#$$dirty#g" \
		-e "s#@date@#$$date#g" \
		-e "s#@specver@#$$specver#g" \
		-e "s#@rcver@#$$rcver#g" \
		-e "s#@rgmanager@#$(RGMANAGER)#g" \
		-e "s#@linux-ha@#$(LINUX_HA)#g" \
		-e "s#@compat-habindir@#$(COMPAT_HABINDIR)#g" \
	$< > $@-t; \
	if [ -z "$$dirty" ]; then sed -i -e "s#%glo.*dirty.*##g" $@-t; fi; \
	if [ -z "$$alphatag" ]; then sed -i -e "s#%glo.*alphatag.*##g" $@-t; fi; \
	if [ -z "$$numcomm" ]; then sed -i -e "s#%glo.*numcomm.*##g" $@-t; fi; \
	if [ -z "$$rcver" ]; then sed -i -e "s#%glo.*rcver.*##g" $@-t; fi
	chmod a-w $@-t
	mv $@-t $@

$(TARFILES):
	$(MAKE) dist

RPMBUILDOPTS    = --define "_sourcedir $(abs_builddir)" \
		  --define "_specdir $(abs_builddir)" \
		  --define "_builddir $(abs_builddir)" \
		  --define "_srcrpmdir $(abs_builddir)" \
		  --define "_rpmdir $(abs_builddir)"

srpm: clean
	$(MAKE) $(SPEC) $(TARFILES)
	rpmbuild $(RPMBUILDOPTS) --nodeps -bs $(SPEC)

rpm: clean
	$(MAKE) $(SPEC) $(TARFILES)
	rpmbuild $(RPMBUILDOPTS) -ba $(SPEC)

clean-generic:
	rm -rf $(SPEC) $(TARFILES) $(PACKAGE_NAME)-$(VERSION) *.rpm
