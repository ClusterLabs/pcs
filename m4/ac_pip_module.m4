dnl @synopsis AC_PIP_MODULE(modname[, version][, action-if-found][, action-if-not-found][, action-if-version-mismatch][, pythonpath])
dnl
dnl Checks for pip module.
dnl
dnl If fatal is non-empty then absence of a module will trigger an
dnl error.
dnl
dnl @category InstalledPackages
dnl @author Fabio M. Di Nitto <fdinitto@redhat.com>.
dnl @version 2020-11-19
dnl @license AllPermissive

AC_DEFUN([AC_PIP_MODULE],[
	module="$1"
	reqversion="$2"
	AC_MSG_CHECKING([pip module: $module $reqversion])
	pipcommonopts="list --format freeze --disable-pip-version-check"
	if test -n "$6"; then
		pipoutput=$(PYTHONPATH=$6 $PIP $pipcommonopts | grep ^${module}==)
	else
		pipoutput=$($PIP $pipcommonopts | grep ^${module}==)
	fi
	if test "x$pipoutput" != "x"; then
		curversion=$(echo $pipoutput | sed -e 's#.*==##g')
		checkver=ok
		if test "x$reqversion" != x; then
			comp=$(echo $reqversion | cut -d " " -f 1)
			tmpversion=$(echo $reqversion | cut -d " " -f 2)
			AC_COMPARE_VERSIONS([$curversion], [$comp], [$tmpversion], [checkver=ok], [checkver=nok])
		fi
		if test "x$checkver" = "xok"; then
			AC_MSG_RESULT([yes (detected: $curversion)])
			eval AS_TR_CPP(HAVE_PIPMOD_$module)=yes
			eval AS_TR_CPP(HAVE_PIPMOD_$module_version)=$curversion
			$3
		else
			if test -n "$5"; then
				AC_MSG_RESULT([no (detected: $curversion)])
				eval AS_TR_CPP(HAVE_PIPMOD_$module)=no
				eval AS_TR_CPP(HAVE_PIPMOD_$module_version)=$curversion
				$5
			else
				AC_MSG_ERROR([python $module version $curversion detected. Requested "$comp $tmpversion"])
			fi
		fi
	else
		AC_MSG_RESULT([no])
		eval AS_TR_CPP(HAVE_PIPMOD_$module)=no
		eval AS_TR_CPP(HAVE_PIPMOD_$module_version)=""
		$4
	fi
])
