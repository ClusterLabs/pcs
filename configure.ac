# Process this file with autoconf to produce a configure script.

AC_PREREQ([2.63])

AC_INIT([pcs],
	m4_esyscmd([make/git-version-gen .tarball-version]),
	[developers@clusterlabs.org])

AC_CONFIG_AUX_DIR([.])

AM_INIT_AUTOMAKE([dist-bzip2 dist-xz])

AC_CONFIG_MACRO_DIR([m4])
AC_CONFIG_SRCDIR([setup.py])

AC_CANONICAL_HOST

AC_LANG([C])

# Sanitize path

if test "$prefix" = "NONE"; then
	prefix="/usr"
	if test "$localstatedir" = "\${prefix}/var"; then
		localstatedir="/var"
	fi
	if test "$sysconfdir" = "\${prefix}/etc"; then
		sysconfdir="/etc"
	fi
	if test "$libdir" = "\${exec_prefix}/lib"; then
		if test -e /usr/lib64; then
			libdir="/usr/lib64"
		else
			libdir="/usr/lib"
		fi
	fi
fi

case $exec_prefix in
  NONE)   exec_prefix=$prefix;;
  prefix) exec_prefix=$prefix;;
esac

# Checks for programs.

# check stolen from gnulib/m4/gnu-make.m4
if ! ${MAKE-make} --version /cannot/make/this >/dev/null 2>&1; then
	AC_MSG_ERROR([you don't seem to have GNU make; it is required])
fi

AC_PROG_LN_S
AC_PROG_INSTALL
AC_PROG_MAKE_SET
AC_PROG_AWK
PKG_PROG_PKG_CONFIG
AM_PATH_PYTHON([3.6])

# check for systemd
PKG_CHECK_MODULES([systemd], [systemd])
PKG_CHECK_VAR([SYSTEMD_UNIT_DIR], [systemd], [systemdsystemunitdir])
if test "x$SYSTEMD_UNIT_DIR" == "x"; then
	AC_MSG_ERROR([Unable to detect systemd unit dir automatically])
fi
AC_SUBST([SYSTEMD_UNIT_DIR])

# check for ruby
PKG_CHECK_MODULES([ruby], [ruby >= 2.5])
PKG_CHECK_VAR([RUBY_VER], [ruby], [ruby_version])
if test "x$RUBY_VER" == "x"; then
	AC_MSG_ERROR([Unable to detect ruby version dir automatically])
fi
AC_SUBST([RUBY_VER])
AC_CHECK_PROGS([GEM], [gem])
if test x$GEM == x; then
	AC_MSG_ERROR([Unable to find gem binary])
fi
AC_SUBST([GEM])

AC_ARG_ENABLE([destructive-tests],
	      [  --enable-destructive-tests           Automatically execute potentially dangerous tests when running make check (default: no)], [destructive_tests="yes"])
AM_CONDITIONAL([EXECUTE_TIER1_TESTS], [test "x$destructive_tests" == "xyes"])

AC_ARG_ENABLE([local-build],
	      [  --enable-local-build           Download and install all dependencies as user / bundles], [local_build="yes"])
AM_CONDITIONAL([LOCAL_BUILD], [test "x$local_build" == "xyes"])

BUNDLE_DIR_LOCAL="pcs/bundled"
AC_SUBST([BUNDLE_DIR_LOCAL])
if test "x$local_build" == "xyes"; then
	BUNDLE_DIR="pcs/bundled"
else
	BUNDLE_DIR="$libdir/pcs/bundled"
fi
AC_SUBST([BUNDLE_DIR])

# required to install python requirements
AC_CHECK_PROGS([PIP], [pip])
if test "x$local_build" == "xyes"; then
	if test x$PIP == x; then
		AC_MSG_ERROR([Unable to find pip binary])
	fi
fi

# used to measure time for some tests, not critical if not available
AC_CHECK_PROGS([TIME], [time])

# used only for testing and reformatting
# if binary is not availalbe in the system, it will be installed by local-build (if enabled)
AC_CHECK_PROGS([BLACK], [black])
if test "x$local_build" != "xyes"; then
	if test "x$BLACK" == "x"; then
		AC_MSG_ERROR([Unable to find black binary. Either execute make install_python_deps or install python black])
	fi
else
	BLACK="black"
	AC_SUBST([BLACK])
fi

# if binary is not availalbe in the system, it will be installed by local-build (if enabled)
AC_CHECK_PROGS([MYPY], [mypy])
if test "x$local_build" != "xyes"; then
	if test "x$MYPY" == "x"; then
		AC_MSG_ERROR([Unable to find mypy binary. Either execute make install_python_deps or install python black])
	fi
else
	MYPY=mypy
	AC_SUBST([MYPY])
fi

MOD_FAILURE=""
if test "x$local_build" != "xyes"; then
	MOD_FAILURE=yes
fi

# python section

PYTHON_LIST="pyagentx astroid pylint tornado dacite dateutil"

# commodity function
PYTHON_LIST_EMBEDDED=""

AC_DEFUN([PCS_CHECK_PYMOD],[
	  AC_PYTHON_MODULE([$1], [$2])
	  res=$(eval echo "$AS_TR_CPP([HAVE_PYMOD_$1])")
	  if test "x$res" == "xno"; then
		  PYTHON_LIST_EMBEDDED="$1 $PYTHON_LIST_EMBEDDED"
	  fi
	  ])

for i in $PYTHON_LIST; do
	PCS_CHECK_PYMOD([$i], [$MOD_FAILURE])
done

if test -n "$PYTHON_LIST_EMBEDDED"; then
	AC_MSG_RESULT([The following python modules will be embedded in the build: $PYTHON_LIST_EMBEDDED])
fi

# special case, because we need to download from github
if test "x$HAVE_PYMOD_PYAGENTX" == "xno"; then
	AC_CHECK_PROGS([WGET], [wget])
	if test "x$WGET" == "x"; then
		AC_MSG_ERROR([Unable to find wget binary.])
	fi
	AC_CHECK_PROGS([TAR], [tar])
	if test "x$TAR" == "x"; then
		AC_MSG_ERROR([Unable to find tar binary.])
	fi
fi
AM_CONDITIONAL([BUILD_PYMOD_PYAGENTX], [test "x$HAVE_PYMOD_PYAGENTX" == "xno"])

# ruby gem section

# keep the list of gems requirements

GEM_LIST="backports daemons ethon ffi eventmachine json mustermann ruby2_keywords open4 power_assert rack rack-protection rack-test sinatra tilt test-unit thin"

# commodity function
GEM_LIST_EMBEDDED=""

AC_DEFUN([PCS_CHECK_GEM],[
	  AC_RUBY_GEM([$1], [$2])
	  res=$(eval echo "$AS_TR_CPP([HAVE_RUBYGEM_$1])")
	  if test "x$res" == "xno"; then
		  GEM_LIST_EMBEDDED="$1 $GEM_LIST_EMBEDDED"
	  fi
	  ])

RUBY_GEM_FAILURE=""
if test "x$local_build" != "xyes"; then
	RUBY_GEM_FAILURE=yes
fi

for i in $GEM_LIST; do
	PCS_CHECK_GEM([$i], [$RUBY_GEM_FAILURE])
done

if test -n "$GEM_LIST_EMBEDDED"; then
	AC_MSG_RESULT([The following gems will be embedded in the build: $GEM_LIST_EMBEDDED])
fi

AC_ARG_WITH([default-config-dir],
	    [  --with-default-config-dir=DIR  pcs config directory. Default: $sysconfdir/sysconfig ],
	    [ CONF_DIR="$withval" ],
	    [ CONF_DIR="$sysconfdir/sysconfig" ])
AC_SUBST([CONF_DIR])

AC_ARG_WITH([pcs-lib-dir],
	    [  --with-pcs-lib-dir=DIR         pcs lib directory. Default: $libdir ],
	    [ LIB_DIR="$withval" ],
	    [ LIB_DIR="$libdir" ])
AC_SUBST([LIB_DIR])

AC_ARG_WITH([snmp-mibs-dir],
	    [  --with-snmp-mibs-dir=DIR      snmp MIB directory. Default: $prefix/share/snmp/mibs ],
	    [ SNMP_MIB_DIR="$withval" ],
	    [ SNMP_MIB_DIR="$prefix/share/snmp/mibs" ])
AC_SUBST([SNMP_MIB_DIR])

AC_CONFIG_FILES([Makefile
		 pcs/Makefile
		 pcs/snmp/pcs_snmp_agent.service
		 pcsd/Makefile
		 pcsd/logrotate/pcsd])

AC_OUTPUT
