# Change Log

## [Unreleased]

### Added
- Resources in location constraints now may be specified by resource name
  patterns in addition to resource names ([rhbz#1362493])
- Proxy settings description in pcsd configuration file ([rhbz#1315627])
- Man page for pcsd ([rhbz#1378742])
- Pcs now allows to set `trace_ra` and `trace_file` options of `ocf:heartbeat`
  and `ocf:pacemaker` resources ([rhbz#1421702])
- `pcs resource describe` and `pcs stonith describe` commands now show all
  information about the specified agent if the `--full` flag is used
- `pcs resource manage | unmanage` enables respectively disables monitor
  operations when the `--monitor` flag is specified ([rhbz#1303969])

### Changed
- It is now possible to specify more than one resource in the `pcs resource
  enable` and `pcs resource disable` commands.

### Fixed
- Python 3: pcs no longer spams stderr with error messages when communicating
  with another node
- Stopping a cluster does not timeout too early and it generally works better
  even if the cluster is running Virtual IP resources ([rhbz#1334429])
- `pcs booth remove` now works correctly even if the booth resource group is
  disabled (another fix) ([rhbz#1389941])

[rhbz#1303969]: https://bugzilla.redhat.com/show_bug.cgi?id=1303969
[rhbz#1315627]: https://bugzilla.redhat.com/show_bug.cgi?id=1315627
[rhbz#1334429]: https://bugzilla.redhat.com/show_bug.cgi?id=1334429
[rhbz#1362493]: https://bugzilla.redhat.com/show_bug.cgi?id=1362493
[rhbz#1378742]: https://bugzilla.redhat.com/show_bug.cgi?id=1378742
[rhbz#1389941]: https://bugzilla.redhat.com/show_bug.cgi?id=1389941
[rhbz#1421702]: https://bugzilla.redhat.com/show_bug.cgi?id=1421702


## [0.9.156] - 2017-02-10

### Added
- Fencing levels now may be targeted in CLI by a node name pattern or a node
  attribute in addition to a node name ([rhbz#1261116])
- `pcs cluster cib-push` allows to push a diff obtained internally by comparing
  CIBs in specified files ([rhbz#1404233], [rhbz#1419903])
- Added flags `--wait`, `--disabled`, `--group`, `--after`, `--before` into
  the command `pcs stonith create`
- Added commands `pcs stonith enable` and `pcs stonith disable`
- Command line option --request-timeout ([rhbz#1292858])
- Check whenever proxy is set when unable to connect to a node ([rhbz#1315627])

### Changed
- `pcs node [un]standby` and `pcs node [un]maintenance` is now atomic even if
  more than one node is specified ([rhbz#1315992])
- Restarting pcsd initiated from pcs is now a synchronous operation
  ([rhbz#1284404])
- Stopped bundling fonts used in pcsd GUI ([ghissue#125])
- In `pcs resource create` flags `--master` and `--clone` changed to keywords
  `master` and `clone`
- libcurl is now used for node to node communication

### Fixed
- When upgrading CIB to the latest schema version, check for minimal common
  version across the cluster ([rhbz#1389443])
- `pcs booth remove` now works correctly even if the booth resource group is
  disabled ([rhbz#1389941])
- Adding a node in a CMAN cluster does not cause the new node to be fenced
  immediately ([rhbz#1394846])
- Show proper error message when there is an HTTP communication failure
  ([rhbz#1394273])
- Fixed searching for files to remove in the `/var/lib` directory ([ghpull#119],
  [ghpull#120])
- Fixed messages when managing services (start, stop, enable, disable...)
- Fixed disabling services on systemd systems when using instances
  ([rhbz#1389501])
- Fixed parsing commandline options ([rhbz#1404229])
- Pcs does not exit with a false error message anymore when pcsd-cli.rb outputs
  to stderr ([ghissue#124])
- Pcs now exits with an error when both `--all` and a list of nodes is specified
  in the `pcs cluster start | stop | enable | disable` commands ([rhbz#1339355])
- built-in help and man page fixes and improvements ([rhbz#1347335])
- In `pcs resource create` the flag `--clone` no longer steals arguments from
  the keywords `meta` and `op` ([rhbz#1395226])
- `pcs resource create` does not produce invalid cib when group id is already
  occupied with non-resource element ([rhbz#1382004])
- Fixed misbehavior of the flag `--master` in `pcs resource create` command
  ([rhbz#1378107])
- Fixed tacit acceptance of invalid resource operation in `pcs resource create`
  ([rhbz#1398562])
- Fixed misplacing metadata for disabling when running `pcs resource create`
  with flags `--clone` and `--disabled` ([rhbz#1402475])
- Fixed incorrect acceptance of the invalid attribute of resource operation in
  `pcs resource create` ([rhbz#1382597])
- Fixed validation of options of resource operations in `pcs resource create`
  ([rhbz#1390071])
- Fixed silent omission of duplicate options ([rhbz#1390066])
- Added more validation for resource agent names ([rhbz#1387670])
- Fixed network communication issues in pcsd when a node was specified by an
  IPv6 address
- Fixed JS error in web UI when empty cluster status is received
  ([rhbz#1396462])
- Fixed sending user group in cookies from Python 3
- Fixed pcsd restart in Python 3
- Fixed parsing XML in Python 3 (caused crashes when reading resource agents
  metadata) ([rhbz#1419639])
- Fixed the recognition of the structure of a resource agent name that contains
  a systemd instance ([rhbz#1419661])

### Removed
- Ruby 1.8 and 1.9 is no longer supported due to bad libcurl support

[ghissue#124]: https://github.com/ClusterLabs/pcs/issues/124
[ghissue#125]: https://github.com/ClusterLabs/pcs/issues/125
[ghpull#119]: https://github.com/ClusterLabs/pcs/pull/119
[ghpull#120]: https://github.com/ClusterLabs/pcs/pull/120
[rhbz#1261116]: https://bugzilla.redhat.com/show_bug.cgi?id=1261116
[rhbz#1284404]: https://bugzilla.redhat.com/show_bug.cgi?id=1284404
[rhbz#1292858]: https://bugzilla.redhat.com/show_bug.cgi?id=1292858
[rhbz#1315627]: https://bugzilla.redhat.com/show_bug.cgi?id=1315627
[rhbz#1315992]: https://bugzilla.redhat.com/show_bug.cgi?id=1315992
[rhbz#1339355]: https://bugzilla.redhat.com/show_bug.cgi?id=1339355
[rhbz#1347335]: https://bugzilla.redhat.com/show_bug.cgi?id=1347335
[rhbz#1378107]: https://bugzilla.redhat.com/show_bug.cgi?id=1378107
[rhbz#1382004]: https://bugzilla.redhat.com/show_bug.cgi?id=1382004
[rhbz#1382597]: https://bugzilla.redhat.com/show_bug.cgi?id=1382597
[rhbz#1387670]: https://bugzilla.redhat.com/show_bug.cgi?id=1387670
[rhbz#1389443]: https://bugzilla.redhat.com/show_bug.cgi?id=1389443
[rhbz#1389501]: https://bugzilla.redhat.com/show_bug.cgi?id=1389501
[rhbz#1389941]: https://bugzilla.redhat.com/show_bug.cgi?id=1389941
[rhbz#1390066]: https://bugzilla.redhat.com/show_bug.cgi?id=1390066
[rhbz#1390071]: https://bugzilla.redhat.com/show_bug.cgi?id=1390071
[rhbz#1394273]: https://bugzilla.redhat.com/show_bug.cgi?id=1394273
[rhbz#1394846]: https://bugzilla.redhat.com/show_bug.cgi?id=1394846
[rhbz#1395226]: https://bugzilla.redhat.com/show_bug.cgi?id=1395226
[rhbz#1396462]: https://bugzilla.redhat.com/show_bug.cgi?id=1396462
[rhbz#1398562]: https://bugzilla.redhat.com/show_bug.cgi?id=1398562
[rhbz#1402475]: https://bugzilla.redhat.com/show_bug.cgi?id=1402475
[rhbz#1404229]: https://bugzilla.redhat.com/show_bug.cgi?id=1404229
[rhbz#1404233]: https://bugzilla.redhat.com/show_bug.cgi?id=1404233
[rhbz#1419639]: https://bugzilla.redhat.com/show_bug.cgi?id=1419639
[rhbz#1419661]: https://bugzilla.redhat.com/show_bug.cgi?id=1419661
[rhbz#1419903]: https://bugzilla.redhat.com/show_bug.cgi?id=1419903


## [0.9.155] - 2016-11-03

### Added
- Show daemon status in `pcs status` on non-systemd machines
- SBD support for cman clusters ([rhbz#1380352])
- Alerts management in pcsd ([rhbz#1376480])

### Changed
- Get all information about resource and stonith agents from pacemaker. Pcs now
  supports the same set of agents as pacemaker does. ([rhbz#1262001],
  [ghissue#81])
- `pcs resource create` now exits with an error if more than one resource agent
  matches the specified short agent name instead of randomly selecting one of
  the agents
- Allow to remove multiple alerts and alert recipients at once

### Fixed
- When stopping a cluster with some of the nodes unreachable, stop the cluster
  completely on all reachable nodes ([rhbz#1380372])
- Fixed pcsd crash when rpam rubygem is installed ([ghissue#109])
- Fixed occasional crashes / failures when using locale other than en\_US.UTF8
  ([rhbz#1387106])
- Fixed starting and stopping cluster services on systemd machines without
  the `service` executable ([ghissue#115])


[ghissue#81]: https://github.com/ClusterLabs/pcs/issues/81
[ghissue#109]: https://github.com/ClusterLabs/pcs/issues/109
[ghissue#115]: https://github.com/ClusterLabs/pcs/issues/115
[rhbz#1262001]: https://bugzilla.redhat.com/show_bug.cgi?id=1262001
[rhbz#1376480]: https://bugzilla.redhat.com/show_bug.cgi?id=1376480
[rhbz#1380352]: https://bugzilla.redhat.com/show_bug.cgi?id=1380352
[rhbz#1380372]: https://bugzilla.redhat.com/show_bug.cgi?id=1380372
[rhbz#1387106]: https://bugzilla.redhat.com/show_bug.cgi?id=1387106


## [0.9.154] - 2016-09-21
- There is no change log for this and previous releases. We are sorry.
- Take a look at git history if you are interested.
