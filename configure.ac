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
PKG_CHECK_MODULES([systemd], [systemd], [SYSTEMD=yes], [SYSTEMD=no])
if test "$SYSTEMD" == yes; then
	PKG_CHECK_VAR([SYSTEMD_UNIT_DIR], [systemd], [systemdsystemunitdir])
	if test "x$SYSTEMD_UNIT_DIR" == "x"; then
		AC_MSG_ERROR([Unable to detect systemd unit dir automatically])
	fi
fi
AM_CONDITIONAL([SYSTEMD], [test "$SYSTEMD" == yes])

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

AC_CONFIG_FILES([Makefile])

AC_OUTPUT
