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
	ln -s ${PYTHON_SITELIB}/pcs/pcs.py ${DESTDIR}${PREFIX}/sbin/pcs

uninstall:
	rm -f ${DESTDIR}${PREFIX}/sbin/pcs
	rm -rf ${DESTDIR}${PYTHON_SITELIB}/pcs*

tarball:
	python setup.py sdist

