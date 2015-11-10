# Compatibility with GNU/Linux [i.e. Debian] based distros
UNAME_OS_GNU := $(shell if uname -o | grep -q "GNU/Linux" ; then echo true; else echo false; fi)
UNAME_KERNEL_DEBIAN := $(shell if uname -v | grep -q "Debian\|Ubuntu" ; then echo true; else echo false; fi)
IS_DEBIAN=false
UNAME_DEBIAN_VER_8=false

ifeq ($(UNAME_OS_GNU),true)
  ifeq ($(UNAME_KERNEL_DEBIAN),true)
    IS_DEBIAN=true
    UNAME_DEBIAN_VER_8 := $(shell if grep -q -i "8" /etc/debian_version ; then echo true; else echo false; fi)
    settings_x86_64 := $(shell if uname -m | grep -q -i "x86_64" ; then echo true; else echo false; fi)
    settings_i386=false
    ifeq ($(settings_x86_64),false)
      settings_i386 := $(shell if uname -m | grep -q -i "i386" ; then echo true; else echo false; fi)
    endif
  endif
endif

ifndef PYTHON_SITELIB
  PYTHON_SITELIB=$(shell python -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")
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
  PREFIX=$(shell prefix=`python -c "import sys; print(sys.prefix)"` || prefix="/usr"; echo $$prefix)
endif

ifndef systemddir
  systemddir=/usr/lib/systemd
endif

ifndef initdir
  initdir=/etc/init.d
endif

ifndef install_settings
  install_settings=false
else
  ifeq ($(install_settings),true)
    ifeq ($(settings_x86_64),true)
      settings_file=settings.py.x86_64-linux-gnu.debian
      settings_file_pcsd=settings.rb.x86_64-linux-gnu.debian
    else
      ifeq ($(settings_i386),true)
        settings_file=settings.py.i386-linux-gnu.debian
        settings_file_pcsd=settings.rb.i386-linux-gnu.debian
      endif
    endif
  endif
endif

install: bash_completion
	python setup.py install --prefix ${DESTDIR}${PREFIX} ${EXTRA_SETUP_OPTS}
	mkdir -p ${DESTDIR}${PREFIX}/sbin/
	chmod 755 ${DESTDIR}${PYTHON_SITELIB}/pcs/pcs.py
	ln -fs ${PYTHON_SITELIB}/pcs/pcs.py ${DESTDIR}${PREFIX}/sbin/pcs
	install -D pcs/bash_completion.d.pcs ${DESTDIR}/etc/bash_completion.d/pcs
	install -m644 -D pcs/pcs.8 ${DESTDIR}/${MANDIR}/man8/pcs.8
ifeq ($(IS_DEBIAN),true)
  ifeq ($(install_settings),true)
	rm -f  ${DESTDIR}${PYTHON_SITELIB}/pcs/settings.py
	install -m755 pcs/${settings_file} ${DESTDIR}${PYTHON_SITELIB}/pcs/settings.py
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
	install -m755 pcsd/${settings_file_pcsd} ${DESTDIR}/usr/share/pcsd/settings.rb
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

tarball: bash_completion
	python setup.py sdist --formats=tar
	python maketarballs.py

newversion:
	python newversion.py

bash_completion:
	cd pcs ; python -c 'import usage;  usage.sub_generate_bash_completion()' > bash_completion.d.pcs ; cd ..
