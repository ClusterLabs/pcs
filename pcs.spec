Name: pcs		
Version: 0.9.1
Release: 1%{?dist}
License: GPLv2
URL: http://github.com/feist/pcs
Group: System Environment/Base
BuildArch: noarch
BuildRequires: python2-devel
Summary: Pacemaker Configuration System	
Source0: http://people.redhat.com/cfeist/pcs/pcs-%{version}.tar.gz

Requires: pacemaker	

%description
pcs is a corosync and pacemaker configuration tool.  It permits users to
easily view, modify and created pacemaker based clusters.

%prep
%setup -q


%build


%install
rm -rf $RPM_BUILD_ROOT
pwd
make install DESTDIR=$RPM_BUILD_ROOT PYTHON_SITELIB=%{python_sitelib}
chmod 755 $RPM_BUILD_ROOT/%{python_sitelib}/pcs/pcs.py


%files
%defattr(-,root,root,-)
%{python_sitelib}/pcs
%{python_sitelib}/pcs-%{version}-py2.*.egg-info
/usr/sbin/pcs

%doc COPYING README

%changelog
* Mon Jan 23 2012 Chris Feist <cfeist@redhat.com> - 0.9.1-1
- Updated BuildRequires and %doc section for fedora

* Fri Jan 20 2012 Chris Feist <cfeist@redhat.com> - 0.9.0-2
- Updated spec file for fedora specific changes

* Mon Jan 16 2012 Chris Feist <cfeist@redhat.com> - 0.9.0-1
- Initial Build

