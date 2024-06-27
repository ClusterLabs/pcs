# Process this file with autoconf to produce a configure script.

AC_PREREQ([2.63])

AC_INIT([pcs],
	m4_esyscmd([make/git-version-gen .tarball-version .gitarchivever]),
	[developers@clusterlabs.org])

AC_CONFIG_AUX_DIR([.])

AM_INIT_AUTOMAKE([dist-bzip2 dist-xz -Wno-portability tar-pax])

AC_CONFIG_MACRO_DIR([m4])
AC_CONFIG_SRCDIR([setup.py.in])

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

# need to expand a bunch of paths to make sure
# the embedded values in files are absolute paths
eval SBINDIR="`eval echo ${sbindir}`"
AC_SUBST([SBINDIR])
eval LOCALSTATEDIR="`eval echo ${localstatedir}`"
AC_SUBST([LOCALSTATEDIR])
eval LIBDIR="`eval echo ${libdir}`"

# Checks for programs.

# check stolen from gnulib/m4/gnu-make.m4
if ! ${MAKE-make} --version /cannot/make/this >/dev/null 2>&1; then
	AC_MSG_ERROR([you don't seem to have GNU make; it is required])
fi

AC_PROG_LN_S
AC_PROG_INSTALL
AC_PROG_MAKE_SET
AC_PROG_AWK
AC_PROG_MKDIR_P

PKG_PROG_PKG_CONFIG

# check for python
AM_PATH_PYTHON([3.9])
eval PYTHON_SITELIB="`eval echo ${pythondir}`"
AC_SUBST([PYTHON_SITELIB])
# required to detect / install python modules
if ! $PYTHON -m pip > /dev/null 2>&1; then
	AC_MSG_ERROR([Python module pip not found])
fi
PIP="$PYTHON -m pip"
AC_SUBST([PIP])

# use a wrapper to call into PKG_CHECK_VAR to allow to set a default
AC_DEFUN([PCS_PKG_CHECK_VAR], [
	  varname=$1
	  default=$4
	  AC_MSG_CHECKING([for pkg-conf $2 var $3])
	  PKG_CHECK_VAR([$1], [$2], [$3])
	  AS_VAR_IF([$1], [""],
		    [AS_VAR_IF([default], [""],
			      AC_MSG_ERROR([not found]),
			      [AS_VAR_COPY([$varname], [default]) && AC_MSG_RESULT([not found, using default ${!varname}])])],
		    [AC_MSG_RESULT([yes (detected: ${!varname})])])
])

# check for systemd
PKG_CHECK_MODULES([systemd], [systemd])
PCS_PKG_CHECK_VAR([SYSTEMD_UNIT_DIR_TMP], [systemd], [systemdsystemunitdir], [/usr/lib/systemd/system])
if test "${prefix}" != "/usr"; then
	SYSTEMD_UNIT_DIR="${prefix}/$SYSTEMD_UNIT_DIR_TMP"
else
	SYSTEMD_UNIT_DIR="$SYSTEMD_UNIT_DIR_TMP"
fi
AC_SUBST([SYSTEMD_UNIT_DIR])
PCS_PKG_CHECK_VAR([SYSTEMD_UNIT_PATH], [systemd], [systemdsystemunitpath],
		  [/etc/systemd/system:/etc/systemd/system:/run/systemd/system:/usr/local/lib/systemd/system:/usr/lib/systemd/system:/usr/lib/systemd/system:/lib/systemd/system])
AC_SUBST([SYSTEMD_UNIT_PATH])

# check for ruby
AC_PATH_PROG([RUBY], [ruby])
if test x$RUBY = x; then
	AC_MSG_ERROR([Unable to find ruby binary])
fi

# opensuse has a versioned ruby-$version.pc file
# that does not match fedora or rhel ruby.pc
# so we need to detect it
rubymod=`pkg-config --list-all | awk '{print $1}' | grep ^ruby | sort -n | tail -n 1`

PKG_CHECK_MODULES([ruby], [$rubymod >= 2.5])
PCS_PKG_CHECK_VAR([RUBY_VER], [$rubymod], [ruby_version])
AC_CHECK_PROGS([GEM], [gem])
if test "x$GEM" = "x"; then
	AC_MSG_ERROR([Unable to find gem binary])
fi
# used to measure time for some tests, not critical if not available
AC_CHECK_PROGS([TIME], [time])

# required to build rpm and pyagentx
AC_CHECK_PROGS([TAR], [tar])
if test "x$TAR" = "x"; then
	AC_MSG_ERROR([Unable to find tar binary.])
fi

# configure options section
AC_ARG_ENABLE([dev-tests],
	      [AS_HELP_STRING([--enable-dev-tests], [Enable extra developers tests (black, isort, mypy, pylint) (default: no)])],
	      [dev_tests="yes"])
AM_CONDITIONAL([DEV_TESTS], [test "x$dev_tests" = "xyes"])

AC_ARG_ENABLE([destructive-tests],
	      [AS_HELP_STRING([--enable-destructive-tests], [Automatically execute potentially dangerous tests when running make check (default: no)])],
	      [destructive_tests="yes"])
AM_CONDITIONAL([EXECUTE_TIER1_TESTS], [test "x$destructive_tests" = "xyes"])

AC_ARG_ENABLE([concise-tests],
	      [AS_HELP_STRING([--enable-concise-tests], [Make tests output brief by not printing a name of each test (default: no)])],
	      [concise_tests="yes"])
AM_CONDITIONAL([CONCISE_TESTS], [test "x$concise_tests" = "xyes"])

AC_ARG_ENABLE([parallel-pylint],
	      [AS_HELP_STRING([--enable-parallel-pylint], [Enable running pylint in multiple threads (default: no)])],
	      [parallel_pylint="yes"])
AM_CONDITIONAL([PARALLEL_PYLINT], [test "x$parallel_pylint" = "xyes"])

AC_ARG_ENABLE([typos-check],
	      [AS_HELP_STRING([--enable-typos-check], [Enable checking source code for typos (needs https://github.com/crate-ci/typos to be installed) (default: no)])],
	      [typos_check="yes"])
AM_CONDITIONAL([TYPOS_CHECK], [test "x$typos_check" = "xyes"])

AC_ARG_ENABLE([local-build],
	      [AS_HELP_STRING([--enable-local-build], [Download and install all dependencies as user / bundles])],
	      [local_build="yes"])
AM_CONDITIONAL([LOCAL_BUILD], [test "x$local_build" = "xyes"])

AC_ARG_ENABLE([tests-only],
	      [AS_HELP_STRING([--enable-tests-only], [Check only for tests dependencies])],
	      [tests_only="yes"])

AC_ARG_ENABLE([individual-bundling],
	      [AS_HELP_STRING([--enable-individual-bundling], [Bundle only missing python packages /ruby gems instead of all of them])],
	      [individual_bundling="yes"])

AC_ARG_ENABLE([use-local-cache-only],
	      [AS_HELP_STRING([--enable-use-local-cache-only], [Use only local cache to build bundles and disable downloads])],
	      [cache_only="yes"])

# This should be removed in the next major release
AC_ARG_ENABLE([booth-enable-authfile-set],
	      [AS_HELP_STRING([--enable-booth-enable-authfile-set], [Enable support for setting enable-authfile booth option])],
	      [booth_enable_authfile_set="yes"])

# This should stay here for at least another major release after booth-enable-authfile-set is removed
AC_ARG_ENABLE([booth-enable-authfile-unset],
	      [AS_HELP_STRING([--enable-booth-enable-authfile-unset], [Enable support for removing enable-authfile booth option])],
	      [booth_enable_authfile_unset="yes"])

# this will catch both ID and ID_LIKE from os-release
AC_ARG_WITH([distro],
	    [AS_HELP_STRING([--with-distro=DIR], [Set defaults to specified distro. Default: autodetected])],
	    [DISTRO="$withval"])

AC_ARG_WITH([pcsd-default-cipherlist],
	[AS_HELP_STRING([--with-pcsd-default-cipherlist=CIPHERLIST],
		[Default pcsd server OpenSSL cipher list. Default: DEFAULT:!RC4:!3DES:@STRENGTH])],
	[PCSD_DEFAULT_CIPHERLIST="$withval"],
	[PCSD_DEFAULT_CIPHERLIST="DEFAULT:!RC4:!3DES:@STRENGTH"])
AC_SUBST([PCSD_DEFAULT_CIPHERLIST])

if test "x$cache_only" != "xyes"; then
	AC_CHECK_PROGS([WGET], [wget])
	if test "x$WGET" = "x"; then
		AC_MSG_ERROR([Unable to find wget binary.])
	fi
fi

if test "x$typos_check" = "xyes"; then
	AC_PATH_PROG([DIFF], [diff])
	if test "x$DIFF" = "x"; then
		AC_MSG_ERROR([Unable to find diff in $PATH])
	fi
	AC_PATH_PROG([SORT], [sort])
	if test "x$SORT" = "x"; then
		AC_MSG_ERROR([Unable to find sort in $PATH])
	fi
	AC_PATH_PROG([TYPOS], [typos])
	if test "x$TYPOS" = "x"; then
		AC_MSG_ERROR([Unable to find typos in $PATH])
	fi
fi

if test "x$DISTRO" = "x"; then
	AC_MSG_CHECKING([linux distribution])
	if test -f /etc/os-release; then
		DISTRO=$(cat /etc/os-release | grep ^ID= | cut -d "=" -f 2 | sed -s 's#"##g')
		if test "x$DISTRO" = "x"; then
			AC_MSG_ERROR([Unable to detect linux distribution. Please specify --with-distro=])
		fi
		DISTROS=$(cat /etc/os-release | grep ^ID_LIKE= | cut -d "=" -f 2 | sed -s 's#"##g')
	fi
	AC_MSG_RESULT([$DISTRO])
else
	AC_MSG_RESULT([Distro detection disabled. Setting forced to: $DISTRO])
fi

AC_MSG_CHECKING([default settings for $DISTRO $DISTROS])
for i in $DISTRO $DISTROS; do
	case $i in
		debian|ubuntu)
			FOUND_DISTRO=1
			CONFIGDIR="$sysconfdir/default"
			PCSLIBDIR="$prefix/share"
			PCMKDAEMONDIR="$prefix/lib/pacemaker"
			COROSYNCLOGDIR="$localstatedir/log/corosync"
			DISTROEXT=debian
			break
		;;
		fedora*|rhel|centos|centos-stream*|opensuse*)
			FOUND_DISTRO=1
			CONFIGDIR="$sysconfdir/sysconfig"
			PCSLIBDIR="$LIBDIR"
			PCMKDAEMONDIR="$prefix/libexec/pacemaker"
			COROSYNCLOGDIR="$localstatedir/log/cluster"
			DISTROEXT=fedora
			break
		;;
		opencloudos)
			FOUND_DISTRO=1
			CONFIGDIR="$sysconfdir/sysconfig"
			PCSLIBDIR="$LIBDIR"
			PCMKDAEMONDIR="$prefix/libexec/pacemaker"
			COROSYNCLOGDIR="$localstatedir/log/cluster"
			DISTROEXT=opencloudos
			break
		;;
	esac
done

if test "x$FOUND_DISTRO" = "x"; then
	AC_MSG_RESULT([not found])
	AC_MSG_ERROR([Unknown distribution $DISTRO. Please contact pcs upstream project to add support, or check --with-distro= value])
else
	AC_MSG_RESULT([$i (or alike) default settings will be used])
fi

AC_SUBST([DISTROEXT])

AC_ARG_WITH([default-config-dir],
	    [AS_HELP_STRING([--with-default-config-dir=DIR], [pcs config directory. Default: autodetected])],
	    [CONF_DIR="$withval"],
	    [CONF_DIR="$CONFIGDIR"])
AC_SUBST([CONF_DIR])

AC_ARG_WITH([pcs-lib-dir],
	    [AS_HELP_STRING([--with-pcs-lib-dir=DIR], [pcs lib directory. Default: autodetected])],
	    [LIB_DIR="$withval"],
	    [LIB_DIR="$PCSLIBDIR"])
AC_SUBST([LIB_DIR])

AC_ARG_WITH([snmp-mibs-dir],
	    [AS_HELP_STRING([--with-snmp-mibs-dir=DIR], [snmp MIB directory. Default: $prefix/share/snmp/mibs])],
	    [SNMP_MIB_DIR="$withval"],
	    [SNMP_MIB_DIR="$prefix/share/snmp/mibs"])
AC_SUBST([SNMP_MIB_DIR])

# python detection section
PCS_BUNDLED_DIR_LOCAL="pcs_bundled"
AC_SUBST([PCS_BUNDLED_DIR_LOCAL])
PCS_BUNDLED_DIR="$LIB_DIR/pcs/$PCS_BUNDLED_DIR_LOCAL"
AC_SUBST([PCS_BUNDLED_DIR])

mkdir -p $ac_pwd/stamps
mkdir -p $ac_pwd/rpm/
rm -rf $ac_pwd/rpm/requirements.txt
touch $ac_pwd/rpm/requirements.txt

# PCS_BUNDLE_PYMOD([module], [version])
AC_DEFUN([PCS_BUNDLE_PYMOD], [
	echo "$1 $2" | sed -e 's# ##g' >> $ac_pwd/rpm/requirements.txt
	if test "x$cache_only" = "xyes"; then
		src=`ls rpm/$1-*`
		if test "x$src" = "x"; then
			 AC_MSG_ERROR([cache only build required but no source detected in rpm/])
		fi
	fi
])

# PCS_CHECK_PYMOD([module], [version], [embedded=yes])
AC_DEFUN([PCS_CHECK_PYMOD], [
	if test "x$local_build" = "xyes" && test "x$3" = "xyes"; then
		AC_PIP_MODULE([$1], [$2], [bundle_module=no], [bundle_module=yes], [bundle_module=yes])
		if test "x$bundle_module" = "xyes" || test "x$individual_bundling" != "xyes"; then
			PCS_BUNDLE_PYMOD([$1], [$2])
		fi
	else
		AC_PIP_MODULE([$1], [$2], [], [AC_MSG_ERROR([Python module $1 not found])])
	fi
])

# required by rpm build
PYAGENTX_VERSION=0.4.pcs.2
AC_SUBST([PYAGENTX_VERSION])

# those MUST be available in BaseOS

# required for --no-build-isolation
AC_PIP_MODULE([pip], [>= 10.0.0], [have_isolation=yes], [have_isolation=no], [have_isolation=no])
AM_CONDITIONAL([PIP_HAS_ISOLATION], [test "x$have_isolation" = xyes])

if test "x$tests_only" != "xyes"; then
	PCS_CHECK_PYMOD([setuptools])
	if test "x$local_build" = "xyes"; then
		PCS_CHECK_PYMOD([wheel])
	fi
	PCS_CHECK_PYMOD([cryptography])
	PCS_CHECK_PYMOD([lxml])
	PCS_CHECK_PYMOD([pycurl])
	PCS_CHECK_PYMOD([pyparsing])

	# those are kind of problematic.
	# use them all from the BaseOS or embedded them all as necessary (--enable-local-build)
	PCS_CHECK_PYMOD([dacite], [], [yes])
	PCS_CHECK_PYMOD([tornado], [>= 6.0.0], [yes])
	PCS_CHECK_PYMOD([python-dateutil], [>= 2.7.0], [yes])
	# setuptoools_scm is needed for bundling dateutil, this uses variables
	# set by the CHECK_PYMOD macro, so it must be executed right after it
	if test "x$bundle_module" = "xyes" && test "x$cache_only" = "xyes"; then
		PCS_CHECK_PYMOD([setuptools-scm])
	fi

	# special case, because we need to download from github
	AC_PIP_MODULE([pyagentx])

	if test "x$HAVE_PIPMOD_PYAGENTX" = "xno" && test "x$local_build" != "xyes"; then
		AC_MSG_ERROR([Python module pyagentx not found])
	fi
fi

# ruby gem section

PCSD_BUNDLED_DIR_ROOT_LOCAL="pcsd/vendor/bundle/"
PCSD_BUNDLED_DIR_LOCAL="$PCSD_BUNDLED_DIR_ROOT_LOCAL/ruby/$RUBY_VER/"
PCSD_BUNDLED_CACHE_DIR="$PCSD_BUNDLED_DIR_ROOT_LOCAL/cache"
AC_SUBST([PCSD_BUNDLED_DIR_ROOT_LOCAL])
AC_SUBST([PCSD_BUNDLED_DIR_LOCAL])
AC_SUBST([PCSD_BUNDLED_CACHE_DIR])

rm -rf Gemfile Gemfile.lock
echo "source 'https://rubygems.org'" > Gemfile
echo "" >> Gemfile

# PCS_BUNDLE_GEM([module])
AC_DEFUN([PCS_BUNDLE_GEM], [
	echo "gem '$1'" >> Gemfile
	if test "x$cache_only" = "xyes"; then
		src=`ls $PCSD_BUNDLED_CACHE_DIR/$1-*`
		if test "x$src" = "x"; then
			AC_MSG_ERROR([cache only build required but no source detected in $PCSD_BUNDLED_CACHE_DIR])
		fi
	fi
])

# PCS_CHECK_GEM([module], [version])
AC_DEFUN([PCS_CHECK_GEM], [
	if test "x$local_build" = "xyes"; then
		AC_RUBY_GEM([$1], [$2], [], [PCS_BUNDLE_GEM([$1])])
	else
		AC_RUBY_GEM([$1], [$2], [], [AC_MSG_ERROR([ruby gem $1 not found])])
	fi
])

# PCS_GEM_ACTION([curversion], [op], [cmpversion][, action-if-true] [, action-if-false])
AC_DEFUN([PCS_GEM_ACTION], [
	if test -n "$1"; then
		AC_COMPARE_VERSIONS([$1], [$2], [$3], [$4], [$5])
	else
		true
		$5
	fi
])

PCS_CHECK_GEM([power_assert])
PCS_CHECK_GEM([test-unit])

RACK_HANDLER="Rackup"
REQUIRE_RACKUP="require 'rackup'"

if test "x$tests_only" != "xyes"; then
	PCS_CHECK_GEM([backports])
	PCS_CHECK_GEM([childprocess])
	PCS_CHECK_GEM([ethon])
	PCS_CHECK_GEM([ffi])
	PCS_CHECK_GEM([json])
	PCS_CHECK_GEM([ruby2_keywords])
	PCS_CHECK_GEM([mustermann])
	PCS_CHECK_GEM([rack])
	PCS_GEM_ACTION([$HAVE_RUBYGEM_RACK_VERSION], [<], [3.0], [RACK_HANDLER=Rack REQUIRE_RACKUP=""], [PCS_CHECK_GEM([rackup])])
	PCS_CHECK_GEM([rack-protection])
	PCS_GEM_ACTION([$HAVE_RUBYGEM_RACK_PROTECTION_VERSION], [<], [3.2.0], [], [PCS_CHECK_GEM([base64], [>= 0.1.0])])
	PCS_CHECK_GEM([rack-test])
	PCS_CHECK_GEM([sinatra])
	PCS_GEM_ACTION([$HAVE_RUBYGEM_SINATRA_VERSION], [<], [4.0.0], [], [PCS_CHECK_GEM([rack-session], [>= 2.0.0])])
	PCS_CHECK_GEM([tilt])
	PCS_CHECK_GEM([nio4r])
	PCS_CHECK_GEM([puma])
	PCS_CHECK_GEM([rexml])
fi
AC_SUBST([RACK_HANDLER])
AC_SUBST([REQUIRE_RACKUP])

if test "x$local_build" = "xyes" && test $(wc -l < Gemfile) -gt 2; then
	GEM_HOME="$LIB_DIR/$PCSD_BUNDLED_DIR_ROOT_LOCAL"
	SYSTEMD_GEM_HOME="Environment=GEM_HOME=$GEM_HOME"
	if test "x$cache_only" != "xyes"; then
		AC_CHECK_PROGS([BUNDLE], [bundle])
		if test "x$BUNDLE" = "x"; then
			AC_MSG_ERROR([Unable to find bundle binary required to install missing ruby gems])
		fi
	fi
fi
AC_SUBST([BUNDLE])
AC_SUBST([GEM])
AC_SUBST([GEM_HOME])
AC_SUBST([SYSTEMD_GEM_HOME])
AM_CONDITIONAL([INSTALL_EMBEDDED_GEMS], [test -n "$GEM_HOME"])

AM_CONDITIONAL([ENABLE_DOWNLOAD], [test "x$cache_only" != "xyes"])

if test "x$booth_enable_authfile_set" = "xyes"; then
	BOOTH_ENABLE_AUTHFILE_SET_DOC="
.TP
enable-authfile
Add option 'enable-authfile' to booth configuration. In some versions of booth, auhfile is not used by default and explicit enabling is required."
fi
if test "x$booth_enable_authfile_unset" = "xyes"; then
	BOOTH_ENABLE_AUTHFILE_UNSET_DOC="
.TP
clean-enable-authfile
Remove 'enable-authfile' option from booth configuration. This is useful when upgrading from booth that required the option to be present to a new version which doesn't tolerate the option."
fi
_AM_SUBST_NOTMAKE([BOOTH_ENABLE_AUTHFILE_SET_DOC])
_AM_SUBST_NOTMAKE([BOOTH_ENABLE_AUTHFILE_UNSET_DOC])
AC_SUBST([BOOTH_ENABLE_AUTHFILE_SET_DOC])
AC_SUBST([BOOTH_ENABLE_AUTHFILE_UNSET_DOC])
AC_SUBST([BOOTH_ENABLE_AUTHFILE_SET_ENABLED], [$(if test "x$booth_enable_authfile_set" = "xyes"; then echo "True"; else echo "False"; fi)])
AC_SUBST([BOOTH_ENABLE_AUTHFILE_UNSET_ENABLED], [$(if test "x$booth_enable_authfile_unset" = "xyes"; then echo "True"; else echo "False"; fi)])
AC_SUBST([BOOTH_ENABLE_AUTHFILE_SET_CAPABILITY], [$(test "x$booth_enable_authfile_set" != "xyes"; echo "$?")])
AC_SUBST([BOOTH_ENABLE_AUTHFILE_UNSET_CAPABILITY], [$(test "x$booth_enable_authfile_unset" != "xyes"; echo "$?")])

OUTPUT_FORMAT_SYNTAX_DOC="\fB\-\-output\-format\fR text|cmd|json"
OUTPUT_FORMAT_DESC_DOC="There are 3 formats of output available: 'cmd', 'json' and 'text', default is 'text'. Format 'text' is a human friendly output. Format 'cmd' prints pcs commands which can be used to recreate the same configuration. Format 'json' is a machine oriented output of the configuration."
AC_SUBST([OUTPUT_FORMAT_SYNTAX_DOC])
AC_SUBST([OUTPUT_FORMAT_DESC_DOC])

# detect different paths required to generate default settings
AC_PATH_PROG([BASH], [bash])
if test "x$BASH" = "x"; then
	AC_MSG_ERROR([Unable to find bash in $PATH])
fi
AC_PATH_PROG([SYSTEMCTL], [systemctl])
if test "x$SYSTEMCTL" = "x"; then
	AC_PATH_PROG([SERVICE], [service])
	if test "x$SERVICE" = "x"; then
		AC_MSG_ERROR([Unable to find systemctl or service in $PATH])
	fi
fi

if test "x$tests_only" != "xyes"; then
	AC_PATH_PROG([KILLALL], [killall])
	if test "x$KILLALL" = "x"; then
		AC_MSG_ERROR([Unable to find killall in $PATH])
	fi
fi
# yes this is absurd but we need full path for some
# python calls
AC_PATH_PROG([RM], [rm])
if test "x$RM" = "x"; then
	AC_MSG_ERROR([Unable to find rm in $PATH])
fi
AC_PATH_PROG([FIND], [find])
if test "x$FIND" = "x"; then
	AC_MSG_ERROR([Unable to find find in $PATH])
fi
AC_PATH_PROG([CERTUTIL], [certutil])
if test "x$CERTUTIL" = "x"; then
	AC_MSG_ERROR([Unable to find certutil in $PATH])
fi

# NOTE: some of those pacemaker var are only available
# in pacemaker.pc with pacemaker >= 2.0.5
PCS_PKG_CHECK_VAR([PCMK_USER], [pacemaker], [daemon_user], [hacluster])
PCS_PKG_CHECK_VAR([PCMK_GROUP], [pacemaker], [daemon_group], [haclient])
PCS_PKG_CHECK_VAR([PCMK_DAEMON_DIR], [pacemaker], [daemondir], [$PCMKDAEMONDIR])
PCS_PKG_CHECK_VAR([PCMKEXECPREFIX], [pacemaker], [exec_prefix], [/usr])
PCS_PKG_CHECK_VAR([PCMKPREFIX], [pacemaker], [prefix], [/usr])
if test "$PCMKPREFIX" = "/usr"; then
	PCMKCONFDIR="/etc"
	PCMKLOCALSTATEDIR="/var"
else
	PCMKCONFDIR="$PCMKPREFIX/etc"
	PCMKLOCALSTATEDIR="$PCMKPREFIX/var"
fi
AC_SUBST([PCMKCONFDIR])
AC_SUBST([PCMKLOCALSTATEDIR])
PCS_PKG_CHECK_VAR([PCMK_CIB_DIR], [pacemaker], [configdir], [/var/lib/pacemaker/cib])
PCS_PKG_CHECK_VAR([PCMK_SCHEMA_DIR], [pacemaker], [schemadir], [/usr/share/pacemaker])

PCS_PKG_CHECK_VAR([COROEXECPREFIX], [corosync], [exec_prefix], [/usr])
PCS_PKG_CHECK_VAR([COROPREFIX], [corosync], [prefix], [/usr])
if test "$COROPREFIX" = "/usr"; then
	COROCONFDIR="/etc"
else
	COROCONFDIR="$COROPREFIX/etc"
fi
AC_SUBST([COROCONFDIR])
eval COROSYNCLOGDIR="`eval echo ${COROSYNCLOGDIR}`"
PCS_PKG_CHECK_VAR([COROLOGDIR], [corosync], [logdir], [$COROSYNCLOGDIR])
PCS_PKG_CHECK_VAR([COROQDEVEXECPREFIX], [corosync-qdevice], [exec_prefix], [/usr])
PCS_PKG_CHECK_VAR([COROQDEVCONFDIR], [corosync-qdevice], [confdir], [/etc/corosync])

PCS_PKG_CHECK_VAR([SBDCONFDIR], [sbd], [confdir], [$CONFIGDIR])
PCS_PKG_CHECK_VAR([SBDEXECPREFIX], [sbd], [exec_prefix], [/usr])

PCS_PKG_CHECK_VAR([FASEXECPREFIX], [fence-agents], [exec_prefix], [/usr])

PCS_PKG_CHECK_VAR([RA_API_DTD], [resource-agents], [ra_api_dtd], [/usr/share/resource-agents/ra-api-1.dtd])
PCS_PKG_CHECK_VAR([RA_TMP_DIR], [resource-agents], [ra_tmp_dir], [/run/resource-agents])

PCS_PKG_CHECK_VAR([BOOTHCONFDIR], [booth], [confdir], [/etc/booth])
PCS_PKG_CHECK_VAR([BOOTHEXECPREFIX], [booth], [exec_prefix], [/usr])

# required for man page and spec file generation
AX_PROG_DATE
AS_IF([test "$ax_cv_prog_date_gnu_date:$ax_cv_prog_date_gnu_utc" = yes:yes],
	[UTC_DATE_AT="date -u -d@"],
	[AS_IF([test "x$ax_cv_prog_date_bsd_date" = xyes],
		[UTC_DATE_AT="date -u -r"],
		[AC_MSG_ERROR([date utility unable to convert epoch to UTC])])])
AC_SUBST([UTC_DATE_AT])

AC_ARG_VAR([SOURCE_EPOCH],[last modification date of the source])
AC_MSG_NOTICE([trying to determine source epoch])
AC_MSG_CHECKING([for source epoch in \$SOURCE_EPOCH])
AS_IF([test -n "$SOURCE_EPOCH"],
	[AC_MSG_RESULT([yes])],
	[AC_MSG_RESULT([no])
	 AC_MSG_CHECKING([for source epoch in source_epoch file])
	 AS_IF([test -e "$srcdir/source_epoch"],
		[read SOURCE_EPOCH <"$srcdir/source_epoch"
		 AC_MSG_RESULT([yes])],
		[AC_MSG_RESULT([no])
		 AC_MSG_CHECKING([for source epoch baked in by gitattributes export-subst])
		 SOURCE_EPOCH='$Format:%at$' # template for rewriting by git-archive
		 AS_CASE([$SOURCE_EPOCH],
			[?Format:*], # was not rewritten
				[AC_MSG_RESULT([no])
				 AC_MSG_CHECKING([for source epoch in \$SOURCE_DATE_EPOCH])
				 AS_IF([test "x$SOURCE_DATE_EPOCH" != x],
					[SOURCE_EPOCH="$SOURCE_DATE_EPOCH"
					 AC_MSG_RESULT([yes])],
					[AC_MSG_RESULT([no])
					 AC_MSG_CHECKING([whether git log can provide a source epoch])
					 SOURCE_EPOCH=f${SOURCE_EPOCH#\$F} # convert into git log --pretty format
					 SOURCE_EPOCH=$(cd "$srcdir" && git log -1 --pretty=${SOURCE_EPOCH%$} 2>/dev/null)
					 AS_IF([test -n "$SOURCE_EPOCH"],
						[AC_MSG_RESULT([yes])],
						[AC_MSG_RESULT([no, using current time and breaking reproducibility])
						 SOURCE_EPOCH=$(date +%s)])])],
			[AC_MSG_RESULT([yes])]
		 )])
	])
AC_MSG_NOTICE([using source epoch $($UTC_DATE_AT$SOURCE_EPOCH +'%F')])
UTC_DATE=$($UTC_DATE_AT$SOURCE_EPOCH +'%F')
AC_SUBST([UTC_DATE])

AC_CONFIG_FILES([Makefile
		 setup.py
		 setup.cfg
		 data/Makefile
		 pcs/Makefile
		 pcs/settings.py
		 pcs/snmp/pcs_snmp_agent.service
		 pcs/snmp/settings.py
		 pcs/snmp/pcs_snmp_agent.8
		 pcs/pcs.8
		 pcs_test/Makefile
		 pcs_test/settings.py
		 pcsd/capabilities.xml
		 pcsd/Makefile
		 pcsd/pcsd.8
		 pcsd/pcsd-cli.rb
		 pcsd/pcsd-ruby.service
		 pcsd/pcsd.service
		 pcsd/rserver.rb
		 pcsd/settings.rb
		 pcsd/logrotate/pcsd])

AC_CONFIG_FILES([pcs/pcs], [chmod +x pcs/pcs])
AC_CONFIG_FILES([pcs/pcs_internal], [chmod +x pcs/pcs_internal])
AC_CONFIG_FILES([pcs/snmp/pcs_snmp_agent], [chmod +x pcs/snmp/pcs_snmp_agent])
AC_CONFIG_FILES([pcs_test/api_v2_client], [chmod +x pcs_test/api_v2_client])
AC_CONFIG_FILES([pcs_test/smoke.sh], [chmod +x pcs_test/smoke.sh])
AC_CONFIG_FILES([pcs_test/pcs_for_tests], [chmod +x pcs_test/pcs_for_tests])
AC_CONFIG_FILES([pcs_test/suite], [chmod +x pcs_test/suite])
AC_CONFIG_FILES([pcs_test/tools/bin_mock/pcmk/crm_resource], [chmod +x pcs_test/tools/bin_mock/pcmk/crm_resource])
AC_CONFIG_FILES([pcs_test/tools/bin_mock/pcmk/pacemaker-fenced], [chmod +x pcs_test/tools/bin_mock/pcmk/pacemaker-fenced])
AC_CONFIG_FILES([pcsd/pcsd], [chmod +x pcsd/pcsd])
AC_CONFIG_FILES([scripts/pcsd.sh], [chmod +x scripts/pcsd.sh])

AC_OUTPUT
