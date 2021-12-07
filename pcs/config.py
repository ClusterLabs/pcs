import sys
import os
import os.path
import re
import datetime
from io import BytesIO
import tarfile
import json
from xml.dom.minidom import parse
import pwd
import grp
import tempfile
import time
import shutil
import difflib

from pcs import (
    cluster,
    constraint,
    quorum,
    resource,
    settings,
    status,
    stonith,
    usage,
    utils,
    alert,
)
from pcs.cli.common import middleware
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.constraint import command as constraint_command
from pcs.cli.nvset import nvset_dto_list_to_lines
from pcs.cli.reports import process_library_reports
from pcs.cli.reports.output import print_to_stderr, warn
from pcs.common.reports import constraints as constraints_reports
from pcs.common.str_tools import indent
from pcs.lib.commands import quorum as lib_quorum
from pcs.lib.errors import LibraryError
from pcs.lib.node import get_existing_nodes_names

# pylint: disable=too-many-branches, too-many-locals, too-many-statements


def config_show(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file, when getting cluster name on remote node (corosync.conf
        doesn't exist)
      * --corosync_conf - corosync.conf file
    """
    modifiers.ensure_only_supported("-f", "--corosync_conf")
    if argv:
        raise CmdLineInputError()
    print("Cluster Name: %s" % utils.getClusterName())
    status.nodes_status(lib, ["config"], modifiers.get_subset("-f"))
    print()
    print("\n".join(_config_show_cib_lines(lib)))
    if (
        utils.hasCorosyncConf()
        and not modifiers.is_specified("-f")
        and not modifiers.is_specified("--corosync_conf")
    ):
        cluster.cluster_uidgid(
            lib, [], modifiers.get_subset(), silent_list=True
        )
    if modifiers.is_specified("--corosync_conf") or utils.hasCorosyncConf():
        print()
        print("Quorum:")
        try:
            config = lib_quorum.get_config(utils.get_lib_env())
            print("\n".join(indent(quorum.quorum_config_to_str(config))))
        except LibraryError as e:
            process_library_reports(e.args)


def _config_show_cib_lines(lib):
    """
    Commandline options:
      * -f - CIB file
    """
    # update of pcs_options will change output of constraint show and
    # displaying resources and operations defaults
    utils.pcs_options["--full"] = 1
    # get latest modifiers object after updating pcs_options
    modifiers = utils.get_input_modifiers()
    cib_xml = utils.get_cib()
    cib_etree = utils.get_cib_etree(cib_xml=cib_xml)
    cib_dom = utils.get_cib_dom(cib_xml=cib_xml)

    resource_lines = []
    stonith_lines = []
    for resource_el in cib_etree.find(".//resources"):
        is_stonith = (
            "class" in resource_el.attrib
            and resource_el.attrib["class"] == "stonith"
        )
        resource_el_lines = resource.resource_node_lines(resource_el)
        if is_stonith:
            stonith_lines += resource_el_lines
        else:
            resource_lines += resource_el_lines

    all_lines = []

    all_lines.append("Resources:")
    all_lines.extend(indent(resource_lines, indent_step=1))
    all_lines.append("")
    all_lines.append("Stonith Devices:")
    all_lines.extend(indent(stonith_lines, indent_step=1))
    all_lines.append("Fencing Levels:")
    levels_lines = stonith.stonith_level_config_to_str(
        lib.fencing_topology.get_config()
    )
    if levels_lines:
        all_lines.extend(indent(levels_lines, indent_step=2))

    all_lines.append("")
    constraints_element = cib_dom.getElementsByTagName("constraints")[0]
    all_lines.extend(
        constraint.location_lines(
            constraints_element,
            showDetail=True,
            show_expired=True,
            verify_expiration=False,
        )
    )
    all_lines.extend(
        constraint_command.config_cmd(
            "Ordering Constraints:",
            lib.constraint_order.config,
            constraints_reports.order_plain,
            modifiers.get_subset("-f", "--full"),
        )
    )
    all_lines.extend(
        constraint_command.config_cmd(
            "Colocation Constraints:",
            lib.constraint_colocation.config,
            constraints_reports.colocation_plain,
            modifiers.get_subset("-f", "--full"),
        )
    )
    all_lines.extend(
        constraint_command.config_cmd(
            "Ticket Constraints:",
            lib.constraint_ticket.config,
            constraints_reports.ticket_plain,
            modifiers.get_subset("-f", "--full"),
        )
    )

    all_lines.append("")
    all_lines.extend(alert.alert_config_lines(lib))

    all_lines.append("")
    all_lines.append("Resources Defaults:")
    all_lines.extend(
        indent(
            nvset_dto_list_to_lines(
                lib.cib_options.resource_defaults_config(
                    evaluate_expired=False
                ),
                with_ids=modifiers.get("--full"),
                text_if_empty="No defaults set",
            )
        )
    )
    all_lines.append("Operations Defaults:")
    all_lines.extend(
        indent(
            nvset_dto_list_to_lines(
                lib.cib_options.operation_defaults_config(
                    evaluate_expired=False
                ),
                with_ids=modifiers.get("--full"),
                text_if_empty="No defaults set",
            )
        )
    )

    all_lines.append("")
    all_lines.append("Cluster Properties:")
    properties = utils.get_set_properties()
    all_lines.extend(
        indent(
            [
                "{0}: {1}".format(prop, val)
                for prop, val in sorted(properties.items())
            ],
            indent_step=1,
        )
    )
    all_lines.append("")
    all_lines.append("Tags:")
    tags = lib.tag.config([])
    if not tags:
        all_lines.append(" No tags defined")
    tag_lines = []
    for tag in tags:
        tag_lines.append(tag["tag_id"])
        tag_lines.extend(indent(tag["idref_list"]))
    all_lines.extend(indent(tag_lines, indent_step=1))
    return all_lines


def config_backup(lib, argv, modifiers):
    """
    Options:
      * --force - overwrite file if already exists
    """
    del lib
    modifiers.ensure_only_supported("--force")
    if len(argv) > 1:
        raise CmdLineInputError()

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
        sys.stdout.buffer.write(tar_data)


def config_backup_local():
    """
    Commandline options: no options
    """
    file_list = config_backup_path_list()
    tar_data = BytesIO()

    try:
        with tarfile.open(fileobj=tar_data, mode="w|bz2") as tarball:
            config_backup_add_version_to_tarball(tarball)
            for tar_path, path_info in file_list.items():
                if (
                    not os.path.exists(path_info["path"])
                    and not path_info["required"]
                ):
                    continue
                tarball.add(path_info["path"], tar_path)
    except (tarfile.TarError, EnvironmentError) as e:
        utils.err("unable to create tarball: %s" % e)

    tar = tar_data.getvalue()
    tar_data.close()
    return tar


def config_restore(lib, argv, modifiers):
    """
    Options:
      * --local - restore config only on local node
      * --request-timeout - timeout for HTTP requests, used only if --local was
        not defined or user is not root
    """
    del lib
    modifiers.ensure_only_supported("--local", "--request-timeout")
    if len(argv) > 1:
        raise CmdLineInputError()

    infile_name = infile_obj = None
    if argv:
        infile_name = argv[0]
    if not infile_name:
        # in python3 stdin returns str so we need to use buffer
        infile_obj = BytesIO(sys.stdin.buffer.read())

    if os.getuid() == 0:
        if modifiers.get("--local"):
            config_restore_local(infile_name, infile_obj)
        else:
            config_restore_remote(infile_name, infile_obj)
    else:
        new_argv = ["config", "restore"]
        options = []
        new_stdin = None
        if modifiers.get("--local"):
            options.append("--local")
        if infile_name:
            new_argv.append(os.path.abspath(infile_name))
        else:
            new_stdin = infile_obj.read()
        err_msgs, exitcode, std_out, std_err = utils.call_local_pcsd(
            new_argv, options, new_stdin
        )
        if err_msgs:
            for msg in err_msgs:
                utils.err(msg, False)
            sys.exit(1)
        print(std_out)
        sys.stderr.write(std_err)
        sys.exit(exitcode)


def config_restore_remote(infile_name, infile_obj):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    extracted = {
        "version.txt": "",
        "corosync.conf": "",
    }
    try:
        with tarfile.open(infile_name, "r|*", infile_obj) as tarball:
            while True:
                # next(tarball) does not work in python2.6
                tar_member_info = tarball.next()
                if tar_member_info is None:
                    break
                if tar_member_info.name in extracted:
                    tar_member = tarball.extractfile(tar_member_info)
                    extracted[tar_member_info.name] = tar_member.read()
                    tar_member.close()
    except (tarfile.TarError, EnvironmentError) as e:
        utils.err("unable to read the tarball: %s" % e)

    config_backup_check_version(extracted["version.txt"])

    node_list, report_list = get_existing_nodes_names(
        utils.get_corosync_conf_facade(
            conf_text=extracted["corosync.conf"].decode("utf-8")
        )
    )
    if report_list:
        process_library_reports(report_list)
    if not node_list:
        utils.err("no nodes found in the tarball")

    err_msgs = []
    for node in node_list:
        try:
            retval, output = utils.checkStatus(node)
            if retval != 0:
                err_msgs.append(output)
                continue
            _status = json.loads(output)
            if any(
                _status["node"]["services"][service_name]["running"]
                for service_name in (
                    "corosync",
                    "pacemaker",
                    "pacemaker_remote",
                )
            ):
                err_msgs.append(
                    "Cluster is currently running on node %s. You need to stop "
                    "the cluster in order to restore the configuration." % node
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
    """
    Commandline options: no options
    """
    service_manager = utils.get_service_manager()
    if (
        service_manager.is_running("corosync")
        or service_manager.is_running("pacemaker")
        or service_manager.is_running("pacemaker_remote")
    ):
        utils.err(
            "Cluster is currently running on this node. You need to stop "
            "the cluster in order to restore the configuration."
        )

    file_list = config_backup_path_list(with_uid_gid=True)
    tarball_file_list = []
    version = None
    tmp_dir = None
    try:
        with tarfile.open(infile_name, "r|*", infile_obj) as tarball:
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
        with tarfile.open(infile_name, "r|*", infile_obj) as tarball:
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
                path_full = None
                if hasattr(extract_info.get("pre_store_call"), "__call__"):
                    extract_info["pre_store_call"]()
                if "rename" in extract_info and extract_info["rename"]:
                    if tmp_dir is None:
                        tmp_dir = tempfile.mkdtemp()
                    tarball.extractall(tmp_dir, [tar_member_info])
                    path_full = extract_info["path"]
                    shutil.move(
                        os.path.join(tmp_dir, tar_member_info.name), path_full
                    )
                else:
                    dir_path = os.path.dirname(extract_info["path"])
                    tarball.extractall(dir_path, [tar_member_info])
                    path_full = os.path.join(dir_path, tar_member_info.name)
                file_attrs = extract_info["attrs"]
                os.chmod(path_full, file_attrs["mode"])
                os.chown(path_full, file_attrs["uid"], file_attrs["gid"])
    except (tarfile.TarError, EnvironmentError, OSError) as e:
        utils.err("unable to restore the cluster: %s" % e)
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    try:
        sig_path = os.path.join(settings.cib_dir, "cib.xml.sig")
        if os.path.exists(sig_path):
            os.remove(sig_path)
    except EnvironmentError as e:
        utils.err("unable to remove %s: %s" % (sig_path, e))


def config_backup_path_list(with_uid_gid=False):
    """
    Commandline options: no option
    NOTE: corosync.conf path may be altered using --corosync_conf
    """
    corosync_attrs = {
        "mtime": int(time.time()),
        "mode": 0o644,
        "uname": "root",
        "gname": "root",
        "uid": 0,
        "gid": 0,
    }
    corosync_authkey_attrs = dict(corosync_attrs)
    corosync_authkey_attrs["mode"] = 0o400
    cib_attrs = {
        "mtime": int(time.time()),
        "mode": 0o600,
        "uname": settings.pacemaker_uname,
        "gname": settings.pacemaker_gname,
    }
    if with_uid_gid:
        cib_attrs["uid"] = _get_uid(cib_attrs["uname"])
        cib_attrs["gid"] = _get_gid(cib_attrs["gname"])

    pcmk_authkey_attrs = dict(cib_attrs)
    pcmk_authkey_attrs["mode"] = 0o440
    file_list = {
        "cib.xml": {
            "path": os.path.join(settings.cib_dir, "cib.xml"),
            "required": True,
            "attrs": dict(cib_attrs),
        },
        "corosync_authkey": {
            "path": settings.corosync_authkey_file,
            "required": False,
            "attrs": corosync_authkey_attrs,
            "restore_procedure": None,
            "rename": True,
        },
        "pacemaker_authkey": {
            "path": settings.pacemaker_authkey_file,
            "required": False,
            "attrs": pcmk_authkey_attrs,
            "restore_procedure": None,
            "rename": True,
            "pre_store_call": _ensure_etc_pacemaker_exists,
        },
        "corosync.conf": {
            "path": settings.corosync_conf_file,
            "required": True,
            "attrs": dict(corosync_attrs),
        },
        "uidgid.d": {
            "path": settings.corosync_uidgid_dir,
            "required": False,
            "attrs": dict(corosync_attrs),
        },
        "pcs_settings.conf": {
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
        },
    }
    return file_list


def _get_uid(user_name):
    """
    Commandline options: no options
    """
    try:
        return pwd.getpwnam(user_name).pw_uid
    except KeyError:
        return utils.err(
            "Unable to determine uid of user '{0}'".format(user_name)
        )


def _get_gid(group_name):
    """
    Commandline options: no options
    """
    try:
        return grp.getgrnam(group_name).gr_gid
    except KeyError:
        return utils.err(
            "Unable to determine gid of group '{0}'".format(group_name)
        )


def _ensure_etc_pacemaker_exists():
    """
    Commandline options: no options
    """
    dir_name = os.path.dirname(settings.pacemaker_authkey_file)
    if not os.path.exists(dir_name):
        os.mkdir(dir_name)
        os.chmod(dir_name, 0o750)
        os.chown(
            dir_name,
            _get_uid(settings.pacemaker_uname),
            _get_gid(settings.pacemaker_gname),
        )


def config_backup_check_version(version):
    """
    Commandline options: no options
    """
    try:
        version_number = int(version)
        supported_version = config_backup_version()
        if version_number > supported_version:
            utils.err(
                f"Unsupported version of the backup, supported version is "
                f"{supported_version}, backup version is {version_number}"
            )
        if version_number < supported_version:
            warn(
                f"Restoring from the backup version {version_number}, current "
                f"supported version is {supported_version}"
            )
    except TypeError:
        utils.err("Cannot determine version of the backup")


def config_backup_add_version_to_tarball(tarball, version=None):
    """
    Commandline options: no options
    """
    ver = version if version is not None else str(config_backup_version())
    return utils.tar_add_file_data(tarball, ver.encode("utf-8"), "version.txt")


def config_backup_version():
    """
    Commandline options: no options
    """
    return 1


def config_checkpoint_list(lib, argv, modifiers):
    """
    Options: no options
    """
    del lib
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    try:
        file_list = os.listdir(settings.cib_dir)
    except OSError as e:
        utils.err("unable to list checkpoints: %s" % e)
    cib_list = []
    cib_name_re = re.compile(r"^cib-(\d+)\.raw$")
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
        print_to_stderr("No checkpoints available")
        return
    for cib_info in cib_list:
        print(
            "checkpoint %s: date %s"
            % (cib_info[1], datetime.datetime.fromtimestamp(round(cib_info[0])))
        )


def _checkpoint_to_lines(lib, checkpoint_number):
    # backup current settings
    orig_usefile = utils.usefile
    orig_filename = utils.filename
    orig_middleware = lib.middleware_factory
    # configure old code to read the CIB from a file
    utils.usefile = True
    utils.filename = os.path.join(
        settings.cib_dir, "cib-%s.raw" % checkpoint_number
    )
    # configure new code to read the CIB from a file
    lib.middleware_factory = orig_middleware._replace(
        cib=middleware.cib(utils.filename, utils.touch_cib_file)
    )
    # export the CIB to text
    result = False, []
    if os.path.isfile(utils.filename):
        result = True, _config_show_cib_lines(lib)
    # restore original settings
    utils.usefile = orig_usefile
    utils.filename = orig_filename
    lib.middleware_factory = orig_middleware
    return result


def config_checkpoint_view(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        print_to_stderr(usage.config(["checkpoint view"]))
        sys.exit(1)

    loaded, lines = _checkpoint_to_lines(lib, argv[0])
    if not loaded:
        utils.err("unable to read the checkpoint")
    print("\n".join(lines))


def config_checkpoint_diff(lib, argv, modifiers):
    """
    Commandline options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if len(argv) != 2:
        print_to_stderr(usage.config(["checkpoint diff"]))
        sys.exit(1)

    if argv[0] == argv[1]:
        utils.err("cannot diff a checkpoint against itself")

    errors = []
    checkpoints_lines = []
    for checkpoint in argv:
        if checkpoint == "live":
            lines = _config_show_cib_lines(lib)
            if not lines:
                errors.append("unable to read live configuration")
            else:
                checkpoints_lines.append(lines)
        else:
            loaded, lines = _checkpoint_to_lines(lib, checkpoint)
            if not loaded:
                errors.append(
                    "unable to read checkpoint '{0}'".format(checkpoint)
                )
            else:
                checkpoints_lines.append(lines)

    if errors:
        utils.err("\n".join(errors))

    print(
        "Differences between {0} (-) and {1} (+):".format(
            *[
                "live configuration"
                if label == "live"
                else f"checkpoint {label}"
                for label in argv
            ]
        )
    )
    print(
        "\n".join(
            [
                line.rstrip()
                for line in difflib.Differ().compare(
                    checkpoints_lines[0], checkpoints_lines[1]
                )
            ]
        )
    )


def config_checkpoint_restore(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file, a checkpoint will be restored into a specified file
    """
    # pylint: disable=broad-except
    del lib
    modifiers.ensure_only_supported("-f")
    if len(argv) != 1:
        print_to_stderr(usage.config(["checkpoint restore"]))
        sys.exit(1)

    cib_path = os.path.join(settings.cib_dir, "cib-%s.raw" % argv[0])
    try:
        snapshot_dom = parse(cib_path)
    except Exception as e:
        utils.err("unable to read the checkpoint: %s" % e)
    utils.replace_cib_configuration(snapshot_dom)
