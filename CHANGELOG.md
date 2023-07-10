# Change Log

## [Unreleased]

### Fixed
- Exporting constraints with rules in form of pcs commands now escapes `#` and
  fixes spaces in dates to make the commands valid ([rhbz#2163953])

### Deprecated
- Using spaces in dates in location constraint rules (using spaces in dates in
  rules in other parts of configuration was never allowed) ([rhbz#2163953])

[rhbz#2163953]: https://bugzilla.redhat.com/show_bug.cgi?id=2163953


## [0.11.6] - 2023-06-20

### Added
- Support for output formats `json` and `cmd` to constraints config commands
  ([rhbz#2179388], [rhbz#1423473], [rhbz#2163953])
- Automatic restarts of the Puma web server in the legacy Ruby daemon to reduce
  its memory footprint ([rhbz#1860626])
- New URL for listing pcsd capabilities: `/capabilities`
- It is now possible to list pcsd capabilities even if pcsd is not running:
  `pcsd --version --full`
- Add lib commands `cluster_property.get_properties` and
  `cluster_property.get_properties_metadata` to API v2
- Add `pcs property defaults` and `pcs property describe` CLI commands
- Support for output formats `json` and `cmd` to property config command
  ([rhbz#2163914])
- Commands `pcs resource describe` and `pcs stonith describe` print detailed
  info about resource options (data type or allowed values, default value)
- Add warning to `pcs resource utilization` and `pcs node utilization` for the
  case configuration is not in effect (cluster property `placement-strategy` is
  not set appropriately) ([rhbz#1465829])
- New format of `pcs resource create` command which requires `meta` keyword for
  specifying clone and promotable meta attributes is available to be enabled
  by specifying --future ([rhbz#2168155])

### Fixed
- Crash in commands that ask for user input (like `pcs cluster destroy`) when
  stdin is closed ([ghissue#612])
- Fix displaying differences between configuration checkpoints in
  `pcs config checkpoint diff` command ([rhbz#2175881])
- Fix `pcs stonith update-scsi-devices` command which was broken since
  Pacemaker-2.1.5-rc1 ([rhbz#2177996])
- Make `pcs resource disable --simulate --brief` documentation clearer
  ([rhbz#2109852])
- Fixed a regression causing crash in `pcs resource move` command (broken since
  pcs-0.11.5) ([rhbz#2210855])
- Using `--force` in `pcs resource meta` command had no effect on a specific
  error message even if the message suggested otherwise.

### Changed
- Commands for displaying cluster configuration have been slightly updated:
  - Headings of empty sections are no longer displayed
  - Resource listing is more dense as operations options are shown in a single
    line
  - Specifying `--full` to show IDs of elements now shows IDs of nvpairs as well

### Deprecated
- Specifying clone and promotable meta attributes without the `meta` keyword is
  now deprecated, i.e. `pcs resource clone myResource name=value` is deprecated
  by `pcs resource clone myResource meta name=value`
  ([rhbz#2168155], [ghpull#648])

[ghissue#612]: https://github.com/ClusterLabs/pcs/issues/612
[ghpull#648]: https://github.com/ClusterLabs/pcs/pull/648
[rhbz#1423473]: https://bugzilla.redhat.com/show_bug.cgi?id=1423473
[rhbz#1465829]: https://bugzilla.redhat.com/show_bug.cgi?id=1465829
[rhbz#1860626]: https://bugzilla.redhat.com/show_bug.cgi?id=1860626
[rhbz#2109852]: https://bugzilla.redhat.com/show_bug.cgi?id=2109852
[rhbz#2163914]: https://bugzilla.redhat.com/show_bug.cgi?id=2163914
[rhbz#2163953]: https://bugzilla.redhat.com/show_bug.cgi?id=2163953
[rhbz#2168155]: https://bugzilla.redhat.com/show_bug.cgi?id=2168155
[rhbz#2175881]: https://bugzilla.redhat.com/show_bug.cgi?id=2175881
[rhbz#2177996]: https://bugzilla.redhat.com/show_bug.cgi?id=2177996
[rhbz#2179388]: https://bugzilla.redhat.com/show_bug.cgi?id=2179388
[rhbz#2210855]: https://bugzilla.redhat.com/show_bug.cgi?id=2210855


## [0.11.5] - 2023-03-01

### Added
- Warning to `pcs resource|stonith update` commands about not using agent
  self-validation feature when the resource is already misconfigured
  ([rhbz#2151524])
- Add lib command `cluster_property.set_properties` to API v2
- Commands for checking and creating qdevice certificates on the local node only

### Fixed
- Graceful stopping pcsd service using `systemctl stop pcsd` command
- Displaying bool and integer values in `pcs resource config` command
  ([rhbz#2151164], [ghissue#604])
- Allow time values in stonith-watchdog-time property ([rhbz#2158790])
- Enable/Disable sbd when cluster is not running ([rhbz#2166249])
- Confusing error message in `pcs constraint ticket add` command
  ([rhbz#2168617], [ghpull#559])
- Internal server error during cluster setup with Ruby 3.2
- Set `Content-Security-Policy: frame-ancestors 'self'; default-src 'self'`
  HTTP header for HTTP 404 responses as well ([rhbz#2160664])
- Validate dates in location constraint rules ([ghpull#644])

### Changed
- Resource/stonith agent self-validation of instance attributes is now
  disabled by default, as many agents do not work with it properly.
  Use flag '--agent-validation' to enable it in supported commands.
  ([rhbz#2159454])

[ghissue#604]: https://github.com/ClusterLabs/pcs/issues/604
[ghpull#559]: https://github.com/ClusterLabs/pcs/pull/559
[ghpull#644]: https://github.com/ClusterLabs/pcs/pull/644
[rhbz#2151164]: https://bugzilla.redhat.com/show_bug.cgi?id=2151164
[rhbz#2151524]: https://bugzilla.redhat.com/show_bug.cgi?id=2151524
[rhbz#2158790]: https://bugzilla.redhat.com/show_bug.cgi?id=2158790
[rhbz#2159454]: https://bugzilla.redhat.com/show_bug.cgi?id=2159454
[rhbz#2160664]: https://bugzilla.redhat.com/show_bug.cgi?id=2160664
[rhbz#2166249]: https://bugzilla.redhat.com/show_bug.cgi?id=2166249
[rhbz#2168617]: https://bugzilla.redhat.com/show_bug.cgi?id=2168617


## [0.11.4] - 2022-11-21

### Security
- CVE-2022-2735 pcs: obtaining an authentication token for hacluster user could
  lead to privilege escalation ([rhbz#2116841])

### Added
- API v2 providing asynchronous interface for pcsd. Note that this feature is
  in tech-preview state and thus may be changed in the future
- Support for resource/stonith agent self-validation of instance attributes via
  pacemaker ([rhbz#2112270])
- Support for booth 'enable-authfile' fix ([rhbz#2116295])

### Fixed
- `pcs resource manage --monitor` no longer enables monitor operation for all
  resources in a group if only one of the resources was requested to become
  managed ([rhbz#2092950])
- `pcs resource restart` command works again (broken in pcs-0.11.3)
  ([rhbz#2102663])
- Misleading error message from `pcs booth sync` when booth config directory
  (`/etc/booth`) is missing ([rhbz#1791670])
- Creating a promotable or globally-unique clones is not allowed for non-ocf
  resource agents ([rhbz#1493416])
- Improved cluster properties validators, OCF 1.1 now supported ([rhbz#2019464])
- `pcs property set/unset` forbid manipulation of specific cluster properties
  ([rhbz#1620043])

[rhbz#1493416]: https://bugzilla.redhat.com/show_bug.cgi?id=1493416
[rhbz#1620043]: https://bugzilla.redhat.com/show_bug.cgi?id=1620043
[rhbz#1791670]: https://bugzilla.redhat.com/show_bug.cgi?id=1791670
[rhbz#2019464]: https://bugzilla.redhat.com/show_bug.cgi?id=2019464
[rhbz#2092950]: https://bugzilla.redhat.com/show_bug.cgi?id=2092950
[rhbz#2102663]: https://bugzilla.redhat.com/show_bug.cgi?id=2102663
[rhbz#2112270]: https://bugzilla.redhat.com/show_bug.cgi?id=2112270
[rhbz#2116295]: https://bugzilla.redhat.com/show_bug.cgi?id=2116295
[rhbz#2116841]: https://bugzilla.redhat.com/show_bug.cgi?id=2116841


## [0.11.3] - 2022-06-23

### Security
- CVE-2022-1049: Pcs daemon was allowing expired accounts, and accounts with
  expired passwords to login when using PAM auth. ([huntr#220307],
  [rhbz#2068457])
- Pcsd does not expose the server name in HTTP headers anymore ([rhbz#2059122])
- Set `Strict-Transport-Security: max-age=63072000` HTTP header for all
  responses ([rhbz#2097731])
- Set HTTP headers to prevent caching everything except static files
  ([rhbz#2097733])
- Set HTTP headers to prevent sending referrer ([rhbz#2097732])
- Set cookie option SameSite to Lax ([rhbz#2097730])
- Set `Content-Security-Policy: frame-ancestors 'self'; default-src 'self'`
  HTTP header for all responses ([rhbz#2097778])

### Added
- Add support for fence\_mpath to `pcs stonith update-scsi-devices` command
  ([rhbz#2024522])
- Support for cluster UUIDs. New clusters now get a UUID during setup. Existing
  clusters can get a UUID by running the new `pcs cluster config uuid generate`
  command ([rhbz#2054671])
- Add warning regarding move constraints to `pcs status` ([rhbz#2058247])
- Support for output formats `json` and `cmd` to `pcs resource config` and `pcs
  stonith config` commands ([rhbz#2058251], [rhbz#2058252])

### Fixed
- Booth ticket name validation ([rhbz#2053177])
- Adding booth ticket doesn't report 'mode' as an unknown option anymore
  ([rhbz#2058243])
- Preventing fence-loop caused when stonith-watchdog-timeout is set
  with wrong value ([rhbz#2058246])
- Do not allow to create an order constraint for resources in one group as that
  may block Pacemaker ([ghpull#509])
- `pcs quorum device remove` works again ([rhbz#2095695])
- Fixed description of full permission ([rhbz#2059177])

[ghpull#509]: https://github.com/ClusterLabs/pcs/pull/509
[rhbz#2024522]: https://bugzilla.redhat.com/show_bug.cgi?id=2024522
[rhbz#2053177]: https://bugzilla.redhat.com/show_bug.cgi?id=2053177
[rhbz#2054671]: https://bugzilla.redhat.com/show_bug.cgi?id=2054671
[rhbz#2058243]: https://bugzilla.redhat.com/show_bug.cgi?id=2058243
[rhbz#2058246]: https://bugzilla.redhat.com/show_bug.cgi?id=2058246
[rhbz#2058247]: https://bugzilla.redhat.com/show_bug.cgi?id=2058247
[rhbz#2058251]: https://bugzilla.redhat.com/show_bug.cgi?id=2058251
[rhbz#2058252]: https://bugzilla.redhat.com/show_bug.cgi?id=2058252
[rhbz#2059122]: https://bugzilla.redhat.com/show_bug.cgi?id=2059122
[rhbz#2059177]: https://bugzilla.redhat.com/show_bug.cgi?id=2059177
[rhbz#2068457]: https://bugzilla.redhat.com/show_bug.cgi?id=2068457
[rhbz#2095695]: https://bugzilla.redhat.com/show_bug.cgi?id=2095695
[rhbz#2097730]: https://bugzilla.redhat.com/show_bug.cgi?id=2097730
[rhbz#2097731]: https://bugzilla.redhat.com/show_bug.cgi?id=2097731
[rhbz#2097732]: https://bugzilla.redhat.com/show_bug.cgi?id=2097732
[rhbz#2097733]: https://bugzilla.redhat.com/show_bug.cgi?id=2097733
[rhbz#2097778]: https://bugzilla.redhat.com/show_bug.cgi?id=2097778
[huntr#220307]: https://huntr.dev/bounties/7aa921fc-a568-4fd8-96f4-7cd826246aa5/


## [0.11.2] - 2022-02-01

### Fixed
- Pcs was not automatically enabling corosync-qdevice when adding a quorum
  device to a cluster (broken since pcs-0.10.9) ([rhbz#2028902])
- `resource update` command exiting with a traceback when updating a resource
  with a non-existing resource agent ([rhbz#2019836])
- pcs\_snmp\_agent is working again (broken since pcs-0.10.1) ([ghpull#431])
- Skip checking of scsi devices to be removed before unfencing to be added
  devices ([rhbz#2033248])
- Make `ocf:linbit:drbd` agent pass OCF standard validation ([ghissue#441],
  [rhbz#2036633])
- Multiple improvements of `pcs resource move` command ([rhbz#1996062])
- Pcs no longer creates Pacemaker-1.x CIB when `-f` is used, so running `pcs
  cluster cib-upgrade` manually is not needed ([rhbz#2022463])

### Deprecated
- Usage of `pcs resource` commands for stonith resources and vice versa
  ([rhbz#1301204])

[ghissue#441]: https://github.com/ClusterLabs/pcs/issues/441
[ghpull#431]: https://github.com/ClusterLabs/pcs/pull/431
[rhbz#1301204]: https://bugzilla.redhat.com/show_bug.cgi?id=1301204
[rhbz#1996062]: https://bugzilla.redhat.com/show_bug.cgi?id=1996062
[rhbz#2019836]: https://bugzilla.redhat.com/show_bug.cgi?id=2019836
[rhbz#2022463]: https://bugzilla.redhat.com/show_bug.cgi?id=2022463
[rhbz#2028902]: https://bugzilla.redhat.com/show_bug.cgi?id=2028902
[rhbz#2033248]: https://bugzilla.redhat.com/show_bug.cgi?id=2033248
[rhbz#2036633]: https://bugzilla.redhat.com/show_bug.cgi?id=2036633


## [0.11.1] - 2021-11-30

### Removed
- Deprecated obsolete commands `pcs config import-cman` and `pcs config export
  pcs-commands|pcs-commands-verbose` have been removed ([rhbz#1881064])
- Unused and unmaintained pcsd urls: `/remote/config_backup`,
  `/remote/node_available`, `/remote/resource_status`
- Pcsd no longer provides data in format used by web UI in pcs 0.9.142 and older

### Added
- Explicit confirmation is now required to prevent accidental destroying
  of the cluster with `pcs cluster destroy` ([rhbz#1283805])
-  Add add/remove cli syntax for command `pcs stonith update-scsi-devices`
   ([rhbz#1992668])
- Command `pcs resource move` is fully supported ([rhbz#1990787])
- Support for OCF 1.1 resource and stonith agents ([rhbz#2018969])

### Changed
- Pcs no longer depends on python3-distro package
- 'pcs status xml' now prints cluster status in the new format provided by
  Pacemaker 2.1 ([rhbz#1985981])
- All errors, warning and progress related output is now printed to stderr
  instead of stdout
- Make roles `Promoted` and `Unpromoted` default ([rhbz#1885293])
- Make auto-deleting constraint default for `pcs resource move` command
  ([rhbz#1996062])
- Deprecation warnings use a "Deprecation Warning:" prefix instead of
  "Warning:" on the command line
- Minimal required version of python has been changed to 3.9
- Minimal required version of ruby has been changed to 2.5
- Minimal supported version of pacemaker is 2.1

### Fixed
- Do not unfence newly added devices on fenced cluster nodes ([rhbz#1991654])
- Fix displaying fencing levels with regular expression targets ([rhbz#1533090])
- Reject cloning of stonith resources ([rhbz#1811072])
- Do not show warning that no stonith device was detected and stonith-enabled
  is not false when a stonith device is in a group ([ghpull#370])
- Misleading error message from `pcs quorum unblock` when `wait_for_all=0`
  ([rhbz#1968088])
- Misleading error message from `pcs booth setup` and `pcs booth pull` when
  booth config directory (`/etc/booth`) is missing ([rhbz#1791670],
  [ghpull#411], [ghissue#225])

### Deprecated
- Legacy role names `Master` and `Slave` ([rhbz#1885293])
- Option `--master` is deprecated and has been replaced by option `--promoted`
  ([rhbz#1885293])

[ghissue#225]: https://github.com/ClusterLabs/pcs/issues/225
[ghpull#370]: https://github.com/ClusterLabs/pcs/pull/370
[ghpull#411]: https://github.com/ClusterLabs/pcs/pull/411
[rhbz#1283805]: https://bugzilla.redhat.com/show_bug.cgi?id=1283805
[rhbz#1533090]: https://bugzilla.redhat.com/show_bug.cgi?id=1533090
[rhbz#1791670]: https://bugzilla.redhat.com/show_bug.cgi?id=1791670
[rhbz#1811072]: https://bugzilla.redhat.com/show_bug.cgi?id=1811072
[rhbz#1881064]: https://bugzilla.redhat.com/show_bug.cgi?id=1881064
[rhbz#1885293]: https://bugzilla.redhat.com/show_bug.cgi?id=1885293
[rhbz#1968088]: https://bugzilla.redhat.com/show_bug.cgi?id=1968088
[rhbz#1985981]: https://bugzilla.redhat.com/show_bug.cgi?id=1985981
[rhbz#1990787]: https://bugzilla.redhat.com/show_bug.cgi?id=1990787
[rhbz#1991654]: https://bugzilla.redhat.com/show_bug.cgi?id=1991654
[rhbz#1992668]: https://bugzilla.redhat.com/show_bug.cgi?id=1992668
[rhbz#1996062]: https://bugzilla.redhat.com/show_bug.cgi?id=1996062
[rhbz#2018969]: https://bugzilla.redhat.com/show_bug.cgi?id=2018969


## [0.10.10] - 2021-08-19

### Added
- Support for new role names introduced in pacemaker 2.1 ([rhbz#1885293])

### Fixed
- Traceback in some cases when --wait without timeout is used

[rhbz#1885293]: https://bugzilla.redhat.com/show_bug.cgi?id=1885293


## [0.10.9] - 2021-08-10

### Added
- Elliptic curve TLS certificates are now supported in pcsd ([ghissue#123])
- Support for corosync option `totem.block_unlisted_ips` ([rhbz#1720221])
- Support for displaying status of a single resource or tag ([rhbz#1290830])
- Support for displaying status of resources on a specified node
  ([rhbz#1285269])
- New option `--brief` for `pcs resource disable --safe` or its alias `pcs
  resource safe-disable` that only prints errors ([rhbz#1909901])
- Support for updating scsi fencing devices without affecting other resources
  added in the new command `pcs stonith update-scsi-devices` ([rhbz#1759995],
  [rhbz#1872378])
- Option `--autodelete` for `pcs resource move` command which removes a location
  constraint used for moving a resource, once the resource has been moved. This
  feature is in tech-preview state and thus may be changed in the future
  ([rhbz#1847102])

### Fixed
- Node attribute expressions are now correctly reported as not allowed in
  resource defaults rules ([rhbz#1896458])
- Upgreded to jquery 3.6.0 ([rhbz#1882291, rhbz#1886342])
- Man page and help: note that 'pcs resource unclone' accepts clone resources
  as well ([rhbz#1930886])
- Improved error messages when a host is found to be a part of a cluster already
  ([rhbz#1690419])
- `pcs cluster sync` command now warns reloading corosync config is necessary
  for changes to take effect ([rhbz#1750240])
- Show user friendly error if unable to delete a group (due to the group being
  referenced within configuration) when moving resources out of the the group.
  ([rhbz#1678273])
- Exit with an error if `on-fail=demote` is specified for a resource operation
  and pacemaker doesn't support it
- The `pcs status nodes` command now correctly shows status of nodes that are
  both in maintenance and standby modes ([rhbz#1432097])

### Changed
- python3-openssl was replaced with python3-cryptography ([rhbz#1927404])

### Deprecated
- `pcs acl show` replaced with `pcs acl config`
- `pcs alert show` replaced with `pcs alert config`
- Undocumented command `pcs cluster certkey` replaced with `pcs pcsd certkey`
- `pcs cluster pcsd-status` replaced with `pcs status pcsd` or `pcs pcsd status`
- `pcs constraint [location | colocation | order | ticket] show | list` replaced
  with `pcs constraint [location | colocation | order | ticket] config`
- `pcs property show`, `pcs property list` replaced with `pcs property config`
- pcsd urls: `/remote/config_backup`, `/remote/node_available`,
  `/remote/node_restart`, `/remote/resource_status`
- Undocumented syntax for constraint location rules:
  - `date start=<date> gt` replaced with `date gt <date>`
  - `date end=<date> lt` replaced with `date lt <date>`
  - `date start=<date> end=<date> in_range` replaced with `date in_range <date>
    to <date>`
  - `operation=date_spec` replaced with `date-spec <date-spec options>`
  - converting invalid score to score-attribute=pingd
- Delimiting stonith devices with a comma in `pcs stonith level add | clear |
  delete | remove` commands, use a space instead
- `pcs stonith level delete | remove [<target>] [<stonith id>]...` replaced with
  `pcs stonith level delete | remove [target <target>] [stonith <stonith id>]...`
- `pcs stonith level clear [<target> | <stonith ids>]` replaced with
  `pcs stonith level clear [target <target> | stonith <stonith id>...]`
- `pcs tag list` replaced with `pcs tag config`

[ghissue#123]: https://github.com/ClusterLabs/pcs/issues/123
[rhbz#1285269]: https://bugzilla.redhat.com/show_bug.cgi?id=1285269
[rhbz#1290830]: https://bugzilla.redhat.com/show_bug.cgi?id=1290830
[rhbz#1432097]: https://bugzilla.redhat.com/show_bug.cgi?id=1432097
[rhbz#1678273]: https://bugzilla.redhat.com/show_bug.cgi?id=1678273
[rhbz#1690419]: https://bugzilla.redhat.com/show_bug.cgi?id=1690419
[rhbz#1720221]: https://bugzilla.redhat.com/show_bug.cgi?id=1720221
[rhbz#1750240]: https://bugzilla.redhat.com/show_bug.cgi?id=1750240
[rhbz#1759995]: https://bugzilla.redhat.com/show_bug.cgi?id=1759995
[rhbz#1847102]: https://bugzilla.redhat.com/show_bug.cgi?id=1847102
[rhbz#1872378]: https://bugzilla.redhat.com/show_bug.cgi?id=1872378
[rhbz#1882291]: https://bugzilla.redhat.com/show_bug.cgi?id=1882291
[rhbz#1886342]: https://bugzilla.redhat.com/show_bug.cgi?id=1886342
[rhbz#1896458]: https://bugzilla.redhat.com/show_bug.cgi?id=1896458
[rhbz#1909901]: https://bugzilla.redhat.com/show_bug.cgi?id=1909901
[rhbz#1927404]: https://bugzilla.redhat.com/show_bug.cgi?id=1927404
[rhbz#1930886]: https://bugzilla.redhat.com/show_bug.cgi?id=1930886


## [0.10.8] - 2021-02-01

### Added
- Support for changing corosync configuration in an existing cluster
  ([rhbz#1457314], [rhbz#1667061], [rhbz#1856397], [rhbz#1774143])
- Command to show structured corosync configuration (see `pcs cluster
  config show` command) ([rhbz#1667066])

### Fixed
- Improved error message with a hint in `pcs cluster cib-push` ([ghissue#241])
- Option --wait was not working with pacemaker 2.0.5+ ([ghissue#260])
- Explicitly close libcurl connections to prevent stalled TCP connections in
  CLOSE-WAIT state ([ghissue#261], [rhbz#1885841])
- Fixed parsing negative float numbers on command line ([rhbz#1869399])
- Removed unwanted logging to system log (/var/log/messages) ([rhbz#1917286])
- Fixed rare race condition in `pcs cluster start --wait` ([rhbz#1794062])
- Better error message when unable to connect to pcsd ([rhbz#1619818])

### Deprecated
- Commands `pcs config import-cman` and `pcs config export
  pcs-commands|pcs-commands-verbose` have been deprecated ([rhbz#1851335])
- Entering values starting with '-' (negative numbers) without '--' on command
  line is now deprecated ([rhbz#1869399])

[ghissue#241]: https://github.com/ClusterLabs/pcs/issues/241
[ghissue#260]: https://github.com/ClusterLabs/pcs/issues/260
[ghissue#261]: https://github.com/ClusterLabs/pcs/issues/261
[rhbz#1457314]: https://bugzilla.redhat.com/show_bug.cgi?id=1457314
[rhbz#1619818]: https://bugzilla.redhat.com/show_bug.cgi?id=1619818
[rhbz#1667061]: https://bugzilla.redhat.com/show_bug.cgi?id=1667061
[rhbz#1667066]: https://bugzilla.redhat.com/show_bug.cgi?id=1667066
[rhbz#1774143]: https://bugzilla.redhat.com/show_bug.cgi?id=1774143
[rhbz#1794062]: https://bugzilla.redhat.com/show_bug.cgi?id=1794062
[rhbz#1851335]: https://bugzilla.redhat.com/show_bug.cgi?id=1851335
[rhbz#1856397]: https://bugzilla.redhat.com/show_bug.cgi?id=1856397
[rhbz#1869399]: https://bugzilla.redhat.com/show_bug.cgi?id=1869399
[rhbz#1885841]: https://bugzilla.redhat.com/show_bug.cgi?id=1885841
[rhbz#1917286]: https://bugzilla.redhat.com/show_bug.cgi?id=1917286


## [0.10.7] - 2020-09-30

### Added
- Support for multiple sets of resource and operation defaults, including
  support for rules ([rhbz#1222691], [rhbz#1817547], [rhbz#1862966],
  [rhbz#1867516], [rhbz#1869399])
- Support for "demote" value of resource operation's "on-fail" option
  ([rhbz#1843079])
- Support for 'number' type in rules ([rhbz#1869399])
- It is possible to set custom (promotable) clone id in `pcs resource create`
  and `pcs resource clone/promotable` commands ([rhbz#1741056])

### Fixed
- Prevent removing non-empty tag by removing tagged resource group or clone
  ([rhbz#1857295])
- Clarify documentation for 'resource move' and 'resource ban' commands with
  regards to the 'lifetime' option.
- Allow moving both promoted and demoted promotable clone resources
  ([rhbz#1875301])

### Deprecated
- `pcs resource [op] defaults <name>=<value>...` commands are deprecated now.
  Use `pcs resource [op] defaults update <name>=<value>...` if you only manage
  one set of defaults, or `pcs resource [op] defaults set` if you manage
  several sets of defaults. ([rhbz#1817547])

[rhbz#1222691]: https://bugzilla.redhat.com/show_bug.cgi?id=1222691
[rhbz#1741056]: https://bugzilla.redhat.com/show_bug.cgi?id=1741056
[rhbz#1817547]: https://bugzilla.redhat.com/show_bug.cgi?id=1817547
[rhbz#1843079]: https://bugzilla.redhat.com/show_bug.cgi?id=1843079
[rhbz#1857295]: https://bugzilla.redhat.com/show_bug.cgi?id=1857295
[rhbz#1862966]: https://bugzilla.redhat.com/show_bug.cgi?id=1862966
[rhbz#1867516]: https://bugzilla.redhat.com/show_bug.cgi?id=1867516
[rhbz#1869399]: https://bugzilla.redhat.com/show_bug.cgi?id=1869399
[rhbz#1875301]: https://bugzilla.redhat.com/show_bug.cgi?id=1875301


## [0.10.6] - 2020-06-11

### Security
- Web UI sends HTTP headers: Content-Security-Policy, X-Frame-Options and
  X-Xss-Protection

### Added
- When creating a cluster, verify the cluster name does not prevent mounting
  GFS2 volumes ([rhbz#1782553])
- An option to run 'pcs cluster setup' in a local mode (do not connect to any
  nodes, save corosync.conf to a specified file) ([rhbz#1839637])
- Support for pacemaker tags. Pcs provides commands for creating and removing
  tags, adding and/or removing IDs to/from tags, and listing current tag
  configuration.  ([rhbz#1684676])
- Support for tag ids in commands resource enable/disable/manage/unmanage
  ([rhbz#1684676])
- `pcs resource [safe-]disable --simulate` has a new option `--brief` to print
  only a list of affected resources ([rhbz#1833114])

### Fixed
- Keep autogenerated IDs of set constraints reasonably short ([rhbz#1387358],
  [rhbz#1824206])
- Pcs is now compatible with Ruby 2.7 and Python 3.8. To achieve this, it newly
  depends on python3-distro package.
- `pcs status` works on remote nodes again (broken since pcs-0.10.4)
  ([rhbz#1830552])
- Fixed inability to create colocation constraint from web ui ([rhbz#1832973])
- Actions going through pcsd no longer time out after 30s (broken since
  pcs-0.10.5) ([rhbz#1833506])

[rhbz#1387358]: https://bugzilla.redhat.com/show_bug.cgi?id=1387358
[rhbz#1684676]: https://bugzilla.redhat.com/show_bug.cgi?id=1684676
[rhbz#1782553]: https://bugzilla.redhat.com/show_bug.cgi?id=1782553
[rhbz#1824206]: https://bugzilla.redhat.com/show_bug.cgi?id=1824206
[rhbz#1830552]: https://bugzilla.redhat.com/show_bug.cgi?id=1830552
[rhbz#1832973]: https://bugzilla.redhat.com/show_bug.cgi?id=1832973
[rhbz#1833114]: https://bugzilla.redhat.com/show_bug.cgi?id=1833114
[rhbz#1833506]: https://bugzilla.redhat.com/show_bug.cgi?id=1833506
[rhbz#1839637]: https://bugzilla.redhat.com/show_bug.cgi?id=1839637


## [0.10.5] - 2020-03-18

### Added
- It is possible to configure a disaster-recovery site and display its status
  ([rhbz#1676431])

### Fixed
- Error messages in cases when cluster is not set up ([rhbz#1743731])
- Improved documentation of configuring links in the 'pcs cluster setup' command
- Safe-disabling clones and groups does not fail any more due to their inner
  resources get stopped ([rhbz#1781303])
- Booth documentation clarified ([ghissue#231])
- Detection of fence history support ([rhbz#1793574])
- Fix documentation and flags regarding bundled/cloned/grouped resources for
  `pcs (resource | stonith) (cleanup | refresh)` ([rhbz#1805082])
- Improved ACL documentation ([rhbz#1722970])
- Added missing Strict-Transport-Security headers to redirects ([rhbz#1810017])
- Improved pcsd daemon performance ([rhbz#1783106])

[ghissue#231]: https://github.com/ClusterLabs/pcs/issues/231
[rhbz#1676431]: https://bugzilla.redhat.com/show_bug.cgi?id=1676431
[rhbz#1722970]: https://bugzilla.redhat.com/show_bug.cgi?id=1722970
[rhbz#1743731]: https://bugzilla.redhat.com/show_bug.cgi?id=1743731
[rhbz#1781303]: https://bugzilla.redhat.com/show_bug.cgi?id=1781303
[rhbz#1783106]: https://bugzilla.redhat.com/show_bug.cgi?id=1783106
[rhbz#1793574]: https://bugzilla.redhat.com/show_bug.cgi?id=1793574
[rhbz#1805082]: https://bugzilla.redhat.com/show_bug.cgi?id=1805082
[rhbz#1810017]: https://bugzilla.redhat.com/show_bug.cgi?id=1810017


## [0.10.4] - 2019-11-28

### Added
- New section in pcs man page summarizing changes in pcs-0.10. Commands removed
  or changed in pcs-0.10 print errors poiting to that section. ([rhbz#1728890])
- `pcs resource disable` can show effects of disabling resources and prevent
  disabling resources if any other resources would be affected ([rhbz#1631519])
- `pcs resource relations` command shows relations between resources such as
  ordering constraints, ordering set constraints and relations defined by
  resource hierarchy ([rhbz#1631514])

### Changed
- Expired location constraints are now hidden by default when listing
  constraints in any way. Using `--all` will list and denote them with
  `(expired)`. All expired rules are then marked the same way. ([rhbz#1442116])

### Fixed
- All node names and scores are validated when running `pcs constraint location
  avoids/prefers` before writing configuration to cib ([rhbz#1673835])
- Fixed crash when an invalid port is given in an address to the
  `pcs host auth` command ([rhbz#1698763])
- Command `pcs cluster verify` suggests `--full` option instead of `-V` option
  which is not recognized by pcs ([rhbz#1712347])
- It is now possible to authenticate remote clusters in web UI even if the local
  cluster is not authenticated ([rhbz#1743735])
- Documentation of `pcs constraint colocation add` ([rhbz#1734361])
- Empty constraint option are not allowed in `pcs constraint order` and `pcs
  constraint colocation add` commands ([rhbz#1734361])
- More fixes for the case when PATH environment variable is not set
- Fixed crashes and other issues when UTF-8 characters are present in the
  corosync.conf file ([rhbz#1741586])

[rhbz#1442116]: https://bugzilla.redhat.com/show_bug.cgi?id=1442116
[rhbz#1631514]: https://bugzilla.redhat.com/show_bug.cgi?id=1631514
[rhbz#1631519]: https://bugzilla.redhat.com/show_bug.cgi?id=1631519
[rhbz#1673835]: https://bugzilla.redhat.com/show_bug.cgi?id=1673835
[rhbz#1698763]: https://bugzilla.redhat.com/show_bug.cgi?id=1698763
[rhbz#1712347]: https://bugzilla.redhat.com/show_bug.cgi?id=1712347
[rhbz#1728890]: https://bugzilla.redhat.com/show_bug.cgi?id=1728890
[rhbz#1734361]: https://bugzilla.redhat.com/show_bug.cgi?id=1734361
[rhbz#1741586]: https://bugzilla.redhat.com/show_bug.cgi?id=1741586
[rhbz#1743735]: https://bugzilla.redhat.com/show_bug.cgi?id=1743735


## [0.10.3] - 2019-08-23

### Fixed
- Fixed crashes in the `pcs host auth` command ([rhbz#1676957])
- Fixed id conflict with current bundle configuration in
  `pcs resource bundle reset` ([rhbz#1657166])
- Options starting with - and -- are no longer ignored for non-root users
  (broken since pcs-0.10.2) ([rhbz#1725183])
- Fixed crashes when pcs is configured that no rubygems are bundled in pcs
  package ([ghissue#208])
- Standby nodes running resources are listed separately in `pcs status nodes`
- Parsing arguments in the `pcs constraint order` and `pcs constraint colocation
  add` commands has been improved, errors which were previously silent are now
  reported ([rhbz#1734361])
- Fixed shebang correction in Makefile ([ghissue#206])
- Generate 256 bytes long corosync authkey, longer keys are not supported when
  FIPS is enabled ([rhbz#1740218])

### Changed
- Command `pcs resource bundle reset` no longer accepts the container type
  ([rhbz#1657166])

[ghissue#206]: https://github.com/ClusterLabs/pcs/issues/206
[ghissue#208]: https://github.com/ClusterLabs/pcs/issues/208
[rhbz#1657166]: https://bugzilla.redhat.com/show_bug.cgi?id=1657166
[rhbz#1676957]: https://bugzilla.redhat.com/show_bug.cgi?id=1676957
[rhbz#1725183]: https://bugzilla.redhat.com/show_bug.cgi?id=1725183
[rhbz#1734361]: https://bugzilla.redhat.com/show_bug.cgi?id=1734361
[rhbz#1740218]: https://bugzilla.redhat.com/show_bug.cgi?id=1740218


## [0.10.2] - 2019-06-12

### Added
- Command `pcs config checkpoint diff` for displaying differences between two
  specified checkpoints ([rhbz#1655055])
- Support for resource instance attributes uniqueness check according to
  resource agent metadata ([rhbz#1665404])
- Command `pcs resource bundle reset` for a bundle configuration resetting
  ([rhbz#1657166])
- `pcs cluster setup` now checks if nodes' addresses match value of `ip_version`
  ([rhbz#1667053])
- Support for sbd option SBD\_TIMEOUT\_ACTION ([rhbz#1664828])
- Support for clearing expired moves and bans of resources ([rhbz#1625386])
- Commands for adding, changing and removing corosync links ([rhbz#1667058])

### Fixed
- Corosync config file parser updated and made more strict to match changes in
  corosync
- Allow non-root users to read quorum status (commands `pcs status corosync`,
  `pcs status quorum`, `pcs quorum device status`, `pcs quorum status`)
  ([rhbz#1653316])
- Removed command `pcs resource show` dropped from usage and man page
  ([rhbz#1656953])
- Put proper link options' names to corosync.conf ([rhbz#1659051])
- Fixed issuses in configuring links in the 'create cluster' form in web UI
  ([rhbz#1664057])
- Pcs no longer removes empty `meta_attributes`, `instance_attributes` and other
  nvsets and similar elements from CIB. Such behavior was causing problems when
  pacemaker ACLs were in effect, leading to inability of pushing modified CIBs
  to pacemaker. ([rhbz#1659144])
- `ipv4-6` and `ipv6-4` are now valid values of `ip_version` in cluster setup
  ([rhbz#1667040])
- Crash when using unsupported options in commands `pcs status` and
  `pcs config` ([rhbz#1668422])
- `pcs resource group add` now fails gracefully instead of dumping an invalid
  CIB when a group ID is already occupied by a non-resource element
  ([rhbz#1668223])
- pcs no longer spawns unnecessary processes for reading known hosts
  ([rhbz#1676945])
- Lower load caused by periodical config files syncing in pcsd by making it
  sync less frequently ([rhbz#1676957])
- Improve logging of periodical config files syncing in pcsd
- Knet link option `ip_version` has been removed, it was never supported by
  corosync. Transport option `ip_version` is still in place. ([rhbz#1674005])
- Several bugs in linklist validation in `pcs cluster setup` ([rhbz#1667090])
- Fixed a typo in documentation (regardles -> regardless) ([rhbz#1660702])
- Fixed pcsd crashes when non-ASCII characters are present in systemd journal
- Pcs works even when PATH environment variable is not set ([rhbz#1673825])
- Fixed several "Unknown report" error messages
- Pcsd SSL certificates are no longer synced across cluster nodes when creating
  new cluster or adding new node to an existing cluster. To enable the syncing,
  set `PCSD_SSL_CERT_SYNC_ENABLED` to `true` in pcsd config. ([rhbz#1673822])
- Pcs now reports missing node names in corosync.conf instead of failing
  silently
- Fixed an issue where some pcs commands could not connect to cluster nodes
  over IPv6
- Fixed cluster setup problem in web UI when full domain names are used
  ([rhbz#1687965])
- Fixed inability to setup cluster in web UI when knet links are not specified
  ([rhbz#1687562])
- `--force` works correctly in `pcs quorum unblock` (broken since pcs-0.10.1)
- Removed `3des` from allowed knet crypto ciphers since it is actually not
  supported by corosync
- Improved validation of corosync options and their values ([rhbz#1679196],
  [rhbz#1679197])

### Changed
- Do not check whether watchdog is defined as an absolute path when enabling
  SBD. This check is not needed anymore as we are validating watchdog against
  list provided by SBD itself.

### Deprecated
- Command `pcs resource show`, removed in pcs-0.10.1, has been readded as
  deprecated to ease transition to its replacements. It will be removed again in
  future. [rhbz#1661059]

[rhbz#1625386]: https://bugzilla.redhat.com/show_bug.cgi?id=1625386
[rhbz#1653316]: https://bugzilla.redhat.com/show_bug.cgi?id=1653316
[rhbz#1655055]: https://bugzilla.redhat.com/show_bug.cgi?id=1655055
[rhbz#1656953]: https://bugzilla.redhat.com/show_bug.cgi?id=1656953
[rhbz#1657166]: https://bugzilla.redhat.com/show_bug.cgi?id=1657166
[rhbz#1659051]: https://bugzilla.redhat.com/show_bug.cgi?id=1659051
[rhbz#1659144]: https://bugzilla.redhat.com/show_bug.cgi?id=1659144
[rhbz#1660702]: https://bugzilla.redhat.com/show_bug.cgi?id=1660702
[rhbz#1661059]: https://bugzilla.redhat.com/show_bug.cgi?id=1661059
[rhbz#1664057]: https://bugzilla.redhat.com/show_bug.cgi?id=1664057
[rhbz#1664828]: https://bugzilla.redhat.com/show_bug.cgi?id=1664828
[rhbz#1665404]: https://bugzilla.redhat.com/show_bug.cgi?id=1665404
[rhbz#1667040]: https://bugzilla.redhat.com/show_bug.cgi?id=1667040
[rhbz#1667053]: https://bugzilla.redhat.com/show_bug.cgi?id=1667053
[rhbz#1667058]: https://bugzilla.redhat.com/show_bug.cgi?id=1667058
[rhbz#1667090]: https://bugzilla.redhat.com/show_bug.cgi?id=1667090
[rhbz#1668223]: https://bugzilla.redhat.com/show_bug.cgi?id=1668223
[rhbz#1668422]: https://bugzilla.redhat.com/show_bug.cgi?id=1668422
[rhbz#1673822]: https://bugzilla.redhat.com/show_bug.cgi?id=1673822
[rhbz#1673825]: https://bugzilla.redhat.com/show_bug.cgi?id=1673825
[rhbz#1674005]: https://bugzilla.redhat.com/show_bug.cgi?id=1674005
[rhbz#1676945]: https://bugzilla.redhat.com/show_bug.cgi?id=1676945
[rhbz#1676957]: https://bugzilla.redhat.com/show_bug.cgi?id=1676957
[rhbz#1679196]: https://bugzilla.redhat.com/show_bug.cgi?id=1679196
[rhbz#1679197]: https://bugzilla.redhat.com/show_bug.cgi?id=1679197
[rhbz#1687562]: https://bugzilla.redhat.com/show_bug.cgi?id=1687562
[rhbz#1687965]: https://bugzilla.redhat.com/show_bug.cgi?id=1687965


## [0.10.1] - 2018-11-23

### Removed
- Pcs-0.10 removes support for CMAN, Corosync 1.x, Corosync 2.x and Pacemaker
  1.x based clusters. For managing those clusters use pcs-0.9.x.
- Pcs-0.10 requires Python 3.6 and Ruby 2.2, support for older Python and Ruby
  versions has been removed.
- `pcs resource failcount reset` command has been removed as `pcs resource
  cleanup` is doing exactly the same job. ([rhbz#1427273])
- Deprecated commands `pcs cluster remote-node add | remove` have been removed
  as they were replaced with `pcs cluster node add-guest | remove-guest`
- Ability to create master resources has been removed as they are deprecated in
  Pacemaker 2.x ([rhbz#1542288])
  - Instead of `pcs resource create ... master` use `pcs resource create ...
    promotable` or `pcs resource create ... clone promotable=true`
  - Instead of `pcs resource master` use `pcs resource promotable` or `pcs
    resource clone ... promotable=true`
- Deprecated --clone option from `pcs resource create` command
- Ability to manage node attributes with `pcs property set|unset|show` commands
  (using `--node` option). The same functionality is still available using
  `pcs node attribute` command.
- Undocumented version of the `pcs constraint colocation add` command, its
  syntax was `pcs constraint colocation add <source resource id> <target
  resource id> [score] [options]`
- Deprecated commands `pcs cluster standby | unstandby`, use
  `pcs node standby | unstandby` instead
- Deprecated command `pcs cluster quorum unblock` which was replaced by
  `pcs quorum unblock`
- Subcommand `pcs status groups` as it was not showing a cluster status but
  cluster configuration. The same functionality is still available using command
  `pcs resource group list`
- Undocumented command `pcs acl target`, use `pcs acl user` instead

### Added
- Validation for an unaccessible resource inside a bundle ([rhbz#1462248])
- Options to filter failures by an operation and its interval in `pcs resource
  cleanup` and `pcs resource failcount show` commands ([rhbz#1427273])
- Commands for listing and testing watchdog devices ([rhbz#1578891])
- Commands for creating promotable clone resources `pcs resource promotable`
  and `pcs resource create ... promotable` ([rhbz#1542288])
- `pcs resource update` and `pcs resource meta` commands change master
  resources to promotable clone resources because master resources are
  deprecated in Pacemaker 2.x ([rhbz#1542288])
- Support for the `promoted-max` bundle option replacing the `masters` option
  in Pacemaker 2.x ([rhbz#1542288])
- Support for OP\_NO\_RENEGOTIATION option when OpenSSL supports it (even with
  Python 3.6) ([rhbz#1566430])
- Support for container types `rkt` and `podman` into bundle commands
  ([rhbz#1619620])
- Support for promotable clone resources in pcsd and web UI ([rhbz#1542288])
- Obsoleting parameters of resource and fence agents are now supported and
  preferred over deprecated parameters ([rhbz#1436217])
- `pcs status` now shows failed and pending fencing actions and `pcs status
  --full` shows the whole fencing history. Pacemaker supporting fencing history
  is required. ([rhbz#1615891])
- `pcs stonith history` commands for displaying, synchronizing and cleaning up
  fencing history. Pacemaker supporting fencing history is required.
  ([rhbz#1620190])
- Validation of node existence in a cluster when creating location constraints
  ([rhbz#1553718])
- Command `pcs client local-auth` for authentication of pcs client against local
  pcsd. This is required when a non-root user wants to execute a command which
  requires root permissions (e.g. `pcs cluster start`). ([rhbz#1554302])
- Command `pcs resource group list` which has the same functionality as removed
  command `pcs resource show --groups`

### Fixed
- Fixed encoding of the CIB\_user\_groups cookie in communication between nodes.
- `pcs cluster cib-push diff-against=` does not consider an empty diff as
  an error ([ghpull#166])
- `pcs cluster cib-push diff-against=` exits gracefully with an error message if
  crm\_feature\_set < 3.0.9 ([rhbz#1488044])
- `pcs resource update` does not create an empty meta\_attributes element any
  more ([rhbz#1568353])
- `pcs resource debug-*` commands provide debug messages even with
  pacemaker-1.1.18 and newer ([rhbz#1574898])
- Improve `pcs quorum device add` usage and man page ([rhbz#1476862])
- Removing resources using web UI when the operation takes longer than expected
  ([rhbz#1579911])
- Removing a cluster node no longer leaves the node in the CIB and therefore
  cluster status even if the removal is run on the node which is being removed
  ([rhbz#1595829])
- Possible race condition causing an HTTP 408 error when sending larger files
  via pcs ([rhbz#1600169])
- Configuring QDevice works even if NSS with the new db format (cert9.db,
  key4.db, pkcs11.txt) is used ([rhbz#1596721])
- Options starting with '-' and '--' are no longer accepted by commands for
  which those options have no effect ([rhbz#1533866])
- When a user makes an error in a pcs command, usage for that specific command
  is printed instead of printing the whole usage
- Show more user friendly error message when testing watchdog device and
  multiple devices are present ([rhbz#1578891])
- Do not distinguish between supported and unsupported watchdog devices as SBD
  cannot reliably provide such information ([rhbz#1578891])
- `pcs config` no longer crashes when `crm_mon` prints something to stderr
  ([rhbz#1578955])
- `pcs resource bundle update` cmd for bundles which are using unsupported
  container backend ([rhbz#1619620])
- Do not crash if unable to load SSL certificate or key, log errors and exit
  gracefully instead ([rhbz#1638852])
- Fixed several issues in parsing `pcs constraint colocation add` command.
- All `remove` subcommands now have `delete` aliases and vice versa. Previously,
  only some of them did and it was mostly undocumented.
- The `pcs acl role delete` command no longer deletes ACL users and groups with
  no ACL roles assigned

### Changed
- Authentication has been overhauled ([rhbz#1549535]):
  - The `pcs cluster auth` command only authenticates nodes in a local cluster
    and does not accept a node list.
  - The new command for authentication is `pcs host auth`. It allows to specify
    host names, addresses and pcsd ports.
  - Previously, running `pcs cluster auth A B C` caused A, B and C to be all
    authenticated against each other. Now, `pcs host auth A B C` makes the
    local host authenticated against A, B and C. This allows better control of
    what is authenticated against what.
  - The `pcs pcsd clear-auth` command has been replaced by `pcs pcsd deauth` and
    `pcs host deauth` commands. The new commands allows to deauthenticate
    a single host / token as well as all hosts / tokens.
  - These changes are not backward compatible. You should use the `pcs host
    auth` command to re-authenticate your hosts.
- The `pcs cluster setup` command has been overhauled ([rhbz#1158816],
  [rhbz#1183103]):
  - It works with Corosync 3.x only and supports knet as well as udp/udpu.
  - Node names are now supported.
  - The number of Corosync options configurable by the command has been
    significantly increased.
  - The syntax of the command has been completely changed to accommodate the
    changes and new features.
  - Corosync encryption is enabled by default when knet is used ([rhbz#1648942])
- The `pcs cluster node add` command has been overhauled ([rhbz#1158816],
  [rhbz#1183103])
  - It works with Corosync 3.x only and supports knet as well as udp/udpu.
  - Node names are now supported.
  - The syntax of the command has been changed to accommodate new features and
    to be consistent with other pcs commands.
- The `pcs cluster node remove` has been overhauled ([rhbz#1158816],
  [rhbz#1595829]):
  - It works with Corosync 3.x only and supports knet as well as udp/udpu.
  - It is now possible to remove more than one node at once.
  - Removing a cluster node no longer leaves the node in the CIB and therefore
    cluster status even if the removal is run on the node which is being removed
- Node names are fully supported now and are no longer coupled with node
  addresses. It is possible to set up a cluster where Corosync communicates
  over different addresses than pcs/pcsd. ([rhbz#1158816], [rhbz#1183103])
- Node names are now required while node addresses are optional in the `pcs
  cluster node add-guest` and `pcs cluster node add-remove` commands.
  Previously, it was the other way around.
- Web UI has been updated following changes in authentication and support for
  Corosync 3.x ([rhbz#1158816], [rhbz#1183103], [rhbz#1549535])
- Commands related to resource failures have been overhauled to support changes
  in pacemaker. Failures are now tracked per resource operations on top of
  resources and nodes. ([rhbz#1427273], [rhbz#1588667])
- `--watchdog` and `--device` options of `pcs stonith sbd enable` and `pcs
  stonith sbd device setup` commands have been replaced with `watchdog` and
  `device` options respectively
- Update pacemaker daemon names to match changes in pacemaker-2.0
  ([rhbz#1573344])
- Watchdog devices are validated against a list provided by sbd
  ([rhbz#1578891])
- Resource operation option `requires` is no longer accepted to match changes
  in pacemaker-2.0 ([rhbz#1605185])
- Update pacemaker exit codes to match changes in pacemaker-2.0 ([rhbz#1536121])
- `pcs cluster cib-upgrade` no longer exits with an error if the CIB schema is
  already the latest available (this has been changed in pacemaker-2.0)
- Pcs now configures corosync to put timestamps in its log ([rhbz#1615420])
- Option `-V` has been replaced with `--full` and a CIB file can be specified
  only using option `-f` in `pcs cluster verify`
- Master resources are now called promotable clone resources to match changes
  in pacemaker-2.0 ([rhbz#1542288])
- Key size of default pcsd self-generated certificates increased from 2048b to
  3072b ([rhbz#1638852])
- pcsd.service now depends on network-online.target ([rhbz#1640477])
- Split command `pcs resource [show]` into two new commands:
    - `pcs resource [status]` - same as `pcs resource [show]`
    - `pcs resource config` - same as `pcs resource [show] --full` or resource
      id specified instead of --full
  Respective changes have been made to `pcs stonith [show]` command.
- Previously, `pcs cluster sync` synchronized only corosync configuration
  across all nodes configured in the cluster. This command will be changed in
  the future to sync all cluster configuration. New subcommand `pcs cluster
  sync corosync` has been introduced to sync only corosync configuration. For
  now, both commands have the same functionality.

### Security
- CVE-2018-1086: Debug parameter removal bypass, allowing information disclosure
  ([rhbz#1557366])
- CVE-2018-1079: Privilege escalation via authorized user malicious REST call
  ([rhbz#1550243])

### Deprecated
- The `masters` bundle option is obsoleted by the `promoted-max` option
  in Pacemaker 2.x and therefore in pcs ([rhbz#1542288])
- `pcs cluster uidgid rm`, use `pcs cluster uidgid delete` or `pcs cluster
  uidgid remove` instead

[ghpull#166]: https://github.com/ClusterLabs/pcs/pull/166
[rhbz#1158816]: https://bugzilla.redhat.com/show_bug.cgi?id=1158816
[rhbz#1183103]: https://bugzilla.redhat.com/show_bug.cgi?id=1183103
[rhbz#1427273]: https://bugzilla.redhat.com/show_bug.cgi?id=1427273
[rhbz#1436217]: https://bugzilla.redhat.com/show_bug.cgi?id=1436217
[rhbz#1462248]: https://bugzilla.redhat.com/show_bug.cgi?id=1462248
[rhbz#1476862]: https://bugzilla.redhat.com/show_bug.cgi?id=1476862
[rhbz#1488044]: https://bugzilla.redhat.com/show_bug.cgi?id=1488044
[rhbz#1533866]: https://bugzilla.redhat.com/show_bug.cgi?id=1533866
[rhbz#1536121]: https://bugzilla.redhat.com/show_bug.cgi?id=1536121
[rhbz#1542288]: https://bugzilla.redhat.com/show_bug.cgi?id=1542288
[rhbz#1549535]: https://bugzilla.redhat.com/show_bug.cgi?id=1549535
[rhbz#1550243]: https://bugzilla.redhat.com/show_bug.cgi?id=1550243
[rhbz#1553718]: https://bugzilla.redhat.com/show_bug.cgi?id=1553718
[rhbz#1554302]: https://bugzilla.redhat.com/show_bug.cgi?id=1554302
[rhbz#1557366]: https://bugzilla.redhat.com/show_bug.cgi?id=1557366
[rhbz#1566430]: https://bugzilla.redhat.com/show_bug.cgi?id=1566430
[rhbz#1568353]: https://bugzilla.redhat.com/show_bug.cgi?id=1568353
[rhbz#1573344]: https://bugzilla.redhat.com/show_bug.cgi?id=1573344
[rhbz#1574898]: https://bugzilla.redhat.com/show_bug.cgi?id=1574898
[rhbz#1578891]: https://bugzilla.redhat.com/show_bug.cgi?id=1578891
[rhbz#1578955]: https://bugzilla.redhat.com/show_bug.cgi?id=1578955
[rhbz#1579911]: https://bugzilla.redhat.com/show_bug.cgi?id=1579911
[rhbz#1588667]: https://bugzilla.redhat.com/show_bug.cgi?id=1588667
[rhbz#1595829]: https://bugzilla.redhat.com/show_bug.cgi?id=1595829
[rhbz#1596721]: https://bugzilla.redhat.com/show_bug.cgi?id=1596721
[rhbz#1600169]: https://bugzilla.redhat.com/show_bug.cgi?id=1600169
[rhbz#1605185]: https://bugzilla.redhat.com/show_bug.cgi?id=1605185
[rhbz#1615420]: https://bugzilla.redhat.com/show_bug.cgi?id=1615420
[rhbz#1615891]: https://bugzilla.redhat.com/show_bug.cgi?id=1615891
[rhbz#1619620]: https://bugzilla.redhat.com/show_bug.cgi?id=1619620
[rhbz#1620190]: https://bugzilla.redhat.com/show_bug.cgi?id=1620190
[rhbz#1638852]: https://bugzilla.redhat.com/show_bug.cgi?id=1638852
[rhbz#1640477]: https://bugzilla.redhat.com/show_bug.cgi?id=1640477
[rhbz#1648942]: https://bugzilla.redhat.com/show_bug.cgi?id=1648942


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
