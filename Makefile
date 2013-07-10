ifndef PYTHON_SITELIB
  PYTHON_SITELIB=$(shell python -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")
endif
ifeq ($(PYTHON_SITELIB), /usr/lib/python2.6/dist-packages)
  EXTRA_SETUP_OPTS="--install-layout=deb"
endif

ifndef PREFIX
  PREFIX=/usr
endif

install:
	python setup.py install --prefix ${DESTDIR}${PREFIX} ${EXTRA_SETUP_OPTS}
	mkdir -p ${DESTDIR}${PREFIX}/sbin/
	chmod 755 ${DESTDIR}${PYTHON_SITELIB}/pcs/pcs.py
	ln -fs ${PYTHON_SITELIB}/pcs/pcs.py ${DESTDIR}${PREFIX}/sbin/pcs


install_pcsd:
	make -C pcsd build_gems
	mkdir -p ${DESTDIR}/var/log/pcsd
	mkdir -p ${DESTDIR}${PREFIX}/lib/
	cp -r pcsd ${DESTDIR}${PREFIX}/lib/
	install -D pcsd/pcsd.conf ${DESTDIR}/etc/sysconfig/pcsd
	install -d ${DESTDIR}/usr/lib/systemd/system/
	install  pcsd/pcsd.service ${DESTDIR}/usr/lib/systemd/system/
	install -d ${DESTDIR}/etc/pam.d
	install  pcsd/pcsd.pam ${DESTDIR}/etc/pam.d/pcsd
	install -m 700 -d ${DESTDIR}/var/lib/pcsd


uninstall:
	rm -f ${DESTDIR}${PREFIX}/sbin/pcs
	rm -rf ${DESTDIR}${PYTHON_SITELIB}/pcs
	rm -rf ${DESTDIR}${PREFIX}/lib/pcsd
	rm -f ${DESTDIR}/usr/lib/systemd/system/pcsd.service
	rm -f ${DESTDIR}/etc/pam.d/pcsd
	rm -rf ${DESTDIR}/var/lib/pcsd

tarball:
	python setup.py sdist

docs:
	help2man -s 8 -N -h '--fullhelp' --output=pcs/pcs.8 --name='pacemaker/corosync configuration system' pcs/pcs.py
