from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys
import os
import os.path
import re
import datetime
from io import BytesIO
import tarfile
import json
from xml.dom.minidom import parse
import logging
import pwd
import grp
import time
import platform

try:
    import clufter.facts
    import clufter.format_manager
    import clufter.filter_manager
    import clufter.command_manager
    no_clufter = False
except ImportError:
    no_clufter = True

from pcs import (
    cluster,
    constraint,
    prop,
    quorum,
    resource,
    settings,
    status,
    stonith,
    usage,
    utils,
    alert,
)
from pcs.lib.errors import LibraryError
from pcs.lib.commands import quorum as lib_quorum
import pcs.cli.constraint_colocation.command as colocation_command
import pcs.cli.constraint_order.command as order_command
import pcs.cli.constraint_ticket.command as ticket_command
from pcs.cli.common.console_report import indent


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
    elif sub_cmd == "export":
        if not argv:
            usage.config(["export"])
            sys.exit(1)
        elif argv[0] == "pcs-commands":
            config_export_pcs_commands(argv[1:])
        elif argv[0] == "pcs-commands-verbose":
            config_export_pcs_commands(argv[1:], True)
        else:
            usage.config(["export"])
            sys.exit(1)
    else:
        usage.config()
        sys.exit(1)

def config_show(argv):
    print("Cluster Name: %s" % utils.getClusterName())
    status.nodes_status(["config"])
    print()
    config_show_cib()
    if (
        utils.hasCorosyncConf()
        and
        (
            utils.is_rhel6()
            or
            (not utils.usefile and "--corosync_conf" not in utils.pcs_options)
        )
    ):
        # with corosync 1 and cman, uid gid is part of cluster.conf file
        # with corosync 2, uid gid is in a separate directory
        cluster.cluster_uidgid([], True)
    if (
        "--corosync_conf" in utils.pcs_options
        or
        (not utils.is_rhel6() and utils.hasCorosyncConf())
    ):
        print()
        print("Quorum:")
        try:
            config = lib_quorum.get_config(utils.get_lib_env())
            print("\n".join(indent(quorum.quorum_config_to_str(config))))
        except LibraryError as e:
            utils.process_library_reports(e.args)

def config_show_cib():
    print("Resources:")
    utils.pcs_options["--all"] = 1
    utils.pcs_options["--full"] = 1
    resource.resource_show([])
    print()
    print("Stonith Devices:")
    resource.resource_show([], True)
    print("Fencing Levels:")
    stonith.stonith_level_show()
    print()

    lib = utils.get_library_wrapper()
    constraint.location_show([])
    modificators = utils.get_modificators()
    order_command.show(lib, [], modificators)
    colocation_command.show(lib, [], modificators)
    ticket_command.show(lib, [], modificators)

    print()
    alert.print_alert_config(lib, [], modificators)

    print()
    del utils.pcs_options["--all"]
    print("Resources Defaults:")
    resource.show_defaults("rsc_defaults", indent=" ")
    print("Operations Defaults:")
    resource.show_defaults("op_defaults", indent=" ")
    print()
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
        ok, message = utils.write_file(
            outfile_name, tar_data, permissions=0o600, binary=True
        )
        if not ok:
            utils.err(message)
    else:
        # in python3 stdout accepts str so we need to use buffer
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write(tar_data)
        else:
            sys.stdout.write(tar_data)

def config_backup_local():
    file_list = config_backup_path_list()
    tar_data = BytesIO()

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
        # in python3 stdin returns str so we need to use buffer
        if hasattr(sys.stdin, "buffer"):
            infile_obj = BytesIO(sys.stdin.buffer.read())
        else:
            infile_obj = BytesIO(sys.stdin.read())

    if os.getuid() == 0:
        if "--local" in utils.pcs_options:
            config_restore_local(infile_name, infile_obj)
        else:
            config_restore_remote(infile_name, infile_obj)
    else:
        new_argv = ['config', 'restore']
        new_stdin = None
        if '--local' in utils.pcs_options:
            new_argv.append('--local')
        if infile_name:
            new_argv.append(os.path.abspath(infile_name))
        else:
            new_stdin = infile_obj.read()
        err_msgs, exitcode, std_out, std_err = utils.call_local_pcsd(
            new_argv, True, new_stdin
        )
        if err_msgs:
            for msg in err_msgs:
                utils.err(msg, False)
            sys.exit(1)
        print(std_out)
        sys.stderr.write(std_err)
        sys.exit(exitcode)

def config_restore_remote(infile_name, infile_obj):
    extracted = {
        "version.txt": "",
        "corosync.conf": "",
        "cluster.conf": "",
    }
    try:
        tarball = tarfile.open(infile_name, "r|*", infile_obj)
        while True:
            # next(tarball) does not work in python2.6
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
        extracted["cluster.conf" if utils.is_rhel6() else "corosync.conf"].decode("utf-8")
    )
    if not node_list:
        utils.err("no nodes found in the tarball")

    err_msgs = []
    for node in node_list:
        try:
            retval, output = utils.checkStatus(node)
            if retval != 0:
                err_msgs.append(output)
                continue
            status = json.loads(output)
            if (
                status["corosync"]
                or
                status["pacemaker"]
                or
                status["cman"]
                or
                # not supported by older pcsd, do not fail if not present
                status.get("pacemaker_remote", False)
            ):
                err_msgs.append(
                    "Cluster is currently running on node %s. You need to stop "
                        "the cluster in order to restore the configuration."
                    % node
                )
                continue
        except (ValueError, NameError, LookupError):
            err_msgs.append("unable to determine status of the node %s" % node)
    if err_msgs:
        for msg in err_msgs:
            utils.err(msg, False)
        sys.exit(1)

    # Temporarily disable config files syncing thread in pcsd so it will not
    # rewrite restored files. 10 minutes should be enough time to restore.
    # If node returns HTTP 404 it does not support config syncing at all.
    for node in node_list:
        retval, output = utils.pauseConfigSyncing(node, 10 * 60)
        if not (retval == 0 or "(HTTP error: 404)" in output):
            utils.err(output)

    if infile_obj:
        infile_obj.seek(0)
        tarball_data = infile_obj.read()
    else:
        with open(infile_name, "rb") as tarball:
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
        status.is_service_running("cman")
        or
        status.is_service_running("corosync")
        or
        status.is_service_running("pacemaker")
        or
        status.is_service_running("pacemaker_remote")
    ):
        utils.err(
            "Cluster is currently running on this node. You need to stop "
                "the cluster in order to restore the configuration."
        )

    file_list = config_backup_path_list(with_uid_gid=True)
    tarball_file_list = []
    version = None
    try:
        tarball = tarfile.open(infile_name, "r|*", infile_obj)
        while True:
            # next(tarball) does not work in python2.6
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
            # next(tarball) does not work in python2.6
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
            path_extract = os.path.dirname(extract_info["path"])
            tarball.extractall(path_extract, [tar_member_info])
            path_full = os.path.join(path_extract, tar_member_info.name)
            file_attrs = extract_info["attrs"]
            os.chmod(path_full, file_attrs["mode"])
            os.chown(path_full, file_attrs["uid"], file_attrs["gid"])
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
    corosync_attrs = {
        "mtime": int(time.time()),
        "mode": 0o644,
        "uname": "root",
        "gname": "root",
        "uid": 0,
        "gid": 0,
    }
    cib_attrs = {
        "mtime": int(time.time()),
        "mode": 0o600,
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
            "attrs": dict(cib_attrs),
        },
    }
    if rhel6:
        file_list["cluster.conf"] = {
            "path": settings.cluster_conf_file,
            "required": True,
            "attrs": dict(corosync_attrs),
        }
    else:
        file_list["corosync.conf"] = {
            "path": settings.corosync_conf_file,
            "required": True,
            "attrs": dict(corosync_attrs),
        }
        file_list["uidgid.d"] = {
            "path": settings.corosync_uidgid_dir.rstrip("/"),
            "required": False,
            "attrs": dict(corosync_attrs),
        }
        file_list["pcs_settings.conf"] = {
            "path": settings.pcsd_settings_conf_location,
            "required": False,
            "attrs": {
                "mtime": int(time.time()),
                "mode": 0o644,
                "uname": "root",
                "gname": "root",
                "uid": 0,
                "gid": 0,
            },
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
    ver = version if version is not None else str(config_backup_version())
    return utils.tar_add_file_data(tarball, ver.encode("utf-8"), "version.txt")

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
        print("No checkpoints available")
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
    output_format = "cluster.conf" if utils.is_rhel6() else "corosync.conf"
    dist = None
    invalid_args = False
    for arg in argv:
        if "=" in arg:
            name, value = arg.split("=", 1)
            if name == "input":
                cluster_conf = value
            elif name == "output":
                dry_run_output = value
            elif name == "output-format":
                if value in (
                    "cluster.conf", "corosync.conf",
                    "pcs-commands", "pcs-commands-verbose",
                ):
                    output_format = value
                else:
                    invalid_args = True
            elif name == "dist":
                dist = value
            else:
                invalid_args = True
        else:
            invalid_args = True
    if (
        output_format not in ("pcs-commands", "pcs-commands-verbose")
        and
        (dry_run_output and not dry_run_output.endswith(".tar.bz2"))
    ):
        dry_run_output += ".tar.bz2"
    if invalid_args or not dry_run_output:
        usage.config(["import-cman"])
        sys.exit(1)
    debug = "--debug" in utils.pcs_options
    force = "--force" in utils.pcs_options
    interactive = "--interactive" in utils.pcs_options

    if dist is not None:
        if output_format == "cluster.conf":
            if not clufter.facts.cluster_pcs_flatiron("linux", dist.split(",")):
                utils.err("dist does not match output-format")
        elif output_format == "corosync.conf":
            if not clufter.facts.cluster_pcs_needle("linux", dist.split(",")):
                utils.err("dist does not match output-format")
    elif (
        (output_format == "cluster.conf" and utils.is_rhel6())
        or
        (output_format == "corosync.conf" and not utils.is_rhel6())
    ):
        dist = ",".join(platform.linux_distribution(full_distribution_name=0))
    elif output_format == "cluster.conf":
        dist = "redhat,6.7,Santiago"
    elif output_format == "corosync.conf":
        dist = "redhat,7.1,Maipo"
    else:
        # for output-format=pcs-command[-verbose]
        dist = ",".join(platform.linux_distribution(full_distribution_name=0))

    clufter_args = {
        "input": str(cluster_conf),
        "cib": {"passin": "bytestring"},
        "nocheck": force,
        "batch": True,
        "sys": "linux",
        "dist": dist,
        # Make it work on RHEL6 as well for sure
        "color": "always" if sys.stdout.isatty() else "never"
    }
    if interactive:
        if "EDITOR" not in os.environ:
            utils.err("$EDITOR environment variable is not set")
        clufter_args["batch"] = False
        clufter_args["editor"] = os.environ["EDITOR"]
    if debug:
        logging.getLogger("clufter").setLevel(logging.DEBUG)
    if output_format == "cluster.conf":
        clufter_args["ccs_pcmk"] = {"passin": "bytestring"}
        cmd_name = "ccs2pcs-flatiron"
    elif output_format == "corosync.conf":
        clufter_args["coro"] = {"passin": "struct"}
        cmd_name = "ccs2pcs-needle"
    elif output_format in ("pcs-commands", "pcs-commands-verbose"):
        clufter_args["output"] = {"passin": "bytestring"}
        clufter_args["start_wait"] = "60"
        clufter_args["tmp_cib"] = "tmp-cib.xml"
        clufter_args["force"] = force
        clufter_args["text_width"] = "80"
        clufter_args["silent"] = True
        clufter_args["noguidance"] = True
        if output_format == "pcs-commands-verbose":
            clufter_args["text_width"] = "-1"
            clufter_args["silent"] = False
            clufter_args["noguidance"] = False
        if clufter.facts.cluster_pcs_flatiron("linux", dist.split(",")):
            cmd_name = "ccs2pcscmd-flatiron"
        elif clufter.facts.cluster_pcs_needle("linux", dist.split(",")):
            cmd_name = "ccs2pcscmd-needle"
        else:
            utils.err(
                "unrecognized dist, try something recognized"
                + " (e. g. rhel,6.8 or redhat,7.3 or debian,7 or ubuntu,trusty)"
            )
    clufter_args_obj = type(str("ClufterOptions"), (object, ), clufter_args)

    # run convertor
    run_clufter(
        cmd_name, clufter_args_obj, debug, force,
            "Error: unable to import cluster configuration"
    )

    # save commands
    if output_format in ("pcs-commands", "pcs-commands-verbose"):
        ok, message = utils.write_file(
            dry_run_output,
            clufter_args_obj.output["passout"]
        )
        if not ok:
            utils.err(message)
        return

    # put new config files into tarball
    file_list = config_backup_path_list(
        force_rhel6=(output_format == "cluster.conf")
    )
    for file_item in file_list.values():
        file_item["attrs"]["uname"] = "root"
        file_item["attrs"]["gname"] = "root"
        file_item["attrs"]["uid"] = 0
        file_item["attrs"]["gid"] = 0
        file_item["attrs"]["mode"] = 0o600
    tar_data = BytesIO()
    try:
        tarball = tarfile.open(fileobj=tar_data, mode="w|bz2")
        config_backup_add_version_to_tarball(tarball)
        utils.tar_add_file_data(
            tarball,
            clufter_args_obj.cib["passout"].encode("utf-8"),
            "cib.xml",
            **file_list["cib.xml"]["attrs"]
        )
        if output_format == "cluster.conf":
            utils.tar_add_file_data(
                tarball,
                clufter_args_obj.ccs_pcmk["passout"].encode("utf-8"),
                "cluster.conf",
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
                tarball,
                corosync_conf_data.encode("utf-8"),
                "corosync.conf",
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
                    tarball,
                    uidgid_data.encode("utf-8"),
                    "uidgid.d/" + filename,
                    **file_list["uidgid.d"]["attrs"]
                )
        tarball.close()
    except (tarfile.TarError, EnvironmentError) as e:
        utils.err("unable to create tarball: %s" % e)
    tar_data.seek(0)

    #save tarball / remote restore
    if dry_run_output:
        ok, message = utils.write_file(
            dry_run_output, tar_data.read(), permissions=0o600, binary=True
        )
        if not ok:
            utils.err(message)
    else:
        config_restore_remote(None, tar_data)
    tar_data.close()

def config_export_pcs_commands(argv, verbose=False):
    if no_clufter:
        utils.err(
            "Unable to perform export due to missing python-clufter package"
        )

    # parse options
    debug = "--debug" in utils.pcs_options
    force = "--force" in utils.pcs_options
    interactive = "--interactive" in utils.pcs_options
    invalid_args = False
    output_file = None
    dist = None
    for arg in argv:
        if "=" in arg:
            name, value = arg.split("=", 1)
            if name == "output":
                output_file = value
            elif name == "dist":
                dist = value
            else:
                invalid_args = True
        else:
            invalid_args = True
    # check options
    if invalid_args:
        usage.config(["export", "pcs-commands"])
        sys.exit(1)
    # complete optional options
    if dist is None:
        dist = ",".join(platform.linux_distribution(full_distribution_name=0))

    # prepare convertor options
    clufter_args = {
        "nocheck": force,
        "batch": True,
        "sys": "linux",
        "dist": dist,
        # Make it work on RHEL6 as well for sure
        "color": "always" if sys.stdout.isatty() else "never",
        "coro": settings.corosync_conf_file,
        "ccs": settings.cluster_conf_file,
        "start_wait": "60",
        "tmp_cib": "tmp-cib.xml",
        "force": force,
        "text_width": "80",
        "silent": True,
        "noguidance": True,
    }
    if output_file:
        clufter_args["output"] = {"passin": "bytestring"}
    else:
        clufter_args["output"] = "-"
    if interactive:
        if "EDITOR" not in os.environ:
            utils.err("$EDITOR environment variable is not set")
        clufter_args["batch"] = False
        clufter_args["editor"] = os.environ["EDITOR"]
    if debug:
        logging.getLogger("clufter").setLevel(logging.DEBUG)
    if utils.usefile:
        clufter_args["cib"] = os.path.abspath(utils.filename)
    else:
        clufter_args["cib"] = ("bytestring", utils.get_cib())
    if verbose:
        clufter_args["text_width"] = "-1"
        clufter_args["silent"] = False
        clufter_args["noguidance"] = False
    clufter_args_obj = type(str("ClufterOptions"), (object, ), clufter_args)
    cmd_name = "pcs2pcscmd-flatiron" if utils.is_rhel6() else "pcs2pcscmd-needle"

    # run convertor
    run_clufter(
        cmd_name, clufter_args_obj, debug, force,
        "Error: unable to export cluster configuration"
    )

    # save commands if not printed to stdout by clufter
    if output_file:
        ok, message = utils.write_file(
            output_file,
            clufter_args_obj.output["passout"]
        )
        if not ok:
            utils.err(message)

def run_clufter(cmd_name, cmd_args, debug, force, err_prefix):
    try:
        result = None
        cmd_manager = clufter.command_manager.CommandManager.init_lookup(
            cmd_name
        )
        result = cmd_manager.commands[cmd_name](cmd_args)
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
            err_prefix
            + (": %s" % error_message if error_message else "")
            + hints_string
            + "\n"
        )
        sys.exit(1 if result is None else result)

