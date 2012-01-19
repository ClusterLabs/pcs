install:
	python setup.py install --prefix ${DESTDIR}/usr
	mkdir -p ${DESTDIR}/usr/sbin/
	ln -s ${PYTHON_SITELIB}/pcs/pcs.py ${DESTDIR}/usr/sbin/pcs
