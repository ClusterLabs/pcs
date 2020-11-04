dnl @synopsis AC_PIP_MODULE(modname[, fatal])
dnl
dnl Checks for pip module.
dnl
dnl If fatal is non-empty then absence of a module will trigger an
dnl error.
dnl
dnl @category InstalledPackages
dnl @author Fabio M. Di Nitto <fdinitto@redhat.com>.
dnl @version 2020-11-04
dnl @license AllPermissive

AC_DEFUN([AC_PIP_MODULE],[
	AC_MSG_CHECKING(pip module: $1)
	$PIP list | cut -d " " -f 1 | grep -q ^$1$
	if test $? -eq 0;
	then
		AC_MSG_RESULT(yes)
		eval AS_TR_CPP(HAVE_PIPMOD_$1)=yes
	else
		AC_MSG_RESULT(no)
		eval AS_TR_CPP(HAVE_PIPMOD_$1)=no
		#
		if test -n "$2"
		then
			AC_MSG_ERROR(failed to find required module $1)
			exit 1
		fi
	fi
])
