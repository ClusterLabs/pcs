ifndef PYTHON_SITELIB
  PYTHON_SITELIB=$(shell python -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")
endif
ifeq ($(PYTHON_SITELIB), /usr/lib/python2.6/dist-packages)
  EXTRA_SETUP_OPTS="--install-layout=deb"
endif
ifeq ($(PYTHON_SITELIB), /usr/lib/python2.7/dist-packages)
  EXTRA_SETUP_OPTS="--install-layout=deb"
endif

IS_SYSTEMCTL=false
ifeq ("$(wildcard /usr/bin/systemctl)","/usr/bin/systemctl")
  IS_SYSTEMCTL=true
else
  ifeq ("$(wildcard /bin/systemctl)","/usr/bin/systemctl")
    IS_SYSTEMCTL=true
  endif
endif

MANDIR=/usr/share/man

ifndef PREFIX
  PREFIX=$(shell prefix=`python -c "import sys; print(sys.prefix)"` || prefix="/usr"; echo $$prefix)
endif

ifndef initdir
  initdir=/etc/init.d
endif

install: bash_completion
	python setup.py install --prefix ${DESTDIR}${PREFIX} ${EXTRA_SETUP_OPTS}
	mkdir -p ${DESTDIR}${PREFIX}/sbin/
	chmod 755 ${DESTDIR}${PYTHON_SITELIB}/pcs/pcs.py
	ln -fs ${PYTHON_SITELIB}/pcs/pcs.py ${DESTDIR}${PREFIX}/sbin/pcs
	install -D pcs/bash_completion.d.pcs ${DESTDIR}/etc/bash_completion.d/pcs
	install -m644 -D pcs/pcs.8 ${DESTDIR}/${MANDIR}/man8/pcs.8

install_pcsd:
	make -C pcsd build_gems
	mkdir -p ${DESTDIR}/var/log/pcsd
	mkdir -p ${DESTDIR}${PREFIX}/lib/
	cp -r pcsd ${DESTDIR}${PREFIX}/lib/
	install -m 644 -D pcsd/pcsd.conf ${DESTDIR}/etc/sysconfig/pcsd
	install -d ${DESTDIR}/etc/pam.d
	install  pcsd/pcsd.pam ${DESTDIR}/etc/pam.d/pcsd
	install -m 700 -d ${DESTDIR}/var/lib/pcsd
	install -m 644 -D pcsd/pcsd.logrotate ${DESTDIR}/etc/logrotate.d/pcsd
ifeq ($(IS_SYSTEMCTL),true)
	install -d ${DESTDIR}/usr/lib/systemd/system/
	install -m 644 pcsd/pcsd.service ${DESTDIR}/usr/lib/systemd/system/
else
	install -m 755 -D pcsd/pcsd ${DESTDIR}/${initdir}/pcsd
endif

uninstall:
	rm -f ${DESTDIR}${PREFIX}/sbin/pcs
	rm -rf ${DESTDIR}${PYTHON_SITELIB}/pcs
	rm -rf ${DESTDIR}${PREFIX}/lib/pcsd
ifeq ($(IS_SYSTEMCTL),true)
	rm -f ${DESTDIR}/usr/lib/systemd/system/pcsd.service
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
