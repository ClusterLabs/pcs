# Process this file with autoconf to produce a configure script.

AC_PREREQ([2.63])

AC_INIT([pcs],
	m4_esyscmd([make/git-version-gen .tarball-version .gitarchivever]),
	[developers@clusterlabs.org])

AC_CONFIG_AUX_DIR([.])

AM_INIT_AUTOMAKE([dist-bzip2 dist-xz -Wno-portability tar-pax])

AC_CONFIG_MACRO_DIR([m4])
AC_CONFIG_SRCDIR([pyproject.toml.in])

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
AM_PATH_PYTHON([3.12])
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
			[AS_VAR_COPY([$varname], [default])
			eval "actual_value=\${$varname}"
			AC_MSG_RESULT([not found, using default $actual_value])])],
		[eval "actual_value=\${$varname}"
		AC_MSG_RESULT([yes (detected: $actual_value)])])
])

# check for systemd
PKG_CHECK_MODULES([systemd], [systemd], [have_systemd=yes], [have_systemd=no])
if test "$have_systemd" = yes; then
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
fi

# Check for openrc
PKG_CHECK_MODULES([openrc], [openrc], [have_openrc=yes], [have_openrc=no])
if test "$have_openrc" = yes; then
	AC_PATH_PROG([RC_SERVICE], [rc-service])
	if test "x$RC_SERVICE" = "x"; then
		AC_MSG_ERROR([Unable to find rc-service binary])
	fi
	AC_PATH_PROG([RC_UPDATE], [rc-update])
	if test "x$RC_UPDATE" = "x"; then
		AC_MSG_ERROR([Unable to find rc-update binary])
	fi
fi

# If no init systems were found, raise an error
if test "$have_systemd" = no && test "$have_openrc" = no; then
	AC_MSG_ERROR([Unable to detect an init system])
fi

# check for ruby
AC_PATH_PROG([RUBY], [ruby])
if test x$RUBY = x; then
	AC_MSG_ERROR([Unable to find ruby binary])
fi

# opensuse has a versioned ruby-$version.pc file
# that does not match fedora or rhel ruby.pc
# so we need to detect it
rubymod=`pkg-config --list-all | awk '{print $1}' | grep ^ruby | sort -n | tail -n 1`

PKG_CHECK_MODULES([ruby], [$rubymod >= 3.1])
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
	      [AS_HELP_STRING([--enable-dev-tests], [Enable extra developers tests (mypy, ruff) (default: no)])],
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

AC_ARG_ENABLE([webui],
	      [AS_HELP_STRING([--enable-webui], [Include pcsd web UI backend module in pcs package])],
	      [webui="yes"])

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

AC_ARG_WITH([python-version],
	[AS_HELP_STRING([--with-python-version=X.Y], [Set an alternative Python interpreter version for generated rpm.])],
	[PYVERSION="$withval"],
	[PYVERSION=""])
AC_SUBST([PYVERSION])

AC_ARG_ENABLE([ci-rpm-workarounds],
	      [AS_HELP_STRING([--enable-ci-rpm-workarounds], [NOT TO BE USED UNLESS YOUR NAME IS JENKINS])],
	      [CIRPMWORKAROUNDS="yes"], [CIRPMWORKAROUNDS=""])
AC_SUBST([CIRPMWORKAROUNDS])

if test "x$cache_only" != "xyes"; then
	AC_CHECK_PROGS([WGET], [wget])
	if test "x$WGET" = "x"; then
		AC_MSG_ERROR([Unable to find wget binary.])
	fi
fi

if test "x$dev_tests" = "xyes"; then
	# diff and sort is used in 'make typos_check' and 'make typos_known'
	AC_PATH_PROG([DIFF], [diff])
	if test "x$DIFF" = "x"; then
		AC_MSG_ERROR([Unable to find diff in $PATH])
	fi
	AC_PATH_PROG([SORT], [sort])
	if test "x$SORT" = "x"; then
		AC_MSG_ERROR([Unable to find sort in $PATH])
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
		opencloudos|alpine)
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

AC_ARG_WITH([custom-gemfile],
	  [AS_HELP_STRING([--with-custom-gemfile=PATH], [Use custom gemfile instead of autogenerated. Effective only with the local-build option. Default: empty])],
	  [PCS_CUSTOM_GEMFILE="$withval"])

# python detection section
PCS_BUNDLED_DIR_LOCAL="pcs_bundled"
AC_SUBST([PCS_BUNDLED_DIR_LOCAL])
PCS_BUNDLED_DIR="$LIB_DIR/pcs/$PCS_BUNDLED_DIR_LOCAL"
AC_SUBST([PCS_BUNDLED_DIR])

mkdir -p $ac_pwd/stamps
mkdir -p $ac_pwd/rpm/
rm -rf $ac_pwd/rpm/requirements.txt
touch $ac_pwd/rpm/requirements.txt
if test "x$CIRPMWORKAROUNDS" = "xyes"; then
	echo "pyparsing>=3.0.0" >> $ac_pwd/rpm/requirements.txt
fi

# PCS_BUNDLE_PYMOD([module], [version])
AC_DEFUN([PCS_BUNDLE_PYMOD], [
	echo "$1 $2" | sed -e 's# ##g' >> $ac_pwd/rpm/requirements.txt
])

# PCS_CHECK_PYMOD([module], [version], [embedded=yes])
AC_DEFUN([PCS_CHECK_PYMOD], [
	AC_PIP_MODULE([$1], [$2], [bundle_module=no], [bundle_module=yes], [bundle_module=yes])
	if { test "x$local_build" != "xyes" || test "x$3" != "xyes"; } && test "x$bundle_module" = "xyes"; then
		AC_MSG_ERROR([Python module $1 not found])
	fi
	if test "x$bundle_module" = "xyes" && test "x$cache_only" = "xyes"; then
		# Workaround for hyphen/underscore inconsistency between module and archive names
		# NOTE: double '[[]]' brackets needs to be used because '[]' are special characters in m4 macros
		pattern=`printf '%s\n' "$1" | sed -e 's/[[-_]]/[[-_]]/'`
		src=`ls rpm/$pattern-*`
		if test "x$src" = "x"; then
			AC_MSG_ERROR([cache only build required but no source detected in rpm/])
		fi
	fi
	if test "x$3" = "xyes" && { test "x$bundle_module" = "xyes" || test "x$individual_bundling" != "xyes"; }; then
		PCS_BUNDLE_PYMOD([$1], [$2])
	fi
])

# PCS_BUNDLE_GEM([module], [version])
AC_DEFUN([PCS_BUNDLE_GEM], [
	if test "x$PCS_CUSTOM_GEMFILE" = "x"; then
		if test "x$2" = "x"; then
			echo "gem '$1'" >> Gemfile
		else
			echo "gem '$1', '$2'" >> Gemfile
		fi
	else
		grep "$1" Gemfile || AC_MSG_ERROR([custom gemfile missing required gem '$1'])
	fi
])

# PCS_CHECK_GEM([module], [version], [default=yes], [record_mode])
# Set the third argument to "yes" for Ruby default gems (gems shipped with Ruby
# itself). Default gems are recorded into a separate rpm requirements list and
# are only added to the Gemfile in a full local build; see below. The fourth
# argument controls how the gem is recorded as an rpm rubygem() dependency:
#   (empty)   - record for both BuildRequires and Requires
#   buildonly - record for BuildRequires only (build-time deps, e.g. test-unit)
#   norecord  - do not record (e.g. kept hardcoded in the spec)
AC_DEFUN([PCS_CHECK_GEM], [
	AC_RUBY_GEM([$1], [$2], [bundle_module=no], [bundle_module=yes])
	if test "x$local_build" != "xyes" && test "x$bundle_module" = "xyes"; then
		AC_MSG_ERROR([ruby gem $1 not found])
	fi
	if test "x$bundle_module" = "xyes" && test "x$cache_only" = "xyes"; then
		src=`ls $PCSD_BUNDLED_CACHE_DIR/$1-*`
		if test "x$src" = "x"; then
			AC_MSG_ERROR([cache only build required but no source detected in $PCSD_BUNDLED_CACHE_DIR])
		fi
	fi
	# Record the gem as an rpm Build/Requires dependency when it is used from the
	# system instead of being bundled. That happens when:
	#   * local build is disabled - all gems come from the system, or
	#   * individual bundling is enabled - a gem found in the system is reused
	#     instead of being bundled.
	# In a full local build (without individual bundling) every gem is bundled,
	# so no rpm rubygem() dependency is generated.
	# Non-default and default gems are recorded into separate lists (consumed
	# together by Makefile.am as BuildRequires). Default gems ship with Ruby and
	# are always present on the system, so their recording does not depend on
	# bundle_module. Gems needed at runtime are additionally recorded into
	# gem_requires.txt (Requires). The record mode (fourth argument, see above)
	# applies to default and non-default gems alike, so e.g. a default gem whose
	# rubygem() Provides is missing on some distro can be set to norecord.
	gem_record_file=""
	if test "x$local_build" != "xyes" || test "x$individual_bundling" = "xyes"; then
		if test "x$3" = "xyes"; then
			gem_record_file=gem_requirements_default.txt
		elif test "x$bundle_module" != "xyes"; then
			gem_record_file=gem_requirements.txt
		fi
	fi
	if test "x$4" != "xnorecord" && test "x$gem_record_file" != "x"; then
		echo "$1" >> $ac_pwd/rpm/$gem_record_file
		if test "x$4" != "xbuildonly"; then
			echo "$1" >> $ac_pwd/rpm/gem_requires.txt
		fi
	fi
	# Add the gem to the Gemfile so it gets bundled or pinned. Default gems ship
	# with Ruby, so they only need to be bundled in a full local build; in every
	# other mode they are used from the system and must stay out of the Gemfile.
	if test "x$3" != "xyes" || { test "x$local_build" = "xyes" && test "x$individual_bundling" != "xyes"; }; then
		gem_version=""
		if test "x$bundle_module" != "xyes" && test "x$individual_bundling" = "xyes"; then
			# Individual bundling is on and the gem is installed in the system:
			# use its installed version so it is reused instead of bundled.
			module_caps=AS_TR_CPP([$1])
			AS_VAR_COPY([gem_version], [HAVE_RUBYGEM_${module_caps}_VERSION])
		fi
		gem_version="${gem_version:-$2}"
		# Pin the gem in the Gemfile to:
		#   * the installed system version -> reuse the system gem (no bundling);
		#   * the given version requirement (or none) -> bundle the newest match.
		PCS_BUNDLE_GEM([$1], [$gem_version])
	fi
])

# required by rpm build
PYAGENTX_VERSION=0.4.pcs.2
AC_SUBST([PYAGENTX_VERSION])

# those MUST be available in BaseOS

# pip 19.0 required for PEP517 support
PCS_CHECK_PYMOD([pip], [>= 23.0])

if test "x$tests_only" != "xyes"; then
	# setuptools 61.0.0 required for PEP621 support
	PCS_CHECK_PYMOD([setuptools], [>= 66.1])
	# wheel is required if setuptools < 71
	AC_PIP_MODULE([setuptools], [>= 71], [], [], [need_wheel=yes])
	# pycurl-7.46.0 requires setuptools >= 77
	AC_PIP_MODULE([setuptools], [>= 77], [setuptools_77=yes], [setuptools_77=no], [setuptools_77=no])
	if test "x$need_wheel" = "xyes"; then
		PCS_CHECK_PYMOD([wheel])
	fi
	PCS_CHECK_PYMOD([cryptography])
	PCS_CHECK_PYMOD([lxml])
	PCS_CHECK_PYMOD([pyparsing], [>= 3.0.0])

	# those are kind of problematic.
	# use them all from the BaseOS or embedded them all as necessary (--enable-local-build)
	PCS_CHECK_PYMOD([dacite], [], [yes])
	PCS_CHECK_PYMOD([tornado], [>= 6.0.0], [yes])
	PCS_CHECK_PYMOD([python-dateutil], [< 4.0.0], [yes])
	# setuptoools_scm is needed for bundling dateutil, this uses variables
	# set by the PCS_CHECK_PYMOD macro, so it must be executed right after it
	if test "x$bundle_module" = "xyes"; then
		PCS_CHECK_PYMOD([setuptools-scm])
		PCS_CHECK_PYMOD([six])
		PKG_CHECK_MODULES([TZDATA], [tzdata])
	fi
	# Pycurl-7.46.0 requires setuptools => 77. However, if pycurl is already
	# installed on the system, use whatever pycurl is installed and don't limit
	# its version based on setuptools version.
	if test "x$setuptools_77" != "xyes" && test "x$local_build" = "xyes"; then
		PCS_CHECK_PYMOD([pycurl], [< 7.46.0], [yes])
	else
		PCS_CHECK_PYMOD([pycurl], [], [yes])
	fi
	# Building pycurl requires devel packages that contain pkg-config, so devel
	# packages must be installed for these checks to pass.
	# This uses variables set by the PCS_CHECK_PYMOD macro, so it must be executed
	# right after it.
	if test "x$bundle_module" = "xyes" || test "x$individual_bundling" != "xyes"; then
		PKG_CHECK_MODULES([LIBCURL], [libcurl])
		PKG_CHECK_MODULES([OPENSSL], [openssl])
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

# Lists of ruby gems which pcs depends on, consumed by Makefile.am to generate
# rpm rubygem() BuildRequires/Requires dependencies in the spec. A gem is listed
# only when it is used from the system rather than bundled, i.e. in every mode
# except a full local build (where gems are bundled). Both lists are populated by
# PCS_CHECK_GEM (default gems are flagged with its third argument):
#   * gem_requirements_default.txt - Ruby default gems (shipped with Ruby).
#   * gem_requirements.txt - non-default gems.
# Together they form the BuildRequires list. The runtime subset (build-only gems
# excluded, see the PCS_CHECK_GEM record_mode argument) is in:
#   * gem_requires.txt - Requires.
# Truncate them here so a reconfigure starts from a clean slate; modes that record
# nothing leave an empty file.
rm -f $ac_pwd/rpm/gem_requirements.txt $ac_pwd/rpm/gem_requirements_default.txt $ac_pwd/rpm/gem_requires.txt
touch $ac_pwd/rpm/gem_requirements.txt $ac_pwd/rpm/gem_requirements_default.txt $ac_pwd/rpm/gem_requires.txt

if test "x$local_build" = "xyes"; then
	if test "x$PCS_CUSTOM_GEMFILE" != "x"; then
		if ! test -e "$PCS_CUSTOM_GEMFILE"; then
			AC_MSG_ERROR([custom gemfile '$PCS_CUSTOM_GEMFILE' does not exist])
		fi
		cp "$PCS_CUSTOM_GEMFILE" Gemfile
	else
		echo "source 'https://rubygems.org'" > Gemfile
		echo "" >> Gemfile
	fi
fi

RACK_HANDLER="Rackup"
REQUIRE_RACKUP="require 'rackup'"

if test "x$tests_only" != "xyes"; then
	# Direct PCSD dependencies
	# ########################
	# Default Gems
	# The third PCS_CHECK_GEM argument flags these as Ruby default gems: they are
	# recorded into the default-gems list and are only added to the Gemfile (for
	# bundling) in a full local build. Checked in all modes so the macro records
	# them regardless of individual bundling.
	PCS_CHECK_GEM([date], [], [yes])
	PCS_CHECK_GEM([etc], [], [yes])
	PCS_CHECK_GEM([fileutils], [], [yes])
	PCS_CHECK_GEM([net-http], [], [yes])
	PCS_CHECK_GEM([openssl], [], [yes])
	PCS_CHECK_GEM([shellwords], [], [yes])
	PCS_CHECK_GEM([stringio], [], [yes])
	PCS_CHECK_GEM([tempfile], [], [yes])
	PCS_CHECK_GEM([timeout], [], [yes])
	PCS_CHECK_GEM([uri], [], [yes])
	# json is a default gem upstream, but RHEL/Fedora ship it as a bundled gem,
	# so it must be checked and pinned explicitly, also in individual bundling.
	PCS_CHECK_GEM([json])
	# Default/Bundled Gems
	# base64 >= 0.1.0 is also required as a dependency of rack-protection >= 3.2.0.
	# The version requirement must be specified here rather than in a separate
	# check, because listing the same gem twice in the Gemfile with different
	# version specs causes bundler to fail.
	PCS_CHECK_GEM([base64], [>= 0.1.0])
	PCS_CHECK_GEM([logger])
	PCS_CHECK_GEM([rexml])
	# Bundled Gems
	PCS_CHECK_GEM([test-unit])
	# Standalone Gems
	PCS_CHECK_GEM([backports])
	# We require childprocess 5.0.0+ due to the libcurl's threaded DNS resolver,
	# new Ruby and Puma. Old childprocess uses a wrong forking method causing
	# SIGABRT or deadlocks, see: https://bugzilla.redhat.com/show_bug.cgi?id=2536998
	if test "x$DISTRO" = "xdebian" || test "x$DISTRO" = "xubuntu"; then
		# Debian and Ubuntu both have old libcurl and Ruby, so there should be
		# no issue for now with using old childprocess
		PCS_CHECK_GEM([childprocess])
	else
		PCS_CHECK_GEM([childprocess], [>= 5.0.0])
	fi
	PCS_CHECK_GEM([curb])
	PCS_CHECK_GEM([puma])
	PCS_CHECK_GEM([rack])
	# rack < 3.0 provides its own handler and does not need the rackup gem
	AC_RUBY_GEM([rack], [< 3.0.0], [need_rackup=no], [need_rackup=yes], [need_rackup=yes])
	if test "x$need_rackup" = "xyes"; then
		PCS_CHECK_GEM([rackup])
	else
		RACK_HANDLER=Rack
		REQUIRE_RACKUP=""
	fi
	PCS_CHECK_GEM([sinatra])
	if test "x$individual_bundling" = "xyes"; then
		# Indirect PCSD dependencies
		# ########################
		# NOTE: These are transitive dependencies of the direct gems above. We
		#       must list them so PCS_CHECK_GEM pins them to their system
		#       versions; an unlisted one stays unpinned and bundler would
		#       download and bundle a newer version instead of reusing the
		#       system gem. A new transitive dependency must therefore be added
		#       here as well.
		# test-unit dependencies
		PCS_CHECK_GEM([power_assert])
		# rest of sinatra dependencies
		PCS_CHECK_GEM([mustermann], [< 4.0.0])
		# musterman < 3.1.0 requires ruby2_keywords ~> 0.0.1
		AC_RUBY_GEM([mustermann], [< 3.1.0], [need_ruby2_keywords=yes], [need_ruby2_keywords=no], [need_ruby2_keywords=no])
		if test "x$need_ruby2_keywords" = "xyes"; then
			PCS_CHECK_GEM([ruby2_keywords], [>= 0.0.1])
		fi
		PCS_CHECK_GEM([rack-protection])
		# sinatra >= 4.0.0 introduced a new dependency on rack-session >= 2.0.0
		AC_RUBY_GEM([sinatra], [< 4.0.0], [need_rack_session=no], [need_rack_session=yes], [need_rack_session=yes])
		if test "x$need_rack_session" = "xyes"; then
			PCS_CHECK_GEM([rack-session], [>= 2.0.0])
		fi
		PCS_CHECK_GEM([tilt])
		# puma dependencies
		PCS_CHECK_GEM([nio4r])
	fi
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
AM_CONDITIONAL([INDIVIDUAL_BUNDLING], [test "x$individual_bundling" = "xyes"])


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
AC_SUBST([PACKAGE_WEBUI_BACKEND], [$(if test "x$webui" != "xyes"; then echo "pcs.daemon.app.webui*"; fi)])
PCSD_PUBLIC_DIR="$LIB_DIR/pcsd/public"
AC_SUBST([PCSD_PUBLIC_DIR])
PCSD_WEBUI_DIR="$PCSD_PUBLIC_DIR/ui"
AC_SUBST([PCSD_WEBUI_DIR])
PCSD_UNIX_SOCKET="$LOCALSTATEDIR/run/pcsd.socket"
AC_SUBST([PCSD_UNIX_SOCKET])

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
		 pcs.pc
		 pyproject.toml
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
AC_CONFIG_FILES([pcs_test/tools/bin_mock/pcmk/stonith_admin], [chmod +x pcs_test/tools/bin_mock/pcmk/stonith_admin])
AC_CONFIG_FILES([pcsd/pcsd], [chmod +x pcsd/pcsd])
AC_CONFIG_FILES([scripts/pcsd.sh], [chmod +x scripts/pcsd.sh])

AC_OUTPUT
