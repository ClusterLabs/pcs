dnl @synopsis AC_RUBY_GEM(gem[, fatal])
dnl
dnl Checks for Ruby gem.
dnl
dnl If fatal is non-empty then absence of a module will trigger an
dnl error.
dnl
dnl @category InstalledPackages
dnl @author Fabio M. Di Nitto <fdinitto@redhat.com>.
dnl @version 2020-11-03
dnl @license AllPermissive

AC_DEFUN([AC_RUBY_GEM],[
	AC_MSG_CHECKING(ruby gem: $1)
	$GEM list | grep -q "^$1 " 2>/dev/null
	if test $? -eq 0;
	then
		AC_MSG_RESULT(yes)
		eval AS_TR_CPP(HAVE_RUBYGEM_$1)=yes
	else
		AC_MSG_RESULT(no)
		eval AS_TR_CPP(HAVE_RUBYGEM_$1)=no
		#
		if test -n "$2"
		then
			AC_MSG_ERROR(failed to find required ruby gem $1)
			exit 1
		fi
	fi
])
