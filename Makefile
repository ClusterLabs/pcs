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
# ==================================

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

ifndef BUNDLE_LOCAL_DIR
  BUNDLE_LOCAL_DIR=./pcs/bundled/
endif

ifndef SNMP_MIB_DIR
  SNMP_MIB_DIR=/share/snmp/mibs/
endif

# INSTALLATION FINE DETAIL CONTROLL
# =================================
#  `BUNDLE_INSTALL_PYAGENTX=false`
#      to disable the default automatic pyagentx instalation
#  `BUNDLE_PYAGENTX_SRC_DIR=/path/to/pyagentx/sources`
#      to install pyagentx from the given location instead of using default
#      location for downloading sources and an installation
#  `BUNDLE_TORNADO_SRC_DIR=/path/to/tornado/sources`
#      to install tornado from specified location (tornado is not installed by
#      default)
BUNDLE_PYAGENTX_VERSION="0.4.pcs.2"
BUNDLE_PYAGENTX_URI="https://github.com/ondrejmular/pyagentx/archive/v${BUNDLE_PYAGENTX_VERSION}.tar.gz"

ifndef BUNDLE_INSTALL_PYAGENTX
	BUNDLE_INSTALL_PYAGENTX=true
endif

BUNDLE_PYAGENTX_SRC_DOWNLOAD=false
ifndef BUNDLE_PYAGENTX_SRC_DIR
	BUNDLE_PYAGENTX_SRC_DOWNLOAD=true
endif
ifneq ($(BUNDLE_INSTALL_PYAGENTX),true)
	BUNDLE_PYAGENTX_SRC_DOWNLOAD=false
endif

# There is BUNDLE_TO_INSTALL when BUNDLE_INSTALL_PYAGENTX is true or
# BUNDLE_TORNADO_SRC_DIR is specified
BUNDLE_TO_INSTALL=false
ifeq ($(BUNDLE_INSTALL_PYAGENTX), true)
	BUNDLE_TO_INSTALL=true
endif
ifdef BUNDLE_TORNADO_SRC_DIR
	BUNDLE_TO_INSTALL=true
endif

# DESTINATION DIRS
# ================

DEST_PYTHON_SITELIB = ${DESTDIR}${PYTHON_SITELIB}
DEST_MAN=${DESTDIR}/usr/share/man/man8
DEST_SYSTEMD_SYSTEM = ${DESTDIR}${SYSTEMD_DIR}/system
DEST_INIT = ${DESTDIR}${INIT_DIR}
DEST_BASH_COMPLETION = ${DESTDIR}${BASH_COMPLETION_DIR}
DEST_CONF = ${DESTDIR}${CONF_DIR}
DEST_LIB = ${DESTDIR}${LIB_DIR}
DEST_PREFIX = ${DESTDIR}${PREFIX}
DEST_BUNDLE_LIB=${DEST_LIB}/pcs/bundled
DEST_BUNDLE_LOCAL=$(shell readlink -f ${BUNDLE_LOCAL_DIR})
DEST_SNMP_MIB=${DEST_PREFIX}${SNMP_MIB_DIR}

# OTHER
# =====

pcsd_fonts = \
	LiberationSans-Regular.ttf;LiberationSans:style=Regular \
	LiberationSans-Bold.ttf;LiberationSans:style=Bold \
	LiberationSans-BoldItalic.ttf;LiberationSans:style=BoldItalic \
	LiberationSans-Italic.ttf;LiberationSans:style=Italic \
	Overpass-Regular.ttf;Overpass:style=Regular \
	Overpass-Bold.ttf;Overpass:style=Bold

# 1 - debian alternative file
# 2 - file which will be replaced by debian alternative file
define use-debian-alternative
	rm -f  $(2)
	tmp_alternative=`mktemp`; \
	sed s/DEB_HOST_MULTIARCH/${DEB_HOST_MULTIARCH}/g $(1) > $$tmp_alternative; \
	install -m644 $$tmp_alternative $(2)
	rm -f $$tmp_alternative
endef

# 1 - sources directory - with python package sources
# 2 - destination directory - python package will be installed into the
#     `packages` subdirectory of this destination directory
define build_python_bundle
	cd $(1) && \
	PYTHONPATH=$(2)/packages/ \
	$(PYTHON) setup.py install --install-lib /packages/ --root $(2)
endef

# TARGETS
# =======

bundle_pyagentx:
ifeq ($(BUNDLE_PYAGENTX_SRC_DOWNLOAD),true)
	mkdir -p ${DEST_BUNDLE_LOCAL}/src
	$(eval BUNDLE_PYAGENTX_SRC_DIR=${DEST_BUNDLE_LOCAL}/src/pyagentx-${BUNDLE_PYAGENTX_VERSION})
	rm -rf ${BUNDLE_PYAGENTX_SRC_DIR}
	wget -qO- ${BUNDLE_PYAGENTX_URI} | tar xvz -C ${DEST_BUNDLE_LOCAL}/src
endif
ifeq ($(BUNDLE_INSTALL_PYAGENTX),true)
	$(call build_python_bundle,${BUNDLE_PYAGENTX_SRC_DIR},$(PYAGENTX_LIB_DIR))
endif
ifeq ($(BUNDLE_PYAGENTX_SRC_DOWNLOAD),true)
	rm -rf ${BUNDLE_PYAGENTX_SRC_DIR}
endif

install_bundled_libs:
ifeq ($(BUNDLE_TO_INSTALL),true)
	install -d ${DEST_BUNDLE_LIB}
endif
ifdef BUNDLE_TORNADO_SRC_DIR
	$(call build_python_bundle,${BUNDLE_TORNADO_SRC_DIR},${DEST_BUNDLE_LIB})
endif
	$(MAKE) PYAGENTX_LIB_DIR=$(DEST_BUNDLE_LIB) bundle_pyagentx

install_python_part: install_bundled_libs
	# make Python interpreter execution sane (via -Es flags)
	printf "[build]\nexecutable = $(PYTHON) -Es\n" > setup.cfg
	$(PYTHON) setup.py install --root=$(or ${DESTDIR}, /) ${EXTRA_SETUP_OPTS}
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
	install -m644 -D pcs/pcs.8 ${DEST_MAN}/pcs.8
	# pcs SNMP install
	mv ${DEST_PREFIX}/bin/pcs_snmp_agent ${DEST_LIB}/pcs/pcs_snmp_agent
	install -d ${DESTDIR}/var/log/pcs
	install -d ${DEST_SNMP_MIB}
	install -m 644 pcs/snmp/mibs/PCMK-PCS*-MIB.txt ${DEST_SNMP_MIB}
	install -m 644 -D pcs/snmp/pcs_snmp_agent.conf ${DEST_CONF}/pcs_snmp_agent
	install -m 644 -D pcs/snmp/pcs_snmp_agent.8 ${DEST_MAN}/pcs_snmp_agent.8
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
	install -m644 -D pcsd/pcsd.8 ${DEST_MAN}/pcsd.8
	$(foreach font,$(pcsd_fonts),\
		$(eval font_file = $(word 1,$(subst ;, ,$(font)))) \
		$(eval font_def = $(word 2,$(subst ;, ,$(font)))) \
		$(eval font_path = $(shell fc-match '--format=%{file}' '$(font_def)')) \
		$(if $(font_path),ln -s -f $(font_path) ${DEST_LIB}/pcsd/public/css/$(font_file);,$(error Font $(font_def) not found)) \
	)

# For running pcs_snmp_agent from a local (git clone) directory (without full
# pcs installation) it is necessary to have pyagentx installed in expected
# location inside the local directory.
bundle_pyagentx_local:
	$(MAKE) PYAGENTX_LIB_DIR=$(DEST_BUNDLE_LOCAL) bundle_pyagentx

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
	rm -f ${DEST_SNMP_MIB}/PCMK-PCS*-MIB.txt

newversion:
	$(PYTHON) newversion.py
