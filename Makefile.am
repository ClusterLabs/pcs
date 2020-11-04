EXTRA_DIST		= autogen.sh \
			  .version make/release.mk \
			  make/git-version-gen make/gitlog-to-changelog

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

SUBDIRS			= pcs pcsd

# release
newversion:
	$(PYTHON) newversion.py

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

# For running pcs_snmp_agent from a local (git clone) directory (without full
# pcs installation) it is necessary to have pyagentx installed in expected
# location inside the local directory.
install_python_pyagentx:
if BUILD_PYMOD_PYAGENTX
	mkdir -p $(PCS_BUNDLED_DIR_LOCAL)/src
	rm -rf $(PCS_BUNDLED_DIR_LOCAL)/src/pyagentx-${PYAGENTX_VERSION} $(PCS_BUNDLED_DIR_LOCAL)/packages/pyagentx*
	$(WGET) -qO- ${PYAGENTX_URI} | $(TAR) xvz -C ${PCS_BUNDLED_DIR_LOCAL}/src
	$(call build_python_bundle,${abs_srcdir}/$(PCS_BUNDLED_DIR_LOCAL)/src/pyagentx-${PYAGENTX_VERSION},${abs_builddir}/$(PCS_BUNDLED_DIR))
	rm -rf $(PCS_BUNDLED_DIR_LOCAL)/src/pyagentx-${PYAGENTX_VERSION}
endif

if LOCAL_BUILD
PIP_FLAGS		= --user
endif

install_python_pip_deps: requirements.txt
	$(PIP) install --upgrade $(PIP_FLAGS) --no-use-pep517 -r $< || $(PIP) install --upgrade -r $<

install_python_deps: install_python_pip_deps install_python_pyagentx

# testing
pylint:
	$(TIME) $(PYTHON) -m pylint --rcfile pylintrc --persistent=n --reports=n --score=n --disable similarities pcs pcs_test

black_check: pyproject.toml
	$(TIME) $(BLACK) --config pyproject.toml --check .

black: pyproject.toml
	$(BLACK) --config pyproject.toml .

mypy:
	$(TIME) $(MYPY) -p pcs

tests_tier0:
	$(PYTHON) pcs_test/suite.py -v --vanilla --tier0

tests_tier1:
if EXECUTE_TIER1_TESTS
	$(PYTHON) pcs_test/suite.py -v --vanilla --tier1
endif

install_ruby_deps:
	rm -rf .bundle Gemfile.lock
	mkdir -p .bundle
	echo '---' > .bundle/config
	echo 'BUNDLE_DISABLE_SHARED_GEMS: "1"' >> .bundle/config
	echo 'BUNDLE_PATH: "${PCSD_BUNDLED_DIR_ROOT_LOCAL}"' >> .bundle/config
	$(BUNDLE)
	rm -rf .bundle Gemfile.lock

pcsd-tests:
	GEM_HOME=${abs_top_srcdir}/${PCSD_BUNDLED_DIR_LOCAL} \
		$(RUBY) \
		-I${abs_top_srcdir}/pcsd \
		-I${abs_top_srcdir}/pcsd/test \
		${abs_top_srcdir}/pcsd/test/test_all_suite.rb

if LOCAL_BUILD
check-local-deps: install_python_deps install_ruby_deps
else
check-local-deps:
endif

check-local: check-local-deps pylint black_check mypy tests_tier0 tests_tier1 pcsd-tests

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

clean-local:
	$(PYTHON) setup.py clean
	rm -rf Gemfile.lock .bundle

# this will get rid of "libtoolized" m4 files
maintainer-clean-local:
	rm -rf ${PCS_BUNDLED_DIR_LOCAL} ${PCSD_BUNDLED_DIR_ROOT_LOCAL}
	rm -rf $(filter-out \
	         $(top_srcdir)/m4/ac_python_module.m4 \
	         $(top_srcdir)/m4/ac_pip_module.m4 \
		 $(top_srcdir)/m4/ac_ruby_gem.m4, \
		 $(wildcard $(top_srcdir)/m4/*.m4))

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
