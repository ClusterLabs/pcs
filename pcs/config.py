import sys
import os
import re
import datetime
import cStringIO
import tarfile
import json
from xml.dom.minidom import parse
import logging
import pwd
import grp
import time

logging.basicConfig() # clufter needs logging set before imported
try:
    import clufter.format_manager
    import clufter.filter_manager
    import clufter.command_manager
    no_clufter = False
except ImportError:
    no_clufter = True

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
    elif sub_cmd == "checkpoint":
        if not argv:
            config_checkpoint_list()
        elif argv[0] == "view":
            config_checkpoint_view(argv[1:])
        elif argv[0] == "restore":
            config_checkpoint_restore(argv[1:])
        else:
            usage.config(["checkpoint"])
            sys.exit(1)
    elif sub_cmd == "import-cman":
        config_import_cman(argv)
    else:
        usage.config()
        sys.exit(1)

def config_show(argv):
    print "Cluster Name: %s" % utils.getClusterName()
    status.nodes_status(["config"])
    print ""
    print ""
    config_show_cib()
    cluster.cluster_uidgid([], True)

def config_show_cib():
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
    print "Resources Defaults:"
    resource.show_defaults("rsc_defaults", indent=" ")
    print "Operations Defaults:"
    resource.show_defaults("op_defaults", indent=" ")
    print
    prop.list_property([])

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

def config_backup_path_list(with_uid_gid=False, force_rhel6=None):
    rhel6 = utils.is_rhel6() if force_rhel6 is None else force_rhel6
    root_attrs = {
        "mtime": int(time.time()),
        "mode": 0644,
        "uname": "root",
        "gname": "root",
        "uid": 0,
        "gid": 0,
    }
    cib_attrs = {
        "mtime": int(time.time()),
        "mode": 0600,
        "uname": settings.pacemaker_uname,
        "gname": settings.pacemaker_gname,
    }
    if with_uid_gid:
        try:
            cib_attrs["uid"] = pwd.getpwnam(cib_attrs["uname"]).pw_uid
        except KeyError:
            utils.err(
                "Unable to determine uid of user '%s'" % cib_attrs["uname"]
            )
        try:
            cib_attrs["gid"] = grp.getgrnam(cib_attrs["gname"]).gr_gid
        except KeyError:
            utils.err(
                "Unable to determine gid of group '%s'" % cib_attrs["gname"]
            )

    file_list = {
        "cib.xml": {
            "path": os.path.join(settings.cib_dir, "cib.xml"),
            "required": True,
            "attrs": cib_attrs,
        },
    }
    if rhel6:
        file_list["cluster.conf"] = {
            "path": settings.cluster_conf_file,
            "required": True,
            "attrs": root_attrs,
        }
    else:
        file_list["corosync.conf"] = {
            "path": settings.corosync_conf_file,
            "required": True,
            "attrs": root_attrs,
        }
        file_list["uidgid.d"] = {
            "path": settings.corosync_uidgid_dir.rstrip("/"),
            "required": False,
            "attrs": root_attrs,
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
    return utils.tar_add_file_data(
        tarball,
        version if version is not None else str(config_backup_version()),
        "version.txt"
    )

def config_backup_version():
    return 1

def config_checkpoint_list():
    try:
        file_list = os.listdir(settings.cib_dir)
    except OSError as e:
        utils.err("unable to list checkpoints: %s" % e)
    cib_list = []
    cib_name_re = re.compile("^cib-(\d+)\.raw$")
    for filename in file_list:
        match = cib_name_re.match(filename)
        if not match:
            continue
        file_path = os.path.join(settings.cib_dir, filename)
        try:
            if os.path.isfile(file_path):
                cib_list.append(
                    (float(os.path.getmtime(file_path)), match.group(1))
                )
        except OSError:
            pass
    cib_list.sort()
    if not cib_list:
        print "No checkpoints available"
        return
    for cib_info in cib_list:
        print(
            "checkpoint %s: date %s"
            % (cib_info[1], datetime.datetime.fromtimestamp(round(cib_info[0])))
        )

def config_checkpoint_view(argv):
    if len(argv) != 1:
        usage.config(["checkpoint", "view"])
        sys.exit(1)

    utils.usefile = True
    utils.filename = os.path.join(settings.cib_dir, "cib-%s.raw" % argv[0])
    if not os.path.isfile(utils.filename):
        utils.err("unable to read the checkpoint")
    config_show_cib()

def config_checkpoint_restore(argv):
    if len(argv) != 1:
        usage.config(["checkpoint", "restore"])
        sys.exit(1)

    cib_path = os.path.join(settings.cib_dir, "cib-%s.raw" % argv[0])
    try:
        snapshot_dom = parse(cib_path)
    except Exception as e:
        utils.err("unable to read the checkpoint: %s" % e)
    utils.replace_cib_configuration(snapshot_dom)

def config_import_cman(argv):
    if no_clufter:
        utils.err("Unable to perform a CMAN cluster conversion due to missing python-clufter package")
    # prepare convertor options
    cluster_conf = settings.cluster_conf_file
    dry_run_output = None
    rhel6 = utils.is_rhel6()
    invalid_args = False
    for arg in argv:
        if "=" in arg:
            name, value = arg.split("=", 1)
            if name == "input":
                cluster_conf = value
            elif name == "output":
                dry_run_output = value
                if not dry_run_output.endswith(".tar.bz2"):
                    dry_run_output += ".tar.bz2"
            elif name == "output-format":
                if value == "corosync.conf":
                    rhel6 = False
                elif value == "cluster.conf":
                    rhel6 = True
                else:
                    invalid_args = True
            else:
                invalid_args = True
        else:
            invalid_args = True
    if invalid_args or not dry_run_output:
        usage.config(["import-cman"])
        sys.exit(1)
    debug = "--debug" in utils.pcs_options
    force = "--force" in utils.pcs_options
    interactive = "--interactive" in utils.pcs_options

    clufter_args = {
        "input": cluster_conf,
        "cib": {"passin": "bytestring"},
        "nocheck": force,
        "batch": True,
    }
    if interactive:
        if "EDITOR" not in os.environ:
            utils.err("$EDITOR environment variable is not set")
        clufter_args["batch"] = False
        clufter_args["editor"] = os.environ["EDITOR"]
    if debug:
        logging.getLogger("clufter").setLevel(logging.DEBUG)
    if rhel6:
        clufter_args["ccs_pcmk"] = {"passin": "bytestring"}
    else:
        clufter_args["coro"] = {"passin": "struct"}
    clufter_args_obj = type('ClufterOptions', (object, ), clufter_args)

    # run convertor
    try:
        cmd_name = "ccs2pcs-flatiron" if rhel6 else "ccs2pcs-needle"
        result = None
        cmd_manager = clufter.command_manager.CommandManager.init_lookup(
            cmd_name
        )
        result = cmd_manager.commands[cmd_name](clufter_args_obj)
        error_message = ""
    except Exception as e:
        error_message = str(e)
    if error_message or result != 0:
        hints = []
        hints.append("--interactive to solve the issues manually")
        if not debug:
            hints.append("--debug to get more information")
        if not force:
            hints.append("--force to override")
        hints_string = "\nTry using %s." % ", ".join(hints) if hints else ""
        sys.stderr.write(
            "Error: unable to import cluster configuration"
            + (": %s" % error_message if error_message else "")
            + hints_string
            + "\n"
        )
        sys.exit(1 if result is None else result)

    # put new config files into tarball
    file_list = config_backup_path_list(with_uid_gid=True, force_rhel6=rhel6)
    tar_data = cStringIO.StringIO()
    try:
        tarball = tarfile.open(fileobj=tar_data, mode="w|bz2")
        config_backup_add_version_to_tarball(tarball)
        utils.tar_add_file_data(
            tarball, clufter_args_obj.cib["passout"], "cib.xml",
            **file_list["cib.xml"]["attrs"]
        )
        if rhel6:
            utils.tar_add_file_data(
                tarball, clufter_args_obj.ccs_pcmk["passout"], "cluster.conf",
                **file_list["cluster.conf"]["attrs"]
            )
        else:
            # put uidgid into separate files
            fmt_simpleconfig = clufter.format_manager.FormatManager.init_lookup(
                'simpleconfig'
            ).plugins['simpleconfig']
            corosync_struct = []
            uidgid_list = []
            for section in clufter_args_obj.coro["passout"][2]:
                if section[0] == "uidgid":
                    uidgid_list.append(section[1])
                else:
                    corosync_struct.append(section)
            corosync_conf_data = fmt_simpleconfig(
                "struct", ("corosync", (), corosync_struct)
            )("bytestring")
            utils.tar_add_file_data(
                tarball, corosync_conf_data, "corosync.conf",
                **file_list["corosync.conf"]["attrs"]
            )
            for uidgid in uidgid_list:
                uid = ""
                gid = ""
                for item in uidgid:
                    if item[0] == "uid":
                        uid = item[1]
                    if item[0] == "gid":
                        gid = item[1]
                filename = utils.get_uid_gid_file_name(uid, gid)
                uidgid_data = fmt_simpleconfig(
                    "struct", ("corosync", (), [("uidgid", uidgid, None)])
                )("bytestring")
                utils.tar_add_file_data(
                    tarball, uidgid_data, "uidgid.d/" + filename,
                    **file_list["uidgid.d"]["attrs"]
                )
        tarball.close()
    except (tarfile.TarError, EnvironmentError) as e:
        utils.err("unable to create tarball: %s" % e)
    tar_data.seek(0)

    #save tarball / remote restore
    if dry_run_output:
        ok, message = utils.write_file(dry_run_output, tar_data.read())
        if not ok:
            utils.err(message)
    else:
        config_restore_remote(None, tar_data)
    tar_data.close()

