# Process this file with autoconf to produce a configure script.

AC_PREREQ([2.63])

AC_INIT([pcs],
	m4_esyscmd([make/git-version-gen .tarball-version]),
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
AM_PATH_PYTHON([3.6])
AC_CHECK_PROGS([PYTHON_ENV], [python3 python])
if test "x$PYTHON_ENV" == "x"; then
	AC_MSG_ERROR([Unable to detect python/python3 binary automatically])
fi
eval PYTHON_SITELIB="`eval echo ${pythondir}`"
AC_SUBST([PYTHON_SITELIB])

# check for systemd
PKG_CHECK_MODULES([systemd], [systemd])
PKG_CHECK_VAR([SYSTEMD_UNIT_DIR_TMP], [systemd], [systemdsystemunitdir])
if test "x$SYSTEMD_UNIT_DIR_TMP" == "x"; then
	AC_MSG_ERROR([Unable to detect systemd unit dir automatically])
fi
if test "${prefix}" != "/usr"; then
	SYSTEMD_UNIT_DIR="${prefix}/$SYSTEMD_UNIT_DIR_TMP"
else
	SYSTEMD_UNIT_DIR="$SYSTEMD_UNIT_DIR_TMP"
fi
AC_SUBST([SYSTEMD_UNIT_DIR])
PKG_CHECK_VAR([SYSTEMD_UNIT_PATH], [systemd], [systemdsystemunitpath])
if test "x$SYSTEMD_UNIT_PATH" == "x"; then
	AC_MSG_ERROR([Unable to detect systemd unit path automatically])
fi
SYSTEMD_UNIT_PATH_PYTHON="$(echo \"$SYSTEMD_UNIT_PATH\", | sed -e 's#:#\", \"#g')"
AC_SUBST([SYSTEMD_UNIT_PATH_PYTHON])
SYSTEMD_UNIT_PATH_RUBY="$(echo \'$SYSTEMD_UNIT_PATH\', | sed -e 's#:#\", \"#g' -e "s#\"#\'#g")"
AC_SUBST([SYSTEMD_UNIT_PATH_RUBY])

# check for ruby
AC_PATH_PROG([RUBY], [ruby])
if test x$RUBY == x; then
	AC_MSG_ERROR([Unable to find ruby binary])
fi
PKG_CHECK_MODULES([ruby], [ruby >= 2.5])
PKG_CHECK_VAR([RUBY_VER], [ruby], [ruby_version])
if test "x$RUBY_VER" == "x"; then
	AC_MSG_ERROR([Unable to detect ruby version dir automatically])
fi
AC_CHECK_PROGS([GEM], [gem])
if test x$GEM == x; then
	AC_MSG_ERROR([Unable to find gem binary])
fi
AC_CHECK_PROGS([FCMATCH], [fc-match])
if test x$FCMATCH == x; then
	AC_MSG_ERROR([Unable to find fc-match binary])
fi

AC_ARG_ENABLE([dev-tests],
	      [  --enable-dev-tests           Enable extra developers tests (black, mypy, pylint) (default: no)], [dev_tests="yes"])
AM_CONDITIONAL([DEV_TESTS], [test "x$dev_tests" == "xyes"])

AC_ARG_ENABLE([destructive-tests],
	      [  --enable-destructive-tests           Automatically execute potentially dangerous tests when running make check (default: no)], [destructive_tests="yes"])
AM_CONDITIONAL([EXECUTE_TIER1_TESTS], [test "x$destructive_tests" == "xyes"])

AC_ARG_ENABLE([local-build],
	      [  --enable-local-build           Download and install all dependencies as user / bundles], [local_build="yes"])
AM_CONDITIONAL([LOCAL_BUILD], [test "x$local_build" == "xyes"])

# required to install python requirements
AC_CHECK_PROGS([PIP], [pip3 pip])
if test "x$local_build" == "xyes"; then
	if test x$PIP == x; then
		AC_MSG_ERROR([Unable to find pip binary])
	fi
fi

# used to measure time for some tests, not critical if not available
AC_CHECK_PROGS([TIME], [time])

rm -rf requirements.txt
touch requirements.txt

AC_DEFUN([PCS_CHECK_PYMOD], [
	 if test "x$local_build" == "xyes"; then
		AC_PIP_MODULE([$1], [$2], [$3], [echo "$1 $2" | sed -e 's# ##g' >> requirements.txt])
	 else
		AC_PIP_MODULE([$1], [$2], [$3], [AC_MSG_ERROR([Python module $1 not found])])
	 fi
])

PCS_CHECK_PYMOD([lxml])
PCS_CHECK_PYMOD([pycurl])
PCS_CHECK_PYMOD([pyparsing])
PCS_CHECK_PYMOD([pyOpenSSL])
PCS_CHECK_PYMOD([dacite])
PCS_CHECK_PYMOD([setuptools])
PCS_CHECK_PYMOD([tornado], [>= 6.0.0])
PCS_CHECK_PYMOD([python-dateutil], [>= 2.7.0])

# python 3.6 needs dataclasses as well (added in 3.7)
if test "$PYTHON_VERSION" == "3.6"; then
	PCS_CHECK_PYMOD([dataclasses])
fi

# python 3.8+ needs distro as well (removed from upstream lib)
if printf '%s\n%s\n' "3.8" "$PYTHON_VERSION" | sort -V -C; then
	PCS_CHECK_PYMOD([distro])
fi

if test "x$dev_tests" != "x"; then
	PCS_CHECK_PYMOD([lxml-stubs])
	PCS_CHECK_PYMOD([pylint], [== 2.6.0])
	PCS_CHECK_PYMOD([astroid], [== 2.4.2])
	PCS_CHECK_PYMOD([mypy], [== 0.790])
	PCS_CHECK_PYMOD([black], [== 19.10b0])
fi

# special case, because we need to download from github
AC_PIP_MODULE([pyagentx])

PYTHON_LIST_EMBEDDED=""
if test "x$HAVE_PIPMOD_PYAGENTX" == "xno"; then
	AC_CHECK_PROGS([WGET], [wget])
	if test "x$WGET" == "x"; then
		AC_MSG_ERROR([Unable to find wget binary.])
	fi
	AC_CHECK_PROGS([TAR], [tar])
	if test "x$TAR" == "x"; then
		AC_MSG_ERROR([Unable to find tar binary.])
	fi
	PYTHON_LIST_EMBEDDED="pyagentx $PYTHON_LIST_EMBEDDED"
fi
AM_CONDITIONAL([BUILD_PIPMOD_PYAGENTX], [test "x$HAVE_PIPMOD_PYAGENTX" == "xno"])

if test -n "$PYTHON_LIST_EMBEDDED"; then
	AC_MSG_RESULT([The following python modules will be embedded in the build: $PYTHON_LIST_EMBEDDED])
fi

# ruby gem section

rm -rf Gemfile Gemfile.lock
echo "source 'https://rubygems.org'" > Gemfile
echo "" >> Gemfile

# commodity function
GEM_LIST_EMBEDDED=""

AC_DEFUN([PCS_CHECK_GEM], [
	 if test "x$local_build" == "xyes"; then
		AC_RUBY_GEM([$1], [$2], [$3], [echo "gem '$1'" >> Gemfile && GEM_LIST_EMBEDDED="$1 $GEM_LIST_EMBEDDED"])
	 else
		AC_RUBY_GEM([$1], [$2], [$3], [AC_MSG_ERROR([ruby gem $1 not found])])
	 fi
])

PCS_CHECK_GEM([backports])
PCS_CHECK_GEM([daemons])
PCS_CHECK_GEM([ethon])
PCS_CHECK_GEM([ffi])
PCS_CHECK_GEM([eventmachine])
PCS_CHECK_GEM([json])
PCS_CHECK_GEM([mustermann])
PCS_CHECK_GEM([open4])
PCS_CHECK_GEM([power_assert])
PCS_CHECK_GEM([rack])
PCS_CHECK_GEM([rack-protection])
PCS_CHECK_GEM([rack-test])
PCS_CHECK_GEM([sinatra])
PCS_CHECK_GEM([tilt])
PCS_CHECK_GEM([test-unit])
PCS_CHECK_GEM([thin])

if test -n "$GEM_LIST_EMBEDDED"; then
	AC_CHECK_PROGS([BUNDLE], [bundle])
	if test "x$BUNDLE" == "x"; then
		AC_MSG_ERROR([Unable to find bundle binary required to install missing ruby gems])
	fi
	AC_MSG_RESULT([The following gems will be embedded in the build: $GEM_LIST_EMBEDDED])
fi

AC_ARG_WITH([default-config-dir],
	    [  --with-default-config-dir=DIR  pcs config directory. Default: $sysconfdir/sysconfig ],
	    [ CONF_DIR="$withval" ],
	    [ CONF_DIR="$sysconfdir/sysconfig" ])
AC_SUBST([CONF_DIR])

AC_ARG_WITH([pcs-lib-dir],
	    [  --with-pcs-lib-dir=DIR         pcs lib directory. Default: $LIBDIR ],
	    [ LIB_DIR="$withval" ],
	    [ LIB_DIR="$LIBDIR" ])
AC_SUBST([LIB_DIR])

# we need to do this after defining LIB_DIR
PCS_BUNDLED_DIR_LOCAL="pcs/bundled"
AC_SUBST([PCS_BUNDLED_DIR_LOCAL])
if test "x$local_build" == "xyes"; then
	PCS_BUNDLED_DIR="pcs/bundled"
else
	PCS_BUNDLED_DIR="$LIB_DIR/pcs/bundled"
fi
AC_SUBST([PCS_BUNDLED_DIR])

PCSD_BUNDLED_DIR_ROOT_LOCAL="pcsd/vendor/bundled/"
PCSD_BUNDLED_DIR_LOCAL="$PCSD_BUNDLED_DIR_ROOT_LOCAL/ruby/$RUBY_VER/"

AC_SUBST([PCSD_BUNDLED_DIR_ROOT_LOCAL])
AC_SUBST([PCSD_BUNDLED_DIR_LOCAL])

if test -n "$GEM_LIST_EMBEDDED"; then
	GEM_HOME="$LIB_DIR/$PCSD_BUNDLED_DIR_LOCAL"
	SYSTEMD_GEM_HOME="Environment=GEM_HOME=$GEM_HOME"
	PCS_GEM_HOME="pcsd_gem_path = '$GEM_HOME'"
else
	PCS_GEM_HOME="pcsd_gem_path = None" 
fi
AC_SUBST([GEM_HOME])
AC_SUBST([PCS_GEM_HOME])
AC_SUBST([SYSTEMD_GEM_HOME])
AM_CONDITIONAL([INSTALL_EMBEDDED_GEMS], [test -n "$GEM_HOME"])

AC_ARG_WITH([snmp-mibs-dir],
	    [  --with-snmp-mibs-dir=DIR      snmp MIB directory. Default: $prefix/share/snmp/mibs ],
	    [ SNMP_MIB_DIR="$withval" ],
	    [ SNMP_MIB_DIR="$prefix/share/snmp/mibs" ])
AC_SUBST([SNMP_MIB_DIR])

# detect different paths required to generate default settings
AC_PATH_PROG([BASH], [bash])
if test "x$BASH" == "x"; then
	AC_MSG_ERROR([Unable to find bash in $PATH])
fi
AC_PATH_PROG([SYSTEMCTL], [systemctl])
if test "x$SYSTEMCTL" == "x"; then
	AC_MSG_ERROR([Unable to find systemctl in $PATH])
fi
AC_PATH_PROG([SERVICE], [service])
if test "x$SERVICE" == "x"; then
	AC_MSG_ERROR([Unable to find service in $PATH])
fi
AC_PATH_PROG([OPENSSL], [openssl])
if test "x$OPENSSL" == "x"; then
	AC_MSG_ERROR([Unable to find openssl in $PATH])
fi
AC_PATH_PROG([KILLALL], [killall])
if test "x$KILLALL" == "x"; then
	AC_MSG_ERROR([Unable to find killall in $PATH])
fi
# yes this is absurd but we need full path for some
# python calls
AC_PATH_PROG([RM], [rm])
if test "x$RM" == "x"; then
	AC_MSG_ERROR([Unable to find rm in $PATH])
fi
AC_PATH_PROG([FIND], [find])
if test "x$FIND" == "x"; then
	AC_MSG_ERROR([Unable to find find in $PATH])
fi
PKG_CHECK_VAR([PCMK_USER], [pacemaker], [daemon_user])
if test "x$PCMK_USER" == "x"; then
	AC_MSG_ERROR([Unable to detect pacemaker daemon_user automatically])
fi
PKG_CHECK_VAR([PCMK_GROUP], [pacemaker], [daemon_group])
if test "x$PCMK_GROUP" == "x"; then
	AC_MSG_ERROR([Unable to detect pacemaker daemon_group automatically])
fi
PKG_CHECK_VAR([PCMK_DAEMON_DIR], [pacemaker], [daemondir])
if test "x$PCMK_DAEMON_DIR" == "x"; then
	AC_MSG_ERROR([Unable to detect pacemaker daemondir automatically])
fi
PKG_CHECK_VAR([PCMKEXECPREFIX], [pacemaker], [exec_prefix])
if test "x$PCMKEXECPREFIX" == "x"; then
	AC_MSG_ERROR([Unable to detect pacemaker exec_prefix automatically])
fi
PKG_CHECK_VAR([PCMKPREFIX], [pacemaker], [prefix])
if test "x$PCMKPREFIX" == "x"; then
	AC_MSG_ERROR([Unable to detect pacemaker prefix automatically])
fi
if test "$PCMKPREFIX" == "/usr"; then
	PCMKCONFDIR="/etc"
	PCMKLOCALSTATEDIR="/var"
else
	PCMKCONFDIR="$PCMKPREFIX/etc"
	PCMKLOCALSTATEDIR="$PCMKPREFIX/var"
fi
AC_SUBST([PCMKCONFDIR])
AC_SUBST([PCMKLOCALSTATEDIR])
PKG_CHECK_VAR([PCMK_CIB_DIR], [pacemaker-cib], [configdir])
if test "x$PCMK_CIB_DIR" == "x"; then
	AC_MSG_ERROR([Unable to detect pacemaker-cib configdir automatically])
fi
PKG_CHECK_VAR([PCMK_SCHEMA_DIR], [pacemaker-cib], [schemadir])
if test "x$PCMK_SCHEMA_DIR" == "x"; then
	AC_MSG_ERROR([Unable to detect pacemaker-cib schemadir automatically])
fi
PKG_CHECK_VAR([COROEXECPREFIX], [corosync], [exec_prefix])
if test "x$COROEXECPREFIX" == "x"; then
	AC_MSG_ERROR([Unable to detect corosync exec_prefix automatically])
fi
PKG_CHECK_VAR([COROPREFIX], [corosync], [prefix])
if test "x$COROPREFIX" == "x"; then
	AC_MSG_ERROR([Unable to detect corosync prefix automatically])
fi
if test "$COROPREFIX" == "/usr"; then
	COROCONFDIR="/etc"
else
	COROCONFDIR="$COROPREFIX/etc"
fi
AC_SUBST([COROCONFDIR])
PKG_CHECK_VAR([COROLOGDIR], [corosync], [logdir])
if test "x$COROLOGDIR" == "x"; then
	AC_MSG_ERROR([Unable to detect corosync logdir automatically])
fi
PKG_CHECK_VAR([COROQDEVEXECPREFIX], [corosync-qdevice], [exec_prefix])
if test "x$COROQDEVEXECPREFIX" == "x"; then
	AC_MSG_ERROR([Unable to detect corosync-qdevice exec_prefix automatically])
fi
PKG_CHECK_VAR([COROQDEVCONFDIR], [corosync-qdevice], [confdir])
if test "x$COROQDEVCONFDIR" == "x"; then
	AC_MSG_ERROR([Unable to detect corosync-qdevice confdir automatically])
fi
PKG_CHECK_VAR([SBDCONFDIR], [sbd], [confdir])
if test "x$SBDCONFDIR" == "x"; then
	AC_MSG_ERROR([Unable to detect sbd confdir automatically])
fi
PKG_CHECK_VAR([SBDEXECPREFIX], [sbd], [exec_prefix])
if test "x$SBDEXECPREFIX" == "x"; then
	AC_MSG_ERROR([Unable to detect sbd exec_prefix automatically])
fi
PKG_CHECK_VAR([FASEXECPREFIX], [fence-agents], [exec_prefix])
if test "x$FASEXECPREFIX" == "x"; then
	AC_MSG_ERROR([Unable to detect fence-agents exec_prefix automatically])
fi
PKG_CHECK_VAR([OCFROOT], [resource-agents], [ocfdir])
if test "x$OCFROOT" == "x"; then
	AC_MSG_ERROR([Unable to detect resource-agents ocfdir automatically])
fi
PKG_CHECK_VAR([RA_API_DTD], [resource-agents], [ra_api_dtd])
if test "x$RA_API_DTD" == "x"; then
	AC_MSG_ERROR([Unable to detect resource-agents ra_api_dtd automatically])
fi
PKG_CHECK_VAR([RA_TMP_DIR], [resource-agents], [ra_tmp_dir])
if test "x$RA_TMP_DIR" == "x"; then
	AC_MSG_ERROR([Unable to detect resource-agents ra_tmp_dir automatically])
fi
PKG_CHECK_VAR([BOOTHCONFDIR], [booth], [confdir])
if test "x$BOOTHCONFDIR" == "x"; then
	AC_MSG_ERROR([Unable to detect booth confdir automatically])
fi
PKG_CHECK_VAR([BOOTHEXECPREFIX], [booth], [exec_prefix])
if test "x$BOOTHEXECPREFIX" == "x"; then
	AC_MSG_ERROR([Unable to detect booth exec_prefix automatically])
fi

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
		 CHANGELOG.md
		 pcs/Makefile
		 pcs/settings_default.py
		 pcs/utils.py
		 pcs/cluster.py
		 pcs/lib/external.py
		 pcs/common/system.py
		 pcs/snmp/pcs_snmp_agent.service
		 pcs/snmp/settings.py
		 pcs/snmp/pcs_snmp_agent.8
		 pcs/pcs.8
		 pcs_test/Makefile
		 pcs_test/tools/misc.py
		 pcs_test/tier0/common/reports/test_messages.py
		 pcs_test/tier0/lib/test_resource_agent.py
		 pcs_test/tier0/lib/test_external.py
		 pcs_test/tier0/lib/booth/test_config_files.py
		 pcs_test/tier0/lib/commands/remote_node/fixtures_add.py
		 pcs_test/tier0/lib/commands/test_booth.py
		 pcs_test/tier0/lib/commands/cluster/test_add_nodes.py
		 pcs_test/tier0/lib/commands/cluster/test_remove_nodes.py
		 pcs_test/tier0/lib/corosync/test_live.py
		 pcs_test/tier0/lib/corosync/test_config_parser.py
		 pcs_test/tier0/lib/pacemaker/test_live.py
		 pcs_test/tier0/lib/corosync/test_qdevice_net.py
		 pcs_test/tier0/lib/corosync/test_qdevice_client.py
		 pcs_test/tier1/test_booth.py
		 pcs_test/tier1/cluster/test_setup_local.py
		 pcsd/Makefile
		 pcsd/pcsd.8
		 pcsd/pcs.rb
		 pcsd/pcsd
		 pcsd/pcsd-cli.rb
		 pcsd/pcsd-ruby.service
		 pcsd/pcsd.service
		 pcsd/bootstrap.rb
		 pcsd/settings.rb
		 pcsd/remote.rb
		 pcsd/test/test_corosyncconf.rb
		 pcsd/logrotate/pcsd])

AC_CONFIG_FILES([pcs/pcs], [chmod +x pcs/pcs])
AC_CONFIG_FILES([pcs/pcs_internal], [chmod +x pcs/pcs_internal])
AC_CONFIG_FILES([pcs/snmp/pcs_snmp_agent], [chmod +x pcs/snmp/pcs_snmp_agent])
AC_CONFIG_FILES([pcs_test/smoke.sh], [chmod +x pcs_test/smoke.sh])
AC_CONFIG_FILES([pcs_test/pcs_for_tests], [chmod +x pcs_test/pcs_for_tests])
AC_CONFIG_FILES([pcs_test/suite.py], [chmod +x pcs_test/suite.py])
AC_CONFIG_FILES([pcs_test/tools/bin_mock/pcmk/crm_resource], [chmod +x pcs_test/tools/bin_mock/pcmk/crm_resource])

AC_OUTPUT
