dnl @synopsis AC_RUBY_GEM(gem[, version][, action-if-found] [, action-if-not-found])
dnl
dnl Checks for Ruby gem.
dnl
dnl @category InstalledPackages
dnl @author Fabio M. Di Nitto <fdinitto@redhat.com>.
dnl @version 2020-11-23
dnl @license AllPermissive

AC_DEFUN([AC_RUBY_GEM],[
	module="$1"
	reqversion="$2"
	AC_MSG_CHECKING([ruby gem: $module])
	gemoutput=$($GEM list --local | grep "^$module " 2>/dev/null)
	if test "x$gemoutput" != "x"; then
		curversion=$(echo $gemoutput | sed -e 's#.*(##g' -e 's#)##'g -e 's#default: ##g')
		if test "x$reqversion" != x; then
			comp=$(echo $reqversion | cut -d " " -f 1)
			tmpversion=$(echo $reqversion | cut -d " " -f 2)
			AC_COMPARE_VERSIONS([$curversion], [$comp], [$tmpversion],, [AC_MSG_ERROR([ruby gem $module version $curversion detected. Requested "$comp $tmpversion"])])
		fi
		AC_MSG_RESULT([yes (detected: $curversion)])
		eval AS_TR_CPP(HAVE_RUBYGEM_$module)=yes
		eval AS_TR_CPP(HAVE_RUBYGEM_$module_version)=$curversion
		$3
	else
		AC_MSG_RESULT([no])
		eval AS_TR_CPP(HAVE_RUBYGEM_$module)=no
		eval AS_TR_CPP(HAVE_RUBYGEM_$module_version)=""
		$4
	fi
])
