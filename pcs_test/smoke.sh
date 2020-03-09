#!/bin/bash
set -ex

cluster_user=hacluster
cluster_user_password=qa57Jk27eP

echo "${cluster_user_password}" | passwd --stdin $cluster_user;

pcs --help
pcs --version
pcs host auth localhost --debug -u ${cluster_user} -p ${cluster_user_password}
if pidof systemd | grep "\b1\b"; then
    # this command requires full system with proper init process
    pcs cluster setup cluster-name localhost --debug
fi
# make sure that pcs_internal entrypoint works properly from pcsd
token=$(python3 -c "import json; print(json.load(open('/var/lib/pcsd/known-hosts'))['known_hosts']['localhost']['token']);")
curl -kb "token=${token}" https://localhost:2224/remote/cluster_status_plaintext -d 'data_json={}' > output.json
cat output.json; echo ""
python3 -c "import json; import sys; json.load(open('output.json'))['status'] == 'exception' and (sys.exit(1))";
