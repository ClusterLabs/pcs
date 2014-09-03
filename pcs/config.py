import sys
import os
import cStringIO
import tarfile
import json

import settings
import utils
import cluster
import constraint
import prop
import resource
import status
import stonith
import usage

def config_cmd(argv):
    if len(argv) == 0:
        config_show(argv)
        return

    sub_cmd = argv.pop(0)
    if sub_cmd == "help":
        usage.config(argv)
    elif sub_cmd == "show":
        config_show(argv)
    elif sub_cmd == "backup":
        config_backup(argv)
    elif sub_cmd == "restore":
        config_restore(argv)
    else:
        usage.config()
        sys.exit(1)

def config_show(argv):
    print "Cluster Name: %s" % utils.getClusterName()
    status.nodes_status(["config"])
    print ""
    print ""
    print "Resources: "
    utils.pcs_options["--all"] = 1
    utils.pcs_options["--full"] = 1
    resource.resource_show([])
    print ""
    print "Stonith Devices: "
    resource.resource_show([], True)
    print "Fencing Levels: "
    print ""
    stonith.stonith_level_show()
    constraint.location_show([])
    constraint.order_show([])
    constraint.colocation_show([])
    print ""
    del utils.pcs_options["--all"]
    prop.list_property([])
    cluster.cluster_uidgid([], True)

def config_backup(argv):
    if len(argv) > 1:
        usage.config(["backup"])
        sys.exit(1)

    outfile_name = None
    if argv:
        outfile_name = argv[0]
        if not outfile_name.endswith(".tar.bz2"):
            outfile_name += ".tar.bz2"

    tar_data = config_backup_local()
    if outfile_name:
        ok, message = utils.write_file(outfile_name, tar_data)
        if not ok:
            utils.err(message)
    else:
        sys.stdout.write(tar_data)

def config_backup_local():
    file_list = config_backup_path_list()
    tar_data = cStringIO.StringIO()

    try:
        tarball = tarfile.open(fileobj=tar_data, mode="w|bz2")
        config_backup_add_version_to_tarball(tarball)
        for tar_path, path_info in file_list.items():
            if (
                not os.path.exists(path_info["path"])
                and
                not path_info["required"]
            ):
                continue
            tarball.add(path_info["path"], tar_path)
        tarball.close()
    except (tarfile.TarError, EnvironmentError) as e:
        utils.err("unable to create tarball: %s" % e)

    tar = tar_data.getvalue()
    tar_data.close()
    return tar

def config_restore(argv):
    if len(argv) > 1:
        usage.config(["restore"])
        sys.exit(1)

    infile_name = infile_obj = None
    if argv:
        infile_name = argv[0]
    if not infile_name:
        infile_obj = cStringIO.StringIO(sys.stdin.read())

    if "--local" in utils.pcs_options:
        config_restore_local(infile_name, infile_obj)
    else:
        config_restore_remote(infile_name, infile_obj)

def config_restore_remote(infile_name, infile_obj):
    extracted = {
        "version.txt": "",
        "corosync.conf": "",
        "cluster.conf": "",
    }
    try:
        tarball = tarfile.open(infile_name, "r|*", infile_obj)
        while True:
            tar_member_info = tarball.next()
            if tar_member_info is None:
                break
            if tar_member_info.name in extracted:
                tar_member = tarball.extractfile(tar_member_info)
                extracted[tar_member_info.name] = tar_member.read()
                tar_member.close()
        tarball.close()
    except (tarfile.TarError, EnvironmentError) as e:
        utils.err("unable to read the tarball: %s" % e)

    config_backup_check_version(extracted["version.txt"])

    node_list = utils.getNodesFromCorosyncConf(
        extracted["cluster.conf" if utils.is_rhel6() else "corosync.conf"]
    )
    if not node_list:
        utils.err("no nodes found in the tarball")

    for node in node_list:
        try:
            retval, output = utils.checkStatus(node)
            if retval != 0:
                utils.err("unable to determine status of the node %s" % node)
            status = json.loads(output)
            if status["corosync"] or status["pacemaker"] or status["cman"]:
                utils.err(
                    "Cluster is currently running on node %s. You need to stop "
                        "the cluster in order to restore the configuration."
                    % node
                )
        except (ValueError, NameError):
            utils.err("unable to determine status of the node %s" % node)

    if infile_obj:
        infile_obj.seek(0)
        tarball_data = infile_obj.read()
    else:
        with open(infile_name, "r") as tarball:
            tarball_data = tarball.read()

    error_list = []
    for node in node_list:
        retval, error = utils.restoreConfig(node, tarball_data)
        if retval != 0:
            error_list.append(error)
    if error_list:
        utils.err("unable to restore all nodes\n" + "\n".join(error_list))

def config_restore_local(infile_name, infile_obj):
    if (
        status.is_cman_running()
        or
        status.is_corosyc_running()
        or
        status.is_pacemaker_running()
    ):
        utils.err(
            "Cluster is currently running on this node. You need to stop "
                "the cluster in order to restore the configuration."
        )

    file_list = config_backup_path_list()
    tarball_file_list = []
    version = None
    try:
        tarball = tarfile.open(infile_name, "r|*", infile_obj)
        while True:
            tar_member_info = tarball.next()
            if tar_member_info is None:
                break
            if tar_member_info.name == "version.txt":
                version_data = tarball.extractfile(tar_member_info)
                version = version_data.read()
                version_data.close()
                continue
            tarball_file_list.append(tar_member_info.name)
        tarball.close()

        required_file_list = [
            tar_path
            for tar_path, path_info in file_list.items()
                if path_info["required"]
        ]
        missing = set(required_file_list) - set(tarball_file_list)
        if missing:
            utils.err(
                "unable to restore the cluster, missing files in backup: %s"
                % ", ".join(missing)
            )

        config_backup_check_version(version)

        if infile_obj:
            infile_obj.seek(0)
        tarball = tarfile.open(infile_name, "r|*", infile_obj)
        while True:
            tar_member_info = tarball.next()
            if tar_member_info is None:
                break
            extract_info = None
            path = tar_member_info.name
            while path:
                if path in file_list:
                    extract_info = file_list[path]
                    break
                path = os.path.dirname(path)
            if not extract_info:
                continue
            tarball.extractall(
                os.path.dirname(extract_info["path"]),
                [tar_member_info]
            )
        tarball.close()
    except (tarfile.TarError, EnvironmentError) as e:
        utils.err("unable to restore the cluster: %s" % e)

    try:
        sig_path = os.path.join(settings.cib_dir, "cib.xml.sig")
        if os.path.exists(sig_path):
            os.remove(sig_path)
    except EnvironmentError as e:
        utils.err("unable to remove %s: %s" % (sig_path, e))

def config_backup_path_list():
    file_list = {
        "cib.xml": {
            "path": os.path.join(settings.cib_dir, "cib.xml"),
            "required": True,
        },
    }
    if utils.is_rhel6():
        file_list["cluster.conf"] = {
            "path": settings.cluster_conf_file,
            "required": True,
        }
    else:
        file_list["corosync.conf"] = {
            "path": settings.corosync_conf_file,
            "required": True,
        }
        file_list["uidgid.d"] = {
            "path": settings.corosync_uidgid_dir.rstrip("/"),
            "required": False,
        }
    return file_list

def config_backup_check_version(version):
    try:
        version_number = int(version)
        supported_version = config_backup_version()
        if version_number > supported_version:
            utils.err(
                "Unsupported version of the backup, "
                    "supported version is %d, backup version is %d"
                % (supported_version, version_number)
            )
        if version_number < supported_version:
            print(
                "Warning: restoring from the backup version %d, "
                    "current supported version is %s"
                % (version_number, supported_version)
            )
    except TypeError:
        utils.err("Cannot determine version of the backup")

def config_backup_add_version_to_tarball(tarball, version=None):
    version = version if version is not None else str(config_backup_version())
    version_info = tarfile.TarInfo("version.txt")
    version_info.size = len(version)
    version_info.type = tarfile.REGTYPE
    tarball.addfile(version_info, cStringIO.StringIO(version))

def config_backup_version():
    return 1

