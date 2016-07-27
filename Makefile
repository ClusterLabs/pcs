# Compatibility with GNU/Linux [i.e. Debian] based distros
UNAME_OS_GNU := $(shell if uname -o | grep -q "GNU/Linux" ; then echo true; else echo false; fi)
DISTRO_DEBIAN := $(shell if [ -e /etc/debian_version ] ; then echo true; else echo false; fi)
IS_DEBIAN=false
DISTRO_DEBIAN_VER_8=false

ifndef PYTHON
	PYTHON=python
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

# Check for systemd presence, add compatibility with Debian based distros
IS_SYSTEMCTL=false

ifeq ($(IS_DEBIAN),true)
  IS_SYSTEMCTL = $(shell if [ -d /var/run/systemd/system ] ; then echo true ; else echo false; fi)
  ifeq ($(IS_SYSTEMCTL),false)
    ifeq ($(SYSTEMCTL_OVERRIDE),true)
      IS_SYSTEMCTL=true
    endif
  endif
else
  ifeq ("$(wildcard /usr/bin/systemctl)","/usr/bin/systemctl")
    IS_SYSTEMCTL=true
  else
    ifeq ("$(wildcard /bin/systemctl)","/usr/bin/systemctl")
      IS_SYSTEMCTL=true
    endif
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

install:
	$(PYTHON) setup.py install --root=$(or ${DESTDIR}, /) ${EXTRA_SETUP_OPTS}
	mkdir -p ${DESTDIR}${PREFIX}/sbin/
	mv ${DESTDIR}${PREFIX}/bin/pcs ${DESTDIR}${PREFIX}/sbin/pcs
	install -D -m644 pcs/bash_completion.sh ${BASH_COMPLETION_DIR}/pcs
	install -m644 -D pcs/pcs.8 ${DESTDIR}/${MANDIR}/man8/pcs.8
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
	mkdir -p ${DESTDIR}${PREFIX}/lib/
	cp -r pcsd ${DESTDIR}${PREFIX}/lib/
	install -m 644 -D pcsd/pcsd.conf ${DESTDIR}/etc/sysconfig/pcsd
	install -d ${DESTDIR}/etc/pam.d
	install  pcsd/pcsd.pam ${DESTDIR}/etc/pam.d/pcsd
  ifeq ($(IS_SYSTEMCTL),true)
	install -d ${DESTDIR}/${systemddir}/system/
	install -m 644 pcsd/pcsd.service ${DESTDIR}/${systemddir}/system/
# ${DESTDIR}${PREFIX}/lib/pcsd/pcsd holds the selinux context
	install -m 755 pcsd/pcsd.service-runner ${DESTDIR}${PREFIX}/lib/pcsd/pcsd
	rm ${DESTDIR}${PREFIX}/lib/pcsd/pcsd.service-runner
  else
	install -m 755 -D pcsd/pcsd ${DESTDIR}/${initdir}/pcsd
  endif
endif
	install -m 700 -d ${DESTDIR}/var/lib/pcsd
	install -m 644 -D pcsd/pcsd.logrotate ${DESTDIR}/etc/logrotate.d/pcsd

uninstall:
	rm -f ${DESTDIR}${PREFIX}/sbin/pcs
	rm -rf ${DESTDIR}${PYTHON_SITELIB}/pcs
ifeq ($(IS_DEBIAN),true)
	rm -rf ${DESTDIR}/usr/share/pcsd
else
	rm -rf ${DESTDIR}${PREFIX}/lib/pcsd
endif
ifeq ($(IS_SYSTEMCTL),true)
	rm -f ${DESTDIR}/${systemddir}/system/pcsd.service
else
	rm -f ${DESTDIR}/${initdir}/pcsd
endif
	rm -f ${DESTDIR}/etc/pam.d/pcsd
	rm -rf ${DESTDIR}/var/lib/pcsd

tarball:
	$(PYTHON) setup.py sdist --formats=tar
	$(PYTHON) maketarballs.py

newversion:
	$(PYTHON) newversion.py
