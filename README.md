## PCS - Pacemaker/Corosync configuration system


### Quick Start
***


- **PCS Installation from Source**

   Run the following in terminal:

   ```shell
   # tar -xzvf pcs-0.9.143.tar.gz
   # cd pcs-0.9.143
   # make install
   ```

   This will install pcs into `/usr/sbin/pcs`.

<br />
- **Create and Start a Basic Cluster**

   To create a cluster run the following commands on all nodes (replacing node1, node2, node3 with a list of nodes in the cluster).

   ```shell
   # pcs cluster setup --local --name cluster_name node1 node2 node3
   ```

   Then run the following command on all nodes:

   ```shell
   # pcs cluster start
   ```

<br />
- **Check the Cluster Status**

   After a few moments the cluster should startup and you can get the status of the cluster

   ```shell
   # pcs status
   ```

<br />
- **Add Cluster Resources**

   After this you can add resources and stonith agents:

   ```shell
   # pcs resource help
   ```

   and

   ```shell
   # pcs stonith help
   ```

<br />
- **PCSD Installation from Source**

   You can also install pcsd which operates as a GUI and remote server for pcs. pcsd may also be necessary in order to follow the guides on the clusterlabs.org website.

   To install pcsd run the following commands from the root of your pcs directory. (You must have the ruby bundler gem installed, rubygem-bundler in Fedora, and development packages installed)

   ```shell
   # cd pcsd ; make get_gems ; cd ..
   # make install_pcsd
   ```

   If you are using GNU/Linux its now time to:

   ```shell
   # systemctl daemon-reload
   ```

<br />
### Packages
***

   Currently this is built into Fedora (other distributions to follow).  You can see the current Fedora .spec in the fedora package git repositories here: http://pkgs.fedoraproject.org/cgit/pcs.git/

   Current Fedora 23 .spec:
   http://pkgs.fedoraproject.org/cgit/pcs.git/tree/pcs.spec?h=f23

<br />
### Inquiries
***

If you have any questions or concerns please feel free to email cfeist@redhat.com or open a github issue on the pcs project.
