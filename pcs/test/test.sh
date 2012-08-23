rm test.xml
cp blank.xml test.xml
echo "Testing Resources..."
../pcs.py -f test.xml resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s
../pcs.py -f test.xml resource create DummyRes ocf:heartbeat:Dummy fake="my fake"
../pcs.py -f test.xml resource create ClusterIP2 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s
../pcs.py -f test.xml resource create ClusterIP3 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s
../pcs.py -f test.xml resource create ClusterIP3 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s
../pcs.py -f test.xml resource create ClusterIP4 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s
../pcs.py -f test.xml resource list
../pcs.py -f test.xml resource delete ClusterIP3
../pcs.py -f test.xml resource list
../pcs.py -f test.xml resource create ClusterIP32 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s
../pcs.py -f test.xml resource list
../pcs.py -f test.xml resource list ClusterIP2
../pcs.py -f test.xml resource update ClusterIP2 ip=192.168.0.100
../pcs.py -f test.xml resource add_operation ClusterIP2 monitor interval="31s"
../pcs.py -f test.xml resource add_operation ClusterIP2 monitor interval="32s"
../pcs.py -f test.xml resource remove_operation ClusterIP2 monitor interval="32s"
../pcs.py -f test.xml resource list ClusterIP2
../pcs.py -f test.xml resource group add MyGroup ClusterIP2 ClusterIP32 ClusterIP4
../pcs.py -f test.xml resource list
../pcs.py -f test.xml resource group remove_resource MyGroup ClusterIP4
../pcs.py -f test.xml resource list
../pcs.py -f test.xml resource group add MyGroup2 ClusterIP4
../pcs.py -f test.xml resource list
../pcs.py -f test.xml resource group remove_resource MyGroup2 ClusterIP4
../pcs.py -f test.xml resource list
../pcs.py -f test.xml resource clone create ClusterIP4 globally-unique=false
../pcs.py -f test.xml resource list
../pcs.py -f test.xml resource list ClusterIP4-clone
../pcs.py -f test.xml resource clone update ClusterIP4 globally-unique=true
../pcs.py -f test.xml resource list ClusterIP4-clone
../pcs.py -f test.xml resource create ClusterIP5 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s
../pcs.py -f test.xml resource create ClusterIP6 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s
../pcs.py -f test.xml resource master create MyMaster ClusterIP5 master-max=1
../pcs.py -f test.xml resource master update MyMaster master-max=2
../pcs.py -f test.xml resource master create MyMaster2 ClusterIP6
../pcs.py -f test.xml resource list
../pcs.py -f test.xml resource list MyMaster
../pcs.py -f test.xml resource master remove MyMaster2
../pcs.py -f test.xml resource list
diff test.xml final.xml


