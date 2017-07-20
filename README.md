## PCS - Pacemaker/Corosync Configuration System

Pcs is a Corosync and Pacemaker configuration tool. It permits users to
easily view, modify and create Pacemaker based clusters. Pcs contains pcsd, a
pcs daemon, which operates as a remote server for pcs and provides a web UI.

---

### Installation from Source

These are the runtime dependencies of pcs and pcsd:
* python 2.6+
* python-lxml / python3-lxml
* python-pycurl / python3-pycurl
* python-setuptools / python3-setuptools
* ruby 2.0.0+
* killall (package psmisc)
* openssl
* corosync
* pacemaker

It is also recommended to have these:
* python-clufter / python3-clufter
* liberation fonts (package liberation-sans-fonts or fonts-liberation or
  fonts-liberation2)
* overpass fonts (package overpass-fonts)

If you plan to manage Corosync 1.x based clusters, you will also need:
* cman
* ccs

It is however highly recommended for new clusters to use Corosync 2.x.

Apart from the dependencies listed above, these are also required for
installation:

* python development files (package python-devel / python3-devel)
* ruby development files (package ruby-devel)
* rubygems
* rubygem bundler (package rubygem-bundler or ruby-bundler or bundler)
* gcc
* gcc-c++
* PAM development files (package pam-devel or libpam0g-dev)
* FFI development files (package libffi-devel or libffi-dev)
* fontconfig
* printf (package coreutils)
* redhat-rpm-config if you are using Fedora

During the installation, all required rubygems are automatically downloaded and
compiled.

To install pcs and pcsd run the following in terminal:
```shell
# tar -xzvf pcs-0.9.159.tar.gz
# cd pcs-0.9.159
# make install
# make install_pcsd
```

If you are using GNU/Linux with systemd, it is now time to:
```shell
# systemctl daemon-reload
```

Start pcsd and make it start on boot:
```shell
# systemctl start pcsd
# systemctl enable pcsd
```

---

### Packages

Currently this is built into Fedora, RHEL and its clones and Debian and its
clones.
* [Fedora package git repositories](http://pkgs.fedoraproject.org/cgit/rpms/pcs.git/)
* [Current Fedora .spec](http://pkgs.fedoraproject.org/cgit/rpms/pcs.git/tree/pcs.spec)
* [Debian-HA project home page](http://debian-ha.alioth.debian.org/)

---

### Quick Start

* **Authenticate cluster nodes**

  Set the same password for the `hacluster` user on all nodes.
  ```shell
  # passwd hacluster
  ```

  To authenticate the nodes, run the following command on one of the nodes
  (replacing node1, node2, node3 with a list of nodes in your future cluster).
  Specify all your cluster nodes in the command. Make sure pcsd is running on
  all nodes.
  ```shell
  # pcs cluster auth node1 node2 node3 -u hacluster
  ```

* **Create a cluster**

  To create a cluster run the following command on one node (replacing
  cluster\_name with a name of your cluster and node1, node2, node3 with a list
  of nodes in the cluster). `--start` and `--enable` will start your cluster
  and configure the nodes to start the cluster on boot respectively.
  ```shell
  # pcs cluster setup --name cluster_name node1 node2 node3 --start --enable
  ```

* **Check the cluster status**

   After a few moments the cluster should startup and you can get the status of
   the cluster.
   ```shell
   # pcs status
   ```

* **Add cluster resources**

   After this you can add stonith agents and resources:
   ```shell
   # pcs -h stonith create
   ```
   and
   ```shell
   # pcs -h resource create
   ```

---

### Accessing the Web UI

Apart from command line interface you can use web user interface to view and
configure your cluster. To access the web UI open a browser to the following
URL (replace nodename with an address of your node):
```
https://nodename:2224
```
Login as the `hacluster` user.

---

### Further Documentation

[ClusterLabs website](http://clusterlabs.org) is an excellent place to learn
more about Pacemaker clusters.
* [ClusterLabs quick start](http://clusterlabs.org/quickstart.html)
* [Clusters from Scratch](http://clusterlabs.org/doc/en-US/Pacemaker/1.1-pcs/html/Clusters_from_Scratch/index.html)
* [ClusterLabs documentation page](http://clusterlabs.org/doc/)

---

### Inquiries
If you have any bug reports or feature requests please feel free to open a
github issue on the pcs project.

Alternatively you can use ClusterLabs
[users mailinglist](http://oss.clusterlabs.org/mailman/listinfo/users)
which is also a great place to ask Pacemaker clusters related questions.
