#!/bin/bash
set -ex

cluster_user=hacluster
cluster_user_password=password

echo "${cluster_user_password}" | passwd --stdin $cluster_user;

pcs --help
pcs --version
pcs host auth localhost --debug -u ${cluster_user} -p ${cluster_user_password}
if pidof systemd | grep "\b1\b"; then
    # this command requires full system with proper init process
    pcs cluster setup cluster-name localhost --debug
fi
