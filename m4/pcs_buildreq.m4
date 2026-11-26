dnl Macros for checking and recording rpm BuildRequires of packages detected
dnl via pkg-config (devel packages shipping .pc files). They are not limited
dnl to dependencies of bundled things: PCS_CHECK_BUILDREQ_PKG can check and
dnl record any package that provides a *.pc file. The current (and so far
dnl only) use is additional build dependencies needed to build bundled python
dnl modules and ruby gems from source - PCS_CHECK_BUILDREQ_PKG is called when
dnl PCS_CHECK_PYMOD / PCS_CHECK_GEM set module_bundled=yes - and the records
dnl are stored in rpm/bundle_buildrequires.txt (consumed by Makefile.am to
dnl fill @bundlebuildreqs@ in the spec), which is where that bundle-specific
dnl file name comes from.
dnl
dnl PCS_BUILDREQ_INIT must be called once before any other macro from this file.

# PCS_BUILDREQ_INIT
# Truncate the BuildRequires list so a reconfigure starts from a clean slate.
AC_DEFUN([PCS_BUILDREQ_INIT], [
	rm -f $ac_pwd/rpm/bundle_buildrequires.txt
	touch $ac_pwd/rpm/bundle_buildrequires.txt
])

# PCS_RECORD_BUILDREQ([rpm-dep], [version])
# Record "rpm-dep[ version]" as an rpm BuildRequires. An identical record is
# stored only once, so several bundled modules may require the same dependency.
# If the dependency is already recorded with a different version, both records
# are kept (rpm applies both constraints) and a warning is printed.
AC_DEFUN([PCS_RECORD_BUILDREQ], [
	buildreq_file="$ac_pwd/rpm/bundle_buildrequires.txt"
	buildreq_dep="$1"
	buildreq_line="$1"
	if test "x$2" != "x"; then
		buildreq_line="$buildreq_line $2"
	fi
	if ! grep -qxF "$buildreq_line" "$buildreq_file"; then
		if $AWK -v d="$buildreq_dep" '$[]1 == d { found = 1 } END { exit !found }' "$buildreq_file"; then
			AC_MSG_WARN([build dependency $buildreq_dep is required with different versions, consider unifying them])
		fi
		echo "$buildreq_line" >> "$buildreq_file"
	fi
])

# PCS_CHECK_BUILDREQ_PKG([pkgconfig-module], [version], [rpm-dep])
# Check that the pkg-config module (shipped as a .pc file by a devel package) is
# available, optionally in the given version (e.g. ">= 2.9", compared against
# the Version field of the .pc file), and record it as an rpm BuildRequires.
# rpm-dep defaults to "pkgconfig(<pkgconfig-module>)" which rpm provides
# automatically for every .pc file.
#
# Meant for native (C/C++) system libraries, detected via the .pc file
# shipped by their devel package. Any such library can be checked and
# recorded, not only ones which compiled extensions of bundled modules link
# against - that is just the current use. Not for python modules or ruby
# gems, those are handled by PCS_CHECK_PYMOD / PCS_CHECK_GEM.
#
# The pkgconfig-module is the name of the .pc file without the suffix, e.g.
# libxml-2.0 for libxml-2.0.pc. Find it with
#   rpm -ql libxml2-devel | grep '\.pc$'   or   pkg-config --list-all
# Check the default rpm dependency with
#   rpm -q --whatprovides 'pkgconfig(libxml-2.0)'
#
# Runtime Requires are not recorded: rpm generates soname dependencies
# (e.g. libxml2.so.2()(64bit)) automatically from the built native extensions
# by its AutoReq mechanism (elfdeps dependency generator).
AC_DEFUN([PCS_CHECK_BUILDREQ_PKG], [
	buildreq_rpm="$3"
	if test "x$buildreq_rpm" = "x"; then
		buildreq_rpm="pkgconfig($1)"
	fi
	AC_MSG_CHECKING([for build dependency $1 $2])
	PKG_CHECK_EXISTS([$1 $2],
		[AC_MSG_RESULT([yes])],
		[
			AC_MSG_RESULT([no])
			AC_MSG_ERROR([pkg-config module $1 $2 not found, install $buildreq_rpm])
		]
	)
	PCS_RECORD_BUILDREQ([$buildreq_rpm], [$2])
])
