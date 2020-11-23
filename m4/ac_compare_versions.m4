dnl @synopsis AC_COMPARE_VERSIONS([verA], [op], [verB] [, action-if-true] [, action-if-false])
dnl
dnl Compare two versions based on "op"
dnl
dnl op can be:
dnl
dnl lt or <
dnl le or <=
dnl eq or ==
dnl ge or >=
dnl gt or >
dnl
dnl @category InstalledPackages
dnl @author Fabio M. Di Nitto <fdinitto@redhat.com>.
dnl @version 2020-11-19
dnl @license AllPermissive

AC_DEFUN([AC_COMPARE_VERSIONS],[
	result=false
	verA="$1"
	op="$2"
	verB="$3"
	if test "x$verA" == "x" || test "x$verB" == "x" || test "x$op" == x; then
		AC_MSG_ERROR([ac_compare_versions: Missing parameters])
	fi
	case "$op" in
		"lt"|"<")
			printf '%s\n%s\n' "$verA" "$verB" | sort -V -C
			if test $? -eq 0 && test "$verA" != "$verB"; then
				result=true
			fi
			;;
		"le"|"<=")
			printf '%s\n%s\n' "$verA" "$verB" | sort -V -C 
			if test $? -eq 0; then
				result=true
			fi
			;;
		"eq"|"==")
			if test "$verB" = "$verA"; then
				result=true
			fi
			;;
		"ge"|">=")
			printf '%s\n%s\n' "$verB" "$verA" | sort -V -C
			if test $? -eq 0; then
				result=true
			fi
			;;
		"gt"|">")
			printf '%s\n%s\n' "$verB" "$verA" | sort -V -C
			if test $? -eq 0 && test "$verA" != "$verB"; then
				result=true
			fi
			;;
		*)
			AC_MSG_ERROR([Unknown operand: $op])
			;;
	esac
	if test "x$result" = "xtrue"; then
		true # need to make shell happy if 4 is empty
		$4
	else
		true # need to make shell happy if 5 is empty
		$5
	fi
])
