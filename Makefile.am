EXTRA_DIST		= autogen.sh \
			  .version make/release.mk \
			  make/git-version-gen make/gitlog-to-changelog

AUTOMAKE_OPTIONS	= foreign

MAINTAINERCLEANFILES	= Makefile.in aclocal.m4 configure depcomp \
			  config.guess config.sub missing install-sh \
			  autoheader automake autoconf libtool libtoolize \
			  ltmain.sh compile autoscan.log \
			  configure.scan

SPEC			= $(PACKAGE_NAME).spec

TARFILES		= $(PACKAGE_NAME)-$(VERSION).tar.bz2 \
			  $(PACKAGE_NAME)-$(VERSION).tar.gz \
			  $(PACKAGE_NAME)-$(VERSION).tar.xz

ACLOCAL_AMFLAGS		= -I m4

SUBDIRS			= 

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

# this will get rid of "libtoolized" m4 files
maintainer-clean-local:
	rm -rf $(filter-out \
	         $(top_srcdir)/m4/ac_python_module.m4,$(wildcard \
		                                        $(top_srcdir)/m4/*.m4))

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
