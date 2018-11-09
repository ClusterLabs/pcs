# Compatibility with GNU/Linux [i.e. Debian] based distros
UNAME_OS_GNU := $(shell if uname -o | grep -q "GNU/Linux" ; then echo true; else echo false; fi)
DISTRO_DEBIAN := $(shell if [ -e /etc/debian_version ] ; then echo true; else echo false; fi)
IS_DEBIAN=false
DISTRO_DEBIAN_VER_8=false

ifndef PYTHON
	PYTHON := $(shell which python3 || which python2 || which python)
endif

ifeq ($(UNAME_OS_GNU),true)
  ifeq ($(DISTRO_DEBIAN),true)
    IS_DEBIAN=true
    DISTRO_DEBIAN_VER_8 := $(shell if grep -q -i "^8\|jessie" /etc/debian_version ; then echo true; else echo false; fi)
    # dpkg-architecture is in the optional dpkg-dev package, unfortunately.
    #DEB_HOST_MULTIARCH := $(shell dpkg-architecture -qDEB_HOST_MULTIARCH)
    # TODO: Use lsb_architecture to get the multiarch tuple if/when it becomes available in distributions.
    DEB_HOST_MULTIARCH := $(shell dpkg -L libc6 | sed -nr 's|^/etc/ld\.so\.conf\.d/(.*)\.conf$$|\1|p')
  endif
endif

ifndef PYTHON_SITELIB
  PYTHON_SITELIB=$(shell $(PYTHON) -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")
endif
ifeq ($(PYTHON_SITELIB), /usr/lib/python2.6/dist-packages)
  EXTRA_SETUP_OPTS="--install-layout=deb"
endif
ifeq ($(PYTHON_SITELIB), /usr/lib/python2.7/dist-packages)
  EXTRA_SETUP_OPTS="--install-layout=deb"
endif
ifeq ($(PYTHON_SITELIB), /usr/lib/python3/dist-packages)
  EXTRA_SETUP_OPTS="--install-layout=deb"
endif

# Check for systemd presence
ifeq ($(SYSTEMCTL_OVERRIDE),true)
  IS_SYSTEMCTL=true
else
  ifeq ($(SYSTEMCTL_OVERRIDE),false)
    IS_SYSTEMCTL=false
  else
    IS_SYSTEMCTL = $(shell if [ -d /run/systemd/system ] || [ -d /var/run/systemd/system ] ; then echo true ; else echo false; fi)
  endif
endif

# Check for an override for building gems
ifndef BUILD_GEMS
  BUILD_GEMS=true
endif

MANDIR=/usr/share/man

ifndef PREFIX
  PREFIX=$(shell prefix=`$(PYTHON) -c "import sys; print(sys.prefix)"` || prefix="/usr"; echo $$prefix)
endif

ifndef systemddir
  systemddir=/usr/lib/systemd
endif

ifndef initdir
  initdir=/etc/init.d
endif

ifndef install_settings
  ifeq ($(IS_DEBIAN),true)
    install_settings=true
  else
    install_settings=false
  endif
endif


ifndef BASH_COMPLETION_DIR
	BASH_COMPLETION_DIR=${DESTDIR}/etc/bash_completion.d
endif

ifndef PCSD_PARENT_DIR
  ifeq ($(IS_DEBIAN),true)
    PCSD_PARENT_DIR = /usr/share
  else
    PCSD_PARENT_DIR = ${PREFIX}/lib
  endif
endif

ifndef PCS_PARENT_DIR
  PCS_PARENT_DIR=${DESTDIR}/${PREFIX}/lib/pcs
endif

BUNDLED_LIB_INSTALL_DIR=${PCS_PARENT_DIR}/bundled

ifndef BUNDLED_LIB_DIR
  BUNDLED_LIB_DIR=./pcs/bundled/
endif
BUNDLED_LIB_DIR_ABS=$(shell readlink -f ${BUNDLED_LIB_DIR})
BUNDLES_TMP_DIR=${BUNDLED_LIB_DIR_ABS}/tmp

ifndef SNMP_MIB_DIR
  SNMP_MIB_DIR=/share/snmp/mibs/
endif
SNMP_MIB_DIR_FULL=${DESTDIR}/${PREFIX}/${SNMP_MIB_DIR}

pcsd_fonts = \
	LiberationSans-Regular.ttf;LiberationSans:style=Regular \
	LiberationSans-Bold.ttf;LiberationSans:style=Bold \
	LiberationSans-BoldItalic.ttf;LiberationSans:style=BoldItalic \
	LiberationSans-Italic.ttf;LiberationSans:style=Italic \
	Overpass-Regular.ttf;Overpass:style=Regular \
	Overpass-Bold.ttf;Overpass:style=Bold


install: install_bundled_libs
	# make Python interpreter execution sane (via -Es flags)
	printf "[build]\nexecutable = $(PYTHON) -Es\n" > setup.cfg
	$(PYTHON) setup.py install --root=$(or ${DESTDIR}, /) ${EXTRA_SETUP_OPTS}
	# fix excessive script interpreting "executable" quoting with old setuptools:
	# https://github.com/pypa/setuptools/issues/188
	# https://bugzilla.redhat.com/1353934
	sed -i '1s|^\(#!\)"\(.*\)"$$|\1\2|' ${DESTDIR}${PREFIX}/bin/pcs
	sed -i '1s|^\(#!\)"\(.*\)"$$|\1\2|' ${DESTDIR}${PREFIX}/bin/pcs_snmp_agent
	rm setup.cfg
	mkdir -p ${DESTDIR}${PREFIX}/sbin/
	mv ${DESTDIR}${PREFIX}/bin/pcs ${DESTDIR}${PREFIX}/sbin/pcs
	install -D -m644 pcs/bash_completion ${BASH_COMPLETION_DIR}/pcs
	install -m644 -D pcs/pcs.8 ${DESTDIR}/${MANDIR}/man8/pcs.8
	# pcs SNMP install
	mv ${DESTDIR}${PREFIX}/bin/pcs_snmp_agent ${PCS_PARENT_DIR}/pcs_snmp_agent
	install -d ${DESTDIR}/var/log/pcs
	install -d ${SNMP_MIB_DIR_FULL}
	install -m 644 pcs/snmp/mibs/PCMK-PCS*-MIB.txt ${SNMP_MIB_DIR_FULL}
	install -m 644 -D pcs/snmp/pcs_snmp_agent.conf ${DESTDIR}/etc/sysconfig/pcs_snmp_agent
	install -m 644 -D pcs/snmp/pcs_snmp_agent.8 ${DESTDIR}/${MANDIR}/man8/pcs_snmp_agent.8
ifeq ($(IS_SYSTEMCTL),true)
	install -d ${DESTDIR}/${systemddir}/system/
	install -m 644 pcs/snmp/pcs_snmp_agent.service ${DESTDIR}/${systemddir}/system/
endif
ifeq ($(IS_DEBIAN),true)
  ifeq ($(install_settings),true)
	rm -f  ${DESTDIR}${PYTHON_SITELIB}/pcs/settings.py
	tmp_settings=`mktemp`; \
	        sed s/DEB_HOST_MULTIARCH/${DEB_HOST_MULTIARCH}/g pcs/settings.py.debian > $$tmp_settings; \
	        install -m644 $$tmp_settings ${DESTDIR}${PYTHON_SITELIB}/pcs/settings.py; \
	        rm -f $$tmp_settings
	$(PYTHON) -m compileall -fl ${DESTDIR}${PYTHON_SITELIB}/pcs/settings.py
  endif
endif

install_pcsd:
ifeq ($(BUILD_GEMS),true)
	make -C pcsd build_gems
endif
	mkdir -p ${DESTDIR}/var/log/pcsd
ifeq ($(IS_DEBIAN),true)
	mkdir -p ${DESTDIR}/usr/share/
	cp -r pcsd ${DESTDIR}/usr/share/
	install -m 644 -D pcsd/pcsd.conf ${DESTDIR}/etc/default/pcsd
	install -d ${DESTDIR}/etc/pam.d
	install  pcsd/pcsd.pam.debian ${DESTDIR}/etc/pam.d/pcsd
  ifeq ($(install_settings),true)
	rm -f  ${DESTDIR}/usr/share/pcsd/settings.rb
	tmp_settings_pcsd=`mktemp`; \
	        sed s/DEB_HOST_MULTIARCH/${DEB_HOST_MULTIARCH}/g pcsd/settings.rb.debian > $$tmp_settings_pcsd; \
	        install -m644 $$tmp_settings_pcsd ${DESTDIR}/usr/share/pcsd/settings.rb; \
	        rm -f $$tmp_settings_pcsd
  endif
  ifeq ($(IS_SYSTEMCTL),true)
	install -d ${DESTDIR}/${systemddir}/system/
	install -m 644 pcsd/pcsd.service.debian ${DESTDIR}/${systemddir}/system/pcsd.service
  else
	install -m 755 -D pcsd/pcsd.debian ${DESTDIR}/${initdir}/pcsd
  endif
else
	mkdir -p ${DESTDIR}${PCSD_PARENT_DIR}/
	cp -r pcsd ${DESTDIR}${PCSD_PARENT_DIR}/
	install -m 644 -D pcsd/pcsd.conf ${DESTDIR}/etc/sysconfig/pcsd
	install -d ${DESTDIR}/etc/pam.d
	install -m 644 pcsd/pcsd.pam ${DESTDIR}/etc/pam.d/pcsd
  ifeq ($(IS_SYSTEMCTL),true)
	install -d ${DESTDIR}/${systemddir}/system/
	install -m 644 pcsd/pcsd.service ${DESTDIR}/${systemddir}/system/
# ${DESTDIR}${PCSD_PARENT_DIR}/pcsd/pcsd holds the selinux context
	install -m 755 pcsd/pcsd.service-runner ${DESTDIR}${PCSD_PARENT_DIR}/pcsd/pcsd
	rm ${DESTDIR}${PCSD_PARENT_DIR}/pcsd/pcsd.service-runner
  else
	install -m 755 -D pcsd/pcsd ${DESTDIR}/${initdir}/pcsd
  endif
endif
	install -m 700 -d ${DESTDIR}/var/lib/pcsd
	install -m 644 -D pcsd/pcsd.logrotate ${DESTDIR}/etc/logrotate.d/pcsd
	install -m644 -D pcsd/pcsd.8 ${DESTDIR}/${MANDIR}/man8/pcsd.8
	$(foreach font,$(pcsd_fonts),\
		$(eval font_file = $(word 1,$(subst ;, ,$(font)))) \
		$(eval font_def = $(word 2,$(subst ;, ,$(font)))) \
		$(eval font_path = $(shell fc-match '--format=%{file}' '$(font_def)')) \
		$(if $(font_path),ln -s -f $(font_path) ${DESTDIR}${PCSD_PARENT_DIR}/pcsd/public/css/$(font_file);,$(error Font $(font_def) not found)) \
	)

build_bundled_libs:
ifndef PYAGENTX_INSTALLED
	rm -rf ${BUNDLES_TMP_DIR}
	mkdir -p ${BUNDLES_TMP_DIR}
	$(MAKE) -C pcs/snmp/ build_bundled_libs
	rm -rf ${BUNDLES_TMP_DIR}
endif

install_bundled_libs: build_bundled_libs
ifndef PYAGENTX_INSTALLED
	install -d ${BUNDLED_LIB_INSTALL_DIR}
	cp -r ${BUNDLED_LIB_DIR_ABS}/packages ${BUNDLED_LIB_INSTALL_DIR}
endif

uninstall:
	rm -f ${DESTDIR}${PREFIX}/sbin/pcs
	rm -rf ${DESTDIR}${PYTHON_SITELIB}/pcs
ifeq ($(IS_DEBIAN),true)
	rm -rf ${DESTDIR}/usr/share/pcsd
	rm -rf ${DESTDIR}/usr/share/pcs
else
	rm -rf ${DESTDIR}${PREFIX}/lib/pcsd
	rm -rf ${DESTDIR}${PREFIX}/lib/pcs
endif
ifeq ($(IS_SYSTEMCTL),true)
	rm -f ${DESTDIR}/${systemddir}/system/pcsd.service
	rm -f ${DESTDIR}/${systemddir}/system/pcs_snmp_agent.service
else
	rm -f ${DESTDIR}/${initdir}/pcsd
endif
	rm -f ${DESTDIR}/etc/pam.d/pcsd
	rm -rf ${DESTDIR}/var/lib/pcsd
	rm -f ${SNMP_MIB_DIR_FULL}/PCMK-PCS*-MIB.txt

tarball:
	$(PYTHON) setup.py sdist --formats=tar
	$(PYTHON) maketarballs.py

newversion:
	$(PYTHON) newversion.py
