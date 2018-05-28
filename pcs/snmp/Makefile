# Default pyagentx version should by for python3 since python 2 is no longer
# supported in pcs-0.10 branch.
PYAGENTX_VERSION="0.4.pcs.2"
PYAGENTX_URI="https://github.com/ondrejmular/pyagentx/archive/v${PYAGENTX_VERSION}.tar.gz"

ifndef PYTHON
	PYTHON := $(shell which python3 || which python2 || which python)
endif

ifndef PREFIX
  PREFIX=$(shell prefix=`$(PYTHON) -c "import sys; print(sys.prefix)"` || prefix="/usr"; echo $$prefix)
endif

ifndef PCS_PARENT_DIR
  PCS_PARENT_DIR=${DESTDIR}/${PREFIX}/lib/pcs
endif

ifndef BUNDLED_LIB_DIR
  BUNDLED_LIB_DIR=../bundled/
endif
ifndef BUNDLED_LIB_DIR_ABS
  BUNDLED_LIB_DIR_ABS=$(shell readlink -f ${BUNDLED_LIB_DIR})
endif
BUNDLES_TMP_DIR=${BUNDLED_LIB_DIR_ABS}/tmp

PYAGENTX_PROVIDED=true
ifndef PYAGENTX_DIR
  PYAGENTX_PROVIDED=false
  PYAGENTX_DIR=${BUNDLES_TMP_DIR}/pyagentx-${PYAGENTX_VERSION}
endif

get_pyagentx:
ifeq (${PYAGENTX_PROVIDED},false)
	rm -rf ${PYAGENTX_DIR}
	mkdir -p ${BUNDLES_TMP_DIR}
	wget -qO- ${PYAGENTX_URI} | tar xvz -C ${BUNDLES_TMP_DIR}
endif

build_pyagentx: get_pyagentx
ifdef PYAGENTX_DIR
	# prefix must be explicit since fedora uses /usr/local as default when
	# environment variable RPM_BUILD_ROOT is not set.
	cd ${PYAGENTX_DIR} && PYTHONPATH=${BUNDLED_LIB_DIR_ABS}/packages/ $(PYTHON) setup.py install --prefix=${PREFIX} --install-purelib /packages/ --root ${BUNDLED_LIB_DIR_ABS}
endif

build_bundled_libs: build_pyagentx

clean:
	rm -rf ${BUNDLES_TMP_DIR}/pyagentx*
	rm -rf ${BUNDLED_LIB_DIR_ABS}/packages/pyagentx*
