# Change Log

## [Unreleased]

### Added
- Command `pcs client local-auth` for authentication of pcs client against local
  pcsd. This is required when a non-root user wants to execute a command which
  requires root permissions (e.g. `pcs cluster start`). ([rhbz#1554302])
- A warning is printed when adding a location constraint for a non-existent
  node ([rhbz#1522858])
- Allow non-root users to read quorum status (commands `pcs status corosync`,
  `pcs status quorum`, `pcs quorum device status`, `pcs quorum status`)
  ([rhbz#1594738])
- Command `pcs config checkpoint diff` for displaying differences between two
  specified checkpoints ([rhbz#1515021])
- Support for resource instance attributes uniqueness check according to
  resource agent metadata ([rhbz#1389140])

### Fixed
- pcsd.service now depends on network-online.target ([rhbz#1638376])
- Propose removing nodes from their clusters instead of destroying cluster on
  the nodes when trying to create new cluster from nodes which are already in
  a cluster ([rhbz#1474747])
- Pcs no longer removes empty `meta_attributes`, `instance_attributes` and other
  nvsets and similar elements from CIB. Such behavior was causing problems when
  pacemaker ACLs were in effect, leading to inability of pushing modified CIBs
  to pacemaker. ([rhbz#1642514])

[rhbz#1389140]: https://bugzilla.redhat.com/show_bug.cgi?id=1389140
[rhbz#1474747]: https://bugzilla.redhat.com/show_bug.cgi?id=1474747
[rhbz#1515021]: https://bugzilla.redhat.com/show_bug.cgi?id=1515021
[rhbz#1522858]: https://bugzilla.redhat.com/show_bug.cgi?id=1522858
[rhbz#1554302]: https://bugzilla.redhat.com/show_bug.cgi?id=1554302
[rhbz#1638376]: https://bugzilla.redhat.com/show_bug.cgi?id=1638376
[rhbz#1642514]: https://bugzilla.redhat.com/show_bug.cgi?id=1642514


## [0.9.166] - 2018-09-30

### Fixed
- Validation for an unaccessible resource inside a bundle ([rhbz#1462248])
- Test of watchdog devices ([rhbz#1475318])
- Possible race condition causing an HTTP 408 error when sending larger files
  via pcs ([rhbz#1600169])
- Support `diff-against` option of `pcs cluster cib-push` only for
  crm\_feature\_set > 3.0.8 ([rhbz#1488044])
- `pcs resource delete` accepts only one resource
- Show more user friendly error message when testing watchdog device and
  multiple devices are present ([rhbz#1475318])
- Do not distinguish betwen supported and unsupported watchdog devices as SBD
  cannot reliably provide such information ([rhbz#1475318])
- Instance attributes setting for fence agents `fence_compute` and
  `fence_evacuate` ([rhbz#1623181])

[rhbz#1462248]: https://bugzilla.redhat.com/show_bug.cgi?id=1462248
[rhbz#1475318]: https://bugzilla.redhat.com/show_bug.cgi?id=1475318
[rhbz#1488044]: https://bugzilla.redhat.com/show_bug.cgi?id=1488044
[rhbz#1594738]: https://bugzilla.redhat.com/show_bug.cgi?id=1594738
[rhbz#1600169]: https://bugzilla.redhat.com/show_bug.cgi?id=1600169
[rhbz#1623181]: https://bugzilla.redhat.com/show_bug.cgi?id=1623181


## [0.9.165] - 2018-06-21

### Added
- Pcsd option to reject client initiated SSL/TLS renegotiation ([rhbz#1566382])
- Commands for listing and testing watchdog devices ([rhbz#1475318]).
- Option for setting netmtu in `pcs cluster setup` command ([rhbz#1535967])
- Validation for an unaccessible resource inside a bundle ([rhbz#1462248])
- Options to display and filter failures by an operation and its interval in
  `pcs resource failcount reset` and `pcs resource failcount show` commands
  ([rhbz#1427273])
- When starting a cluster, each node is now started with a small delay to help
  preventing JOIN flood in corosync ([rhbz#1572886])

### Fixed
- `pcs cib-push diff-against=` does not consider an empty diff as an error
  ([ghpull#166])
- `pcs resource update` does not create an empty meta\_attributes element any
  more ([rhbz#1568353])
- `pcs resource debug-*` commands provide debug messages even with
  pacemaker-1.1.18 and newer ([rhbz#1574898])
- `pcs config` no longer crashes when `crm_mon` prints anything to stderr
  ([rhbz#1581150])
- Removing resources using web UI when the operation takes longer than expected
  ([rhbz#1579911])
- Improve `pcs quorum device add` usage and man page ([rhbz#1476862])
- `pcs resource failcount show` works correctly with pacemaker-1.1.18 and newer
  ([rhbz#1588667])
- Do not lowercase node addresses in the `pcs cluster auth` command
  ([rhbz#1590533])

### Changed
- Watchdog devices are validated against a list provided by sbd
  ([rhbz#1475318]).

[ghpull#166]: https://github.com/ClusterLabs/pcs/pull/166
[rhbz#1427273]: https://bugzilla.redhat.com/show_bug.cgi?id=1427273
[rhbz#1462248]: https://bugzilla.redhat.com/show_bug.cgi?id=1462248
[rhbz#1475318]: https://bugzilla.redhat.com/show_bug.cgi?id=1475318
[rhbz#1476862]: https://bugzilla.redhat.com/show_bug.cgi?id=1476862
[rhbz#1535967]: https://bugzilla.redhat.com/show_bug.cgi?id=1535967
[rhbz#1566382]: https://bugzilla.redhat.com/show_bug.cgi?id=1566382
[rhbz#1568353]: https://bugzilla.redhat.com/show_bug.cgi?id=1568353
[rhbz#1572886]: https://bugzilla.redhat.com/show_bug.cgi?id=1572886
[rhbz#1574898]: https://bugzilla.redhat.com/show_bug.cgi?id=1574898
[rhbz#1579911]: https://bugzilla.redhat.com/show_bug.cgi?id=1579911
[rhbz#1581150]: https://bugzilla.redhat.com/show_bug.cgi?id=1581150
[rhbz#1588667]: https://bugzilla.redhat.com/show_bug.cgi?id=1588667
[rhbz#1590533]: https://bugzilla.redhat.com/show_bug.cgi?id=1590533


## [0.9.164] - 2018-04-09

### Security
- CVE-2018-1086: Debug parameter removal bypass, allowing information disclosure
  ([rhbz#1557366])
- CVE-2018-1079: Privilege escalation via authorized user malicious REST call
  ([rhbz#1550243])
- CVE-2018-1000119 rack-protection: Timing attack in authenticity\_token.rb
  ([rhbz#1534027])

[rhbz#1534027]: https://bugzilla.redhat.com/show_bug.cgi?id=1534027
[rhbz#1550243]: https://bugzilla.redhat.com/show_bug.cgi?id=1550243
[rhbz#1557366]: https://bugzilla.redhat.com/show_bug.cgi?id=1557366


## [0.9.163] - 2018-02-20

### Added
- Added `pcs status booth` as an alias to `pcs booth status`
- A warning is displayed in `pcs status` and a stonith device detail in web UI
  when a stonith device has its `method` option set to `cycle` ([rhbz#1523378])

### Fixed
- `--skip-offline` is no longer ignored in the `pcs quorum device remove`
  command
- pcs now waits up to 5 minutes (previously 10 seconds) for pcsd restart when
  synchronizing pcsd certificates
- Usage and man page now correctly state it is possible to enable or disable
  several stonith devices at once
- It is now possible to set the `action` option of stonith devices in web UI by
  using force ([rhbz#1421702])
- Do not crash when `--wait` is used in `pcs stonith create` ([rhbz#1522813])
- Nodes are now authenticated after running `pcs cluster auth` even if
  an existing corosync.conf defines no nodes ([ghissue#153], [rhbz#1517333])
- Pcs now properly exits with code 1 when an error occurs in `pcs cluster node
  add-remote` and `pcs cluster node add-guest` commands ([rhbz#1464781])
- Fixed a crash in the `pcs booth sync` command ([rhbz#1527530])
- Always replace the whole CIB instead of applying a diff when
  crm\_feature\_set <= 3.0.8 ([rhbz#1488044])
- Fixed `pcs cluster auth` in a cluster when not authenticated and using
  a non-default port ([rhbz#1415197])
- Fixed `pcs cluster auth` in a cluster when previously authenticated using a
  non-default port and reauthenticating using an implicit default port
  ([rhbz#1415197])

[ghissue#153]: https://github.com/ClusterLabs/pcs/issues/153
[rhbz#1415197]: https://bugzilla.redhat.com/show_bug.cgi?id=1415197
[rhbz#1421702]: https://bugzilla.redhat.com/show_bug.cgi?id=1421702
[rhbz#1464781]: https://bugzilla.redhat.com/show_bug.cgi?id=1464781
[rhbz#1488044]: https://bugzilla.redhat.com/show_bug.cgi?id=1488044
[rhbz#1517333]: https://bugzilla.redhat.com/show_bug.cgi?id=1517333
[rhbz#1522813]: https://bugzilla.redhat.com/show_bug.cgi?id=1522813
[rhbz#1523378]: https://bugzilla.redhat.com/show_bug.cgi?id=1523378
[rhbz#1527530]: https://bugzilla.redhat.com/show_bug.cgi?id=1527530


## [0.9.162] - 2017-11-15

### Added
- `pcs status --full` now displays information about tickets ([rhbz#1389943])
- Support for managing qdevice heuristics ([rhbz#1389209])
- SNMP agent providing information about cluster to the master agent. It
  supports only python 2.7 for now ([rhbz#1367808]).

### Fixed
- Fixed crash when loading a huge xml ([rhbz#1506864])
- Fixed adding an existing cluster into the web UI ([rhbz#1415197])
- False warnings about failed actions when resource is master/unmaster from the
  web UI ([rhbz#1506220])

### Changed
- `pcs resource|stonith cleanup` no longer deletes the whole operation history
  of resources. Instead, it only deletes failed operations from the history. The
  original functionality is available in the `pcs resource|stonith refresh`
  command. ([rhbz#1508351], [rhbz#1508350])

[rhbz#1367808]: https://bugzilla.redhat.com/show_bug.cgi?id=1367808
[rhbz#1389209]: https://bugzilla.redhat.com/show_bug.cgi?id=1389209
[rhbz#1389943]: https://bugzilla.redhat.com/show_bug.cgi?id=1389943
[rhbz#1415197]: https://bugzilla.redhat.com/show_bug.cgi?id=1415197
[rhbz#1506220]: https://bugzilla.redhat.com/show_bug.cgi?id=1506220
[rhbz#1506864]: https://bugzilla.redhat.com/show_bug.cgi?id=1506864
[rhbz#1508350]: https://bugzilla.redhat.com/show_bug.cgi?id=1508350
[rhbz#1508351]: https://bugzilla.redhat.com/show_bug.cgi?id=1508351


## [0.9.161] - 2017-11-02

### Added
- List of pcs and pcsd capabilities ([rhbz#1230919])

### Fixed
- Fixed `pcs cluster auth` when already authenticated and using different port
  ([rhbz#1415197])
- It is now possible to restart a bundle resource on one node ([rhbz#1501274])
- `resource update` no longer exits with an error when the `remote-node` meta
  attribute is set to the same value that it already has
  ([rhbz#1502715], [ghissue#145])
- Listing and describing resource and stonith agents no longer crashes when
  agents' metadata contain non-ascii characters ([rhbz#1503110], [ghissue#151])

[ghissue#145]: https://github.com/ClusterLabs/pcs/issues/145
[ghissue#151]: https://github.com/ClusterLabs/pcs/issues/151
[rhbz#1230919]: https://bugzilla.redhat.com/show_bug.cgi?id=1230919
[rhbz#1415197]: https://bugzilla.redhat.com/show_bug.cgi?id=1415197
[rhbz#1501274]: https://bugzilla.redhat.com/show_bug.cgi?id=1501274
[rhbz#1502715]: https://bugzilla.redhat.com/show_bug.cgi?id=1502715
[rhbz#1503110]: https://bugzilla.redhat.com/show_bug.cgi?id=1503110


## [0.9.160] - 2017-10-09

### Added
- Configurable pcsd port ([rhbz#1415197])
- Description of the `--force` option added to man page and help
  ([rhbz#1491631])

### Fixed
- Fixed some crashes when pcs encounters a non-ascii character in environment
  variables, command line arguments and so on ([rhbz#1435697])
- Fixed detecting if systemd is in use ([ghissue#118])
- Upgrade CIB schema version when `resource-discovery` option is used in
  location constraints ([rhbz#1420437])
- Fixed error messages in `pcs cluster report` ([rhbz#1388783])
- Increase request timeout when starting a cluster with large number of nodes
  to prevent timeouts ([rhbz#1463327])
- Fixed "Unable to update cib" error caused by invalid resource operation IDs
- `pcs resource op defaults` now fails on an invalid option ([rhbz#1341582])
- Fixed behaviour of `pcs cluster verify` command when entered with the filename
  argument ([rhbz#1213946])

### Changed
- CIB changes are now pushed to pacemaker as a diff in commands overhauled to
  the new architecture (previously the whole CIB was pushed). This resolves
  race conditions and ACLs related errors when pushing CIB. ([rhbz#1441673])
- All actions / operations defined in resource agent's metadata (except
  meta-data, status and validate-all) are now copied to the CIB when creating
  a resource. ([rhbz#1418199], [ghissue#132])
- Improve documentation of the `pcs stonith confirm` command ([rhbz#1489682])

### Deprecated
- This is the last version fully supporting CMAN clusters and python 2.6.
  Support for these will be gradually dropped.

[ghissue#118]: https://github.com/ClusterLabs/pcs/issues/118
[ghissue#132]: https://github.com/ClusterLabs/pcs/issues/132
[rhbz#1213946]: https://bugzilla.redhat.com/show_bug.cgi?id=1213946
[rhbz#1341582]: https://bugzilla.redhat.com/show_bug.cgi?id=1341582
[rhbz#1388783]: https://bugzilla.redhat.com/show_bug.cgi?id=1388783
[rhbz#1415197]: https://bugzilla.redhat.com/show_bug.cgi?id=1415197
[rhbz#1418199]: https://bugzilla.redhat.com/show_bug.cgi?id=1418199
[rhbz#1420437]: https://bugzilla.redhat.com/show_bug.cgi?id=1420437
[rhbz#1435697]: https://bugzilla.redhat.com/show_bug.cgi?id=1435697
[rhbz#1441673]: https://bugzilla.redhat.com/show_bug.cgi?id=1441673
[rhbz#1463327]: https://bugzilla.redhat.com/show_bug.cgi?id=1463327
[rhbz#1489682]: https://bugzilla.redhat.com/show_bug.cgi?id=1489682
[rhbz#1491631]: https://bugzilla.redhat.com/show_bug.cgi?id=1491631


## [0.9.159] - 2017-06-30

### Added
- Option to create a cluster with or without corosync encryption enabled,
  by default the encryption is disabled ([rhbz#1165821])
- It is now possible to disable, enable, unmanage and manage bundle resources
  and set their meta attributes ([rhbz#1447910])
- Pcs now warns against using the `action` option of stonith devices
  ([rhbz#1421702])

### Fixed
- Fixed crash of the `pcs cluster setup` command when the `--force` flag was
  used ([rhbz#1176018])
- Fixed crash of the `pcs cluster destroy --all` command when the cluster was
  not running ([rhbz#1176018])
- Fixed crash of the `pcs config restore` command when restoring pacemaker
  authkey ([rhbz#1176018])
- Fixed "Error: unable to get cib" when adding a node to a stopped cluster
  ([rhbz#1176018])
- Fixed a crash in the `pcs cluster node add-remote` command when an id
  conflict occurs ([rhbz#1386114])
- Fixed creating a new cluster from the web UI ([rhbz#1284404])
- `pcs cluster node add-guest` now works with the flag `--skip-offline`
  ([rhbz#1176018])
- `pcs cluster node remove-guest` can be run again when the guest node was
  unreachable first time ([rhbz#1176018])
- Fixed "Error: Unable to read /etc/corosync/corosync.conf" when running
  `pcs resource create`([rhbz#1386114])
- It is now possible to set `debug` and `verbose` parameters of stonith devices
  ([rhbz#1432283])
- Resource operation ids are now properly validated and no longer ignored in
  `pcs resource create`, `pcs resource update` and `pcs resource op add`
  commands ([rhbz#1443418])
- Flag `--force` works correctly when an operation is not successful on some
  nodes during `pcs cluster node add-remote` or `pcs cluster node add-guest`
  ([rhbz#1464781])

### Changed
- Binary data are stored in corosync authkey ([rhbz#1165821])
- It is now mandatory to specify container type in the `resource bundle create`
  command
- When creating a new cluster, corosync communication encryption is disabled
  by default (in 0.9.158 it was enabled by default, in 0.9.157 and older it was
  disabled)

[rhbz#1165821]: https://bugzilla.redhat.com/show_bug.cgi?id=1165821
[rhbz#1176018]: https://bugzilla.redhat.com/show_bug.cgi?id=1176018
[rhbz#1284404]: https://bugzilla.redhat.com/show_bug.cgi?id=1284404
[rhbz#1386114]: https://bugzilla.redhat.com/show_bug.cgi?id=1386114
[rhbz#1421702]: https://bugzilla.redhat.com/show_bug.cgi?id=1421702
[rhbz#1432283]: https://bugzilla.redhat.com/show_bug.cgi?id=1432283
[rhbz#1443418]: https://bugzilla.redhat.com/show_bug.cgi?id=1443418
[rhbz#1447910]: https://bugzilla.redhat.com/show_bug.cgi?id=1447910
[rhbz#1464781]: https://bugzilla.redhat.com/show_bug.cgi?id=1464781


## [0.9.158] - 2017-05-23

### Added
- Support for bundle resources (CLI only) ([rhbz#1433016])
- Commands for adding and removing guest and remote nodes including handling
  pacemaker authkey (CLI only) ([rhbz#1176018], [rhbz#1254984], [rhbz#1386114],
  [rhbz#1386512])
- Command `pcs cluster node clear` to remove a node from pacemaker's
  configuration and caches
- Backing up and restoring cluster configuration by `pcs config backup` and
  `pcs config restore` commands now support corosync and pacemaker authkeys
  ([rhbz#1165821], [rhbz#1176018])

### Deprecated
- `pcs cluster remote-node add` and `pcs cluster remote-node remove `commands
  have been deprecated in favor of `pcs cluster node add-guest` and `pcs
  cluster node remove-guest` commands ([rhbz#1386512])

### Fixed
- Fixed a bug which under specific conditions caused pcsd to crash on start
  when running under systemd ([ghissue#134])
- `pcs resource unmanage` now sets the unmanaged flag to primitive resources
  even if a clone or master/slave resource is specified. Thus the primitive
  resources will not become managed just by uncloning. This also prevents some
  discrepancies between disabled monitor operations and the unmanaged flag.
  ([rhbz#1303969])
- `pcs resource unmanage --monitor` now properly disables monitor operations
  even if a clone or master/slave resource is specified. ([rhbz#1303969])
- `--help` option now shows help just for the specified command. Previously the
  usage for a whole group of commands was shown.
- Fixed a crash when `pcs cluster cib-push` is called with an explicit value of
  the `--wait` flag ([rhbz#1422667])
- Handle pcsd crash when an unusable address is set in `PCSD_BIND_ADDR`
  ([rhbz#1373614])
- Removal of a pacemaker remote resource no longer causes the respective remote
  node to be fenced ([rhbz#1390609])

### Changed
- Newly created clusters are set up to encrypt corosync communication
  ([rhbz#1165821], [ghissue#98])

[ghissue#98]: https://github.com/ClusterLabs/pcs/issues/98
[ghissue#134]: https://github.com/ClusterLabs/pcs/issues/134
[rhbz#1176018]: https://bugzilla.redhat.com/show_bug.cgi?id=1176018
[rhbz#1254984]: https://bugzilla.redhat.com/show_bug.cgi?id=1254984
[rhbz#1303969]: https://bugzilla.redhat.com/show_bug.cgi?id=1303969
[rhbz#1373614]: https://bugzilla.redhat.com/show_bug.cgi?id=1373614
[rhbz#1386114]: https://bugzilla.redhat.com/show_bug.cgi?id=1386114
[rhbz#1386512]: https://bugzilla.redhat.com/show_bug.cgi?id=1386512
[rhbz#1390609]: https://bugzilla.redhat.com/show_bug.cgi?id=1390609
[rhbz#1422667]: https://bugzilla.redhat.com/show_bug.cgi?id=1422667
[rhbz#1433016]: https://bugzilla.redhat.com/show_bug.cgi?id=1433016
[rhbz#1165821]: https://bugzilla.redhat.com/show_bug.cgi?id=1165821


## [0.9.157] - 2017-04-10

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
- Support for shared storage in SBD. Currently, there is very limited support
  in web UI ([rhbz#1413958])

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
- Fixed Cross-site scripting (XSS) vulnerability in web UI ([CVE-2017-2661],
  [rhbz#1434111])
- Pcs no longer allows to create a stonith resource based on an agent whose
  name contains a colon ([rhbz#1415080])
- Pcs command now launches Python interpreter with "sane" options (python -Es)
  ([rhbz#1328882])
- Clufter is now supported on both Python 2 and Python 3 ([rhbz#1428350])
- Do not colorize clufter output if saved to a file

[CVE-2017-2661]: https://access.redhat.com/security/cve/CVE-2017-2661
[rhbz#1303969]: https://bugzilla.redhat.com/show_bug.cgi?id=1303969
[rhbz#1315627]: https://bugzilla.redhat.com/show_bug.cgi?id=1315627
[rhbz#1328882]: https://bugzilla.redhat.com/show_bug.cgi?id=1328882
[rhbz#1334429]: https://bugzilla.redhat.com/show_bug.cgi?id=1334429
[rhbz#1362493]: https://bugzilla.redhat.com/show_bug.cgi?id=1362493
[rhbz#1378742]: https://bugzilla.redhat.com/show_bug.cgi?id=1378742
[rhbz#1389941]: https://bugzilla.redhat.com/show_bug.cgi?id=1389941
[rhbz#1413958]: https://bugzilla.redhat.com/show_bug.cgi?id=1413958
[rhbz#1415080]: https://bugzilla.redhat.com/show_bug.cgi?id=1415080
[rhbz#1421702]: https://bugzilla.redhat.com/show_bug.cgi?id=1421702
[rhbz#1428350]: https://bugzilla.redhat.com/show_bug.cgi?id=1428350
[rhbz#1434111]: https://bugzilla.redhat.com/show_bug.cgi?id=1434111


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
- Stopped bundling fonts used in pcsd web UI ([ghissue#125])
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
