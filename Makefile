# Compatibility with GNU/Linux [i.e. Debian] based distros
UNAME_OS_GNU := $(shell if uname -o | grep -q "GNU/Linux" ; then echo true; else echo false; fi)
DISTRO_DEBIAN := $(shell if [ -e /etc/debian_version ] ; then echo true; else echo false; fi)
IS_DEBIAN=false
DISTRO_DEBIAN_VER_8=false

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

ifeq ($(IS_DEBIAN),true)
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

# VARIABLES OVERRIDABLE FROM OUTSIDE

ifndef PYTHON
	# some distros ship python3 as python
	PYTHON := $(shell which python3 || which python)
endif

ifndef PYTHON_SITELIB
  PYTHON_SITELIB=$(shell $(PYTHON) -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")
endif

# Check for an override for building gems
ifndef BUILD_GEMS
  BUILD_GEMS=true
endif

ifndef PREFIX
  PREFIX=$(shell prefix=`$(PYTHON) -c "import sys; print(sys.prefix)"` || prefix="/usr"; echo $$prefix)
endif

ifndef SYSTEMD_DIR
  SYSTEMD_DIR=/usr/lib/systemd
endif

ifndef INIT_DIR
  INIT_DIR=/etc/init.d
endif

ifndef BASH_COMPLETION_DIR
  BASH_COMPLETION_DIR=/etc/bash_completion.d
endif

ifndef CONF_DIR
  ifeq ($(IS_DEBIAN),true)
    CONF_DIR = /etc/default
  else
    CONF_DIR = /etc/sysconfig
  endif
endif

ifndef SYSTEMD_SERVICE_FILE
  ifeq ($(IS_DEBIAN),true)
    SYSTEMD_SERVICE_FILE = pcsd/pcsd.service.debian
  else
    SYSTEMD_SERVICE_FILE = pcsd/pcsd.service
  endif
endif

ifndef LIB_DIR
  ifeq ($(IS_DEBIAN),true)
    LIB_DIR = /usr/share
  else
    LIB_DIR = ${PREFIX}/lib
  endif
endif

ifndef BUNDLED_LIB_DIR
  BUNDLED_LIB_DIR=./pcs/bundled/
endif

ifndef SNMP_MIB_DIR
  SNMP_MIB_DIR=/share/snmp/mibs/
endif

# DESTINATION DIRS

DEST_PYTHON_SITELIB = ${DESTDIR}${PYTHON_SITELIB}
DEST_MAN=${DESTDIR}/usr/share/man/man8
DEST_SYSTEMD_SYSTEM = ${DESTDIR}${SYSTEMD_DIR}/system
DEST_INIT = ${DESTDIR}${INIT_DIR}
DEST_BASH_COMPLETION = ${DESTDIR}${BASH_COMPLETION_DIR}
DEST_CONF = ${DESTDIR}${CONF_DIR}
DEST_LIB = ${DESTDIR}${LIB_DIR}
DEST_PREFIX = ${DESTDIR}${PREFIX}
SNMP_MIB_DIR_FULL=${DEST_PREFIX}${SNMP_MIB_DIR}
BUNDLED_LIB_INSTALL_DIR=${DEST_LIB}/pcs/bundled
BUNDLED_LIB_DIR_ABS=$(shell readlink -f ${BUNDLED_LIB_DIR})
BUNDLES_TMP_DIR=${BUNDLED_LIB_DIR_ABS}/tmp

pcsd_fonts = \
	LiberationSans-Regular.ttf;LiberationSans:style=Regular \
	LiberationSans-Bold.ttf;LiberationSans:style=Bold \
	LiberationSans-BoldItalic.ttf;LiberationSans:style=BoldItalic \
	LiberationSans-Italic.ttf;LiberationSans:style=Italic \
	Overpass-Regular.ttf;Overpass:style=Regular \
	Overpass-Bold.ttf;Overpass:style=Bold

define use-debian-alternative
	rm -f  $(2)
	tmp_alternative=`mktemp`; \
	sed s/DEB_HOST_MULTIARCH/${DEB_HOST_MULTIARCH}/g $(1) > $$tmp_alternative; \
	install -m644 $$tmp_alternative $(2)
	rm -f $$tmp_alternative
endef

install_python_part: install_bundled_libs
	# make Python interpreter execution sane (via -Es flags)
	printf "[build]\nexecutable = $(PYTHON) -Es\n" > setup.cfg
	# prefix must be explicit since fedora uses /usr/local as default when
	# environment variable RPM_BUILD_ROOT is not set.
	$(PYTHON) setup.py install --prefix=${DEST_PREFIX} --root=$(or ${DESTDIR}, /) ${EXTRA_SETUP_OPTS}
	# fix excessive script interpreting "executable" quoting with old setuptools:
	# https://github.com/pypa/setuptools/issues/188
	# https://bugzilla.redhat.com/1353934
	sed -i '1s|^\(#!\)"\(.*\)"$$|\1\2|' ${DEST_PREFIX}/bin/pcs
	sed -i '1s|^\(#!\)"\(.*\)"$$|\1\2|' ${DEST_PREFIX}/bin/pcs_snmp_agent
	rm setup.cfg
	mkdir -p ${DEST_PREFIX}/sbin/
	mv ${DEST_PREFIX}/bin/pcs ${DEST_PREFIX}/sbin/pcs
	mv ${DEST_PREFIX}/bin/pcsd ${DEST_PREFIX}/sbin/pcsd
	install -D -m644 pcs/bash_completion ${DEST_BASH_COMPLETION}/pcs
	install -m644 -D pcs/pcs.8 ${DEST_MAN}
	# pcs SNMP install
	mv ${DEST_PREFIX}/bin/pcs_snmp_agent ${DEST_LIB}/pcs/pcs_snmp_agent
	install -d ${DESTDIR}/var/log/pcs
	install -d ${SNMP_MIB_DIR_FULL}
	install -m 644 pcs/snmp/mibs/PCMK-PCS*-MIB.txt ${SNMP_MIB_DIR_FULL}
	install -m 644 -D pcs/snmp/pcs_snmp_agent.conf ${DEST_CONF}/pcs_snmp_agent
	install -m 644 -D pcs/snmp/pcs_snmp_agent.8 ${DEST_MAN}
ifeq ($(IS_DEBIAN),true)
	$(call use-debian-alternative,pcs/settings.py.debian,${DEST_PYTHON_SITELIB}/pcs/settings.py)
endif
	$(PYTHON) -m compileall -fl ${DEST_PYTHON_SITELIB}/pcs/settings.py
ifeq ($(IS_SYSTEMCTL),true)
	install -d ${DEST_SYSTEMD_SYSTEM}
	install -m 644 pcs/snmp/pcs_snmp_agent.service ${DEST_SYSTEMD_SYSTEM}
endif

install: install_python_part
ifeq ($(BUILD_GEMS),true)
	make -C pcsd build_gems
endif
	mkdir -p ${DESTDIR}/var/log/pcsd
	mkdir -p ${DEST_LIB}
	cp -r pcsd ${DEST_LIB}
	install -m 644 -D pcsd/pcsd.conf ${DEST_CONF}/pcsd
	install -d ${DESTDIR}/etc/pam.d
	install  pcsd/pcsd.pam ${DESTDIR}/etc/pam.d/pcsd
ifeq ($(IS_DEBIAN),true)
	$(call use-debian-alternative,pcsd/settings.rb.debian,${DEST_LIB}/pcsd/settings.rb)
endif
ifeq ($(IS_DEBIAN)$(IS_SYSTEMCTL),truefalse)
	install -m 755 -D pcsd/pcsd.debian ${DEST_INIT}/pcsd
else
	install -d ${DEST_SYSTEMD_SYSTEM}
	install -m 644 ${SYSTEMD_SERVICE_FILE} ${DEST_SYSTEMD_SYSTEM}/pcsd.service
endif
	install -m 700 -d ${DESTDIR}/var/lib/pcsd
	install -m 644 -D pcsd/pcsd.logrotate ${DESTDIR}/etc/logrotate.d/pcsd
	install -m644 -D pcsd/pcsd.8 ${DEST_MAN}
	$(foreach font,$(pcsd_fonts),\
		$(eval font_file = $(word 1,$(subst ;, ,$(font)))) \
		$(eval font_def = $(word 2,$(subst ;, ,$(font)))) \
		$(eval font_path = $(shell fc-match '--format=%{file}' '$(font_def)')) \
		$(if $(font_path),ln -s -f $(font_path) ${DEST_LIB}/pcsd/public/css/$(font_file);,$(error Font $(font_def) not found)) \
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
	rm -f ${DEST_PREFIX}/sbin/pcs
	rm -rf ${DEST_PYTHON_SITELIB}/pcs
	rm -rf ${DEST_LIB}/pcsd
	rm -rf ${DEST_LIB}/pcs
ifeq ($(IS_DEBIAN)$(IS_SYSTEMCTL),truefalse)
	rm -f ${DEST_INIT}/pcsd
else
	rm -f ${DEST_SYSTEMD_SYSTEM}/pcsd.service
	rm -f ${DEST_SYSTEMD_SYSTEM}/pcs_snmp_agent.service
endif
	rm -f ${DESTDIR}/etc/pam.d/pcsd
	rm -rf ${DESTDIR}/var/lib/pcsd
	rm -f ${SNMP_MIB_DIR_FULL}/PCMK-PCS*-MIB.txt

newversion:
	$(PYTHON) newversion.py
