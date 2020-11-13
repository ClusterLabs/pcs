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
PKG_CHECK_VAR([SYSTEMD_UNIT_DIR], [systemd], [systemdsystemunitdir])
if test "x$SYSTEMD_UNIT_DIR" == "x"; then
	AC_MSG_ERROR([Unable to detect systemd unit dir automatically])
fi
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

AC_ARG_ENABLE([destructive-tests],
	      [  --enable-destructive-tests           Automatically execute potentially dangerous tests when running make check (default: no)], [destructive_tests="yes"])
AM_CONDITIONAL([EXECUTE_TIER1_TESTS], [test "x$destructive_tests" == "xyes"])

AC_ARG_ENABLE([local-build],
	      [  --enable-local-build           Download and install all dependencies as user / bundles], [local_build="yes"])
AM_CONDITIONAL([LOCAL_BUILD], [test "x$local_build" == "xyes"])

# required to install python requirements
AC_CHECK_PROGS([PIP], [pip pip3])
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

PYTHON_LIST="astroid pylint tornado dacite dateutil"

# commodity function
PYTHON_LIST_PIP=""

AC_DEFUN([PCS_CHECK_PYMOD],[
	  AC_PYTHON_MODULE([$1], [$2])
	  res=$(eval echo "$AS_TR_CPP([HAVE_PYMOD_$1])")
	  if test "x$res" == "xno"; then
		  PYTHON_LIST_PIP="$1 $PYTHON_LIST_PIP"
	  fi
	  ])

for i in $PYTHON_LIST; do
	PCS_CHECK_PYMOD([$i], [$MOD_FAILURE])
done

# special case lxml-stubs, it can be installed via pip
# but it cannot be detected as python module
AC_PIP_MODULE([lxml-stubs], [$MOD_FAILURE])
if test "$HAVE_PIPMOD_LXML_STUBS" == "no"; then
	PYTHON_LIST_PIP="lxml-stubs $PYTHON_LIST_PIP"
fi

# generate requirements.txt here or in Makefile?
rm -rf requirements.txt
touch requirements.txt
for i in $PYTHON_LIST_PIP; do
	echo $i >> requirements.txt
done

if test -n "$PYTHON_LIST_PIP"; then
	AC_MSG_RESULT([The following python modules will be pip installed: $PYTHON_LIST_PIP])
fi

# special case, because we need to download from github
AC_PYTHON_MODULE([pyagentx], [$MOD_FAILURE])

PYTHON_LIST_EMBEDDED=""
if test "x$HAVE_PYMOD_PYAGENTX" == "xno"; then
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
AM_CONDITIONAL([BUILD_PYMOD_PYAGENTX], [test "x$HAVE_PYMOD_PYAGENTX" == "xno"])

if test -n "$PYTHON_LIST_EMBEDDED"; then
	AC_MSG_RESULT([The following python modules will be embedded in the build: $PYTHON_LIST_EMBEDDED])
fi

# ruby gem section

# keep the list of gems requirements

GEM_LIST="backports daemons ethon ffi eventmachine json mustermann open4 power_assert rack rack-protection rack-test sinatra tilt test-unit thin"

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
	AC_CHECK_PROGS([BUNDLE], [bundle])
	if test "x$BUNDLE" == "x"; then
		AC_MSG_ERROR([Unable to find bundle binary required to install missing ruby gems])
	fi
	AC_MSG_RESULT([The following gems will be embedded in the build: $GEM_LIST_EMBEDDED])
fi

# generate pcsd/Gemfile here or in Makefile?
rm -rf Gemfile Gemfile.lock
echo "source 'https://rubygems.org'" > Gemfile
echo "" >> Gemfile
for i in $GEM_LIST_EMBEDDED; do
	echo "gem '$i'" >> Gemfile
done

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
AC_PATH_PROG([CRM_MON], [crm_mon])
if test "x$CRM_MON" == "x"; then
	AC_MSG_ERROR([Unable to find crm_mon in $PATH])
fi
AC_PATH_PROG([CRM_REPORT], [crm_report])
if test "x$CRM_REPORT" == "x"; then
	AC_MSG_ERROR([Unable to find crm_report in $PATH])
fi
AC_PATH_PROG([CRM_RESOURCE], [crm_resource])
if test "x$CRM_RESOURCE" == "x"; then
	AC_MSG_ERROR([Unable to find crm_resource in $PATH])
fi
AC_PATH_PROG([CRM_RULE], [crm_rule])
if test "x$CRM_RULE" == "x"; then
	AC_MSG_ERROR([Unable to find crm_rule in $PATH])
fi
AC_PATH_PROG([CRM_NODE], [crm_node])
if test "x$CRM_NODE" == "x"; then
	AC_MSG_ERROR([Unable to find crm_node in $PATH])
fi
AC_PATH_PROG([CRM_VERIFY], [crm_verify])
if test "x$CRM_VERIFY" == "x"; then
	AC_MSG_ERROR([Unable to find crm_verify in $PATH])
fi
AC_PATH_PROG([CRM_DIFF], [crm_diff])
if test "x$CRM_DIFF" == "x"; then
	AC_MSG_ERROR([Unable to find crm_diff in $PATH])
fi
AC_PATH_PROG([CIBADMIN], [cibadmin])
if test "x$CIBADMIN" == "x"; then
	AC_MSG_ERROR([Unable to find cibadmin in $PATH])
fi
AC_PATH_PROG([PACEMAKERD], [pacemakerd])
if test "x$PACEMAKERD" == "x"; then
	AC_MSG_ERROR([Unable to find pacemakerd in $PATH])
fi
PKG_CHECK_MODULES([PCMK], [pacemaker])
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
# we will take this one from resource-agents once it´s available
PKG_CHECK_MODULES([PCMK_SERVICE], [pacemaker-service])
PKG_CHECK_VAR([OCFROOT], [pacemaker-service], [ocfdir])
if test "x$OCFROOT" == "x"; then
	AC_MSG_ERROR([Unable to detect pacemaker-service ocfdir automatically])
fi
PKG_CHECK_MODULES([PCMK_CIB], [pacemaker-cib])
PKG_CHECK_VAR([PCMK_CIB_DIR], [pacemaker-cib], [configdir])
if test "x$PCMK_CIB_DIR" == "x"; then
	AC_MSG_ERROR([Unable to detect pacemaker-cib configdir automatically])
fi
PKG_CHECK_VAR([PCMK_SCHEMA_DIR], [pacemaker-cib], [schemadir])
if test "x$PCMK_SCHEMA_DIR" == "x"; then
	AC_MSG_ERROR([Unable to detect pacemaker-cib schemadir automatically])
fi
PKG_CHECK_MODULES([COROSYNC], [corosync])
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
PKG_CHECK_MODULES([COROSYNCQDEV], [corosync-qdevice])
PKG_CHECK_VAR([COROQDEVEXECPREFIX], [corosync-qdevice], [exec_prefix])
if test "x$COROQDEVEXECPREFIX" == "x"; then
	AC_MSG_ERROR([Unable to detect corosync-qdevice exec_prefix automatically])
fi
PKG_CHECK_VAR([COROQDEVCONFDIR], [corosync-qdevice], [confdir])
if test "x$COROQDEVCONFDIR" == "x"; then
	AC_MSG_ERROR([Unable to detect corosync-qdevice confdir automatically])
fi
PKG_CHECK_MODULES([SBD], [sbd])
PKG_CHECK_VAR([SBDCONFDIR], [sbd], [confdir])
if test "x$SBDCONFDIR" == "x"; then
	AC_MSG_ERROR([Unable to detect sbd confdir automatically])
fi

PKG_CHECK_VAR([SBDEXECPREFIX], [sbd], [exec_prefix])
if test "x$SBDEXECPREFIX" == "x"; then
	AC_MSG_ERROR([Unable to detect sbd exec_prefix automatically])
fi

AC_CONFIG_FILES([Makefile
		 newversion.py
		 setup.py
		 setup.cfg
		 pcs/Makefile
		 pcs/settings_default.py
		 pcs/utils.py
		 pcs/cluster.py
		 pcs/lib/external.py
		 pcs/common/system.py
		 pcs/snmp/pcs_snmp_agent.service
		 pcs/snmp/settings.py
		 pcs_test/Makefile
		 pcs_test/tier0/lib/test_resource_agent.py
		 pcs_test/tier0/lib/test_external.py
		 pcs_test/tier0/lib/corosync/test_live.py
		 pcs_test/tier0/lib/pacemaker/test_live.py
		 pcs_test/tier0/lib/corosync/test_qdevice_net.py
		 pcs_test/tier0/lib/corosync/test_qdevice_client.py
		 pcs_test/tier1/test_booth.py
		 pcsd/Makefile
		 pcsd/pcs.rb
		 pcsd/pcsd
		 pcsd/pcsd-cli.rb
		 pcsd/pcsd-ruby.service
		 pcsd/pcsd.service
		 pcsd/bootstrap.rb
		 pcsd/settings.rb
		 pcsd/remote.rb
		 pcsd/logrotate/pcsd])

AC_CONFIG_FILES([pcs/pcs], [chmod +x pcs/pcs])
AC_CONFIG_FILES([pcs/pcs_internal], [chmod +x pcs/pcs_internal])
AC_CONFIG_FILES([pcs/snmp/pcs_snmp_agent], [chmod +x pcs/snmp/pcs_snmp_agent])
AC_CONFIG_FILES([pcs_test/smoke.sh], [chmod +x pcs_test/smoke.sh])
AC_CONFIG_FILES([pcs_test/pcs_for_tests], [chmod +x pcs_test/pcs_for_tests])
AC_CONFIG_FILES([pcs_test/suite.py], [chmod +x pcs_test/suite.py])
AC_CONFIG_FILES([pcs_test/tools/bin_mock/pcmk/crm_resource], [chmod +x pcs_test/tools/bin_mock/pcmk/crm_resource])

AC_OUTPUT
