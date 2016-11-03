# Change Log

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
- Fixed occasional crashes / failures when using locale other than en_US.UTF8
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
