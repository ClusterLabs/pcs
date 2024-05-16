## PCS - Pacemaker/Corosync Configuration System

Pcs is a Corosync and Pacemaker configuration tool. It permits users to easily
view, modify and create Pacemaker based clusters. Pcs contains pcsd, a pcs
daemon, which operates as a remote server for pcs.

---

### Pcs Branches

* main
  * This is where pcs-0.12 lives.
  * Clusters running Pacemaker 3.x on top of Corosync 3.x are supported.
  * The main development happens here.
* pcs-0.11
  * Clusters running Pacemaker 2.1 on top of Corosync 3.x are supported.
  * This branch is in maintenance mode - bugs are being fixed but only a subset
    of new features lands here.
* pcs-0.10
  * Clusters running Pacemaker 2.0 on top of Corosync 3.x are supported.
  * Pacemaker 2.1 is supported, if it is compiled with `--enable-compat-2.0`
    option.
  * This branch is no longer maintained.
* pcs-0.9
  * Clusters running Pacemaker 1.x on top of Corosync 2.x or Corosync 1.x with
    CMAN are supported.
  * This branch is no longer maintained.

---

### Dependencies

These are the runtime dependencies of pcs and pcsd:
* python 3.12+
* python3-cryptography
* python3-dateutil 2.7.0+
* python3-lxml
* python3-pycurl
* python3-setuptools
* python3-setuptools\_scm
* python3-pyparsing 3.0.0+
* python3-tornado 6.1.0+
* [dacite](https://github.com/konradhalas/dacite)
* ruby 3.3.0+
* killall (package psmisc)
* corosync 3.x
* pacemaker 3.x

---

### Installation from Source

Apart from the dependencies listed above, these are also required for
installation:

* python development files (packages python3-devel, python3-setuptools,
  python3-setuptools\_scm, python3-wheel)
* ruby development files (package ruby-devel)
* rubygems
* rubygem bundler (package rubygem-bundler or ruby-bundler or bundler)
* autoconf, automake
* gcc
* gcc-c++
* FFI development files (package libffi-devel or libffi-dev)
* printf (package coreutils)
* redhat-rpm-config (if you are using Fedora)
* wget (to download bundled libraries)

During the installation, all required rubygems are automatically downloaded and
compiled.

To install pcs and pcsd run the following in terminal:
```shell
./autogen.sh
./configure
# alternatively './configure --enable-local-build' can be used to also download
# missing dependencies
make
make install
```

If you are using GNU/Linux with systemd, it is now time to:
```shell
systemctl daemon-reload
```

Start pcsd and make it start on boot:
```shell
systemctl start pcsd
systemctl enable pcsd
```

---

### Packages

Currently this is built into Fedora, RHEL, CentOS and Debian and its
derivates. It is likely that other Linux distributions also contain pcs
packages.
* [Fedora package git repositories](https://src.fedoraproject.org/rpms/pcs)
* [Current Fedora .spec](https://src.fedoraproject.org/rpms/pcs/blob/rawhide/f/pcs.spec)
* [Debian-HA project home page](https://wiki.debian.org/Debian-HA)

---

### Quick Start

* **Authenticate cluster nodes**

  Set the same password for the `hacluster` user on all nodes.
  ```shell
  passwd hacluster
  ```

  To authenticate the nodes, run the following command on one of the nodes
  (replacing node1, node2, node3 with a list of nodes in your future cluster).
  Specify all your cluster nodes in the command. Make sure pcsd is running on
  all nodes.
  ```shell
  pcs host auth node1 node2 node3 -u hacluster
  ```

* **Create a cluster**

  To create a cluster run the following command on one node (replacing
  cluster\_name with a name of your cluster and node1, node2, node3 with a list
  of nodes in the cluster). `--start` and `--enable` will start your cluster
  and configure the nodes to start the cluster on boot respectively.
  ```shell
  pcs cluster setup cluster_name node1 node2 node3 --start --enable
  ```

* **Check the cluster status**

   After a few moments the cluster should startup and you can get the status of
   the cluster.
   ```shell
   pcs status
   ```

* **Add cluster resources**

   After this you can add stonith agents and resources:
   ```shell
   pcs stonith create --help
   ```
   and
   ```shell
   pcs resource create --help
   ```

---

### Further Documentation

[ClusterLabs website](https://clusterlabs.org) is an excellent place to learn
more about Pacemaker clusters.
* [ClusterLabs quick start](https://clusterlabs.org/quickstart.html)
* [Clusters from Scratch](https://clusterlabs.org/pacemaker/doc/2.1/Clusters_from_Scratch/html/)
* [ClusterLabs documentation page](https://clusterlabs.org/pacemaker/doc/)

---

### Inquiries
If you have any bug reports or feature requests please feel free to open a
github issue on the pcs project.

Alternatively you can use ClusterLabs
[users mailinglist](https://lists.clusterlabs.org/mailman/listinfo/users)
which is also a great place to ask Pacemaker clusters related questions.
