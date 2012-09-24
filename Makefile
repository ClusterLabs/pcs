ifndef PYTHON_SITELIB
  PYTHON_SITELIB=`python -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())"`
endif

install:
	python setup.py install --prefix ${DESTDIR}/usr
	mkdir -p ${DESTDIR}/usr/sbin/
	chmod 755 ${DESTDIR}/${PYTHON_SITELIB}/pcs/pcs.py
	ln -s ${PYTHON_SITELIB}/pcs/pcs.py ${DESTDIR}/usr/sbin/pcs

tarball:
	python setup.py sdist
