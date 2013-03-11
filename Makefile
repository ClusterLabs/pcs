ifndef PYTHON_SITELIB
  PYTHON_SITELIB=`python -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())"`
endif
ifndef PREFIX
  PREFIX=/usr
endif

install:
	python setup.py install --prefix ${DESTDIR}${PREFIX}
	mkdir -p ${DESTDIR}${PREFIX}/sbin/
	chmod 755 ${DESTDIR}${PYTHON_SITELIB}/pcs/pcs.py
	ln -fs ${PYTHON_SITELIB}/pcs/pcs.py ${DESTDIR}${PREFIX}/sbin/pcs
	make install_pcsd


install_pcsd:
	make -C pcsd build_gems
	mkdir -p ${DESTDIR}${PREFIX}/lib/
	cp -r pcsd ${DESTDIR}${PREFIX}/lib/pcsd
	install -d ${DESTDIR}/usr/lib/systemd/system/
	install  pcsd/pcsd.service ${DESTDIR}/usr/lib/systemd/system/
	install -d ${DESTDIR}/etc/pam.d
	install  pcsd/pcsd.pam ${DESTDIR}/etc/pam.d/pcsd
	install -d ${DESTDIR}/var/lib/pcsd


uninstall:
	rm -f ${DESTDIR}${PREFIX}/sbin/pcs
	rm -rf ${DESTDIR}${PYTHON_SITELIB}/pcs
	rm -rf ${DESTDIR}${PREFIX}/lib/pcsd
	rm -f ${DESTDIR}/usr/lib/systemd/system/pcsd.service
	rm -f ${DESTDIR}/etc/pam.d/pcsd
	rm -rf ${DESTDIR}/var/lib/pcsd

tarball:
	python setup.py sdist

