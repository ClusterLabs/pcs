import datetime
import difflib
import grp
import json
import logging
import os
import os.path
import pwd
import re
import shutil
import sys
import tarfile
import tempfile
import time
from io import BytesIO
from xml.dom.minidom import parse

try:
    import distro

    no_distro_package = False
except ImportError:
    no_distro_package = True
    import platform

# TODO remove, deprecated
try:
    import clufter.command_manager
    import clufter.facts
    import clufter.filter_manager
    import clufter.format_manager

    no_clufter = False
except ImportError:
    no_clufter = True

from pcs import (
    alert,
    cluster,
    constraint,
    quorum,
    settings,
    status,
    stonith,
    usage,
    utils,
)
from pcs.cli.cluster_property.output import (
    PropertyConfigurationFacade,
    properties_to_text_legacy,
)
from pcs.cli.common import middleware
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.output import (
    INDENT_STEP,
    smart_wrap_text,
)
from pcs.cli.constraint import command as constraint_command
from pcs.cli.nvset import nvset_dto_list_to_lines
from pcs.cli.reports import process_library_reports
from pcs.cli.reports.output import warn
from pcs.cli.resource.output import (
    ResourcesConfigurationFacade,
    resources_to_text,
)
from pcs.common.interface import dto
from pcs.common.reports import constraints as constraints_reports
from pcs.common.str_tools import indent
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

    corosync_conf_dto = None
    cluster_name = ""
    properties_facade = PropertyConfigurationFacade.from_properties_config(
        lib.cluster_property.get_properties(),
    )
    try:
        corosync_conf_dto = lib.cluster.get_corosync_conf_struct()
        cluster_name = corosync_conf_dto.cluster_name
    except LibraryError:
        # there is no corosync.conf on remote nodes, we can try to
        # get cluster name from pacemaker
        pass
    if not cluster_name:
        cluster_name = properties_facade.get_property_value("cluster-name", "")
    print("Cluster Name: %s" % cluster_name)

    status.nodes_status(lib, ["config"], modifiers.get_subset("-f"))
    print()
    print(
        "\n".join(
            _config_show_cib_lines(lib, properties_facade=properties_facade)
        )
    )
    if (
        utils.hasCorosyncConf()
        and not modifiers.is_specified("-f")
        and not modifiers.is_specified("--corosync_conf")
    ):
        cluster.cluster_uidgid(
            lib, [], modifiers.get_subset(), silent_list=True
        )
    if corosync_conf_dto:
        quorum_device_dict = {}
        if corosync_conf_dto.quorum_device:
            quorum_device_dict = dto.to_dict(corosync_conf_dto.quorum_device)
        config = dict(
            options=corosync_conf_dto.quorum_options,
            device=quorum_device_dict,
        )
        quorum_lines = quorum.quorum_config_to_str(config)
        print()
        print("Quorum:")
        print("\n".join(indent(quorum_lines)))


def _config_show_cib_lines(lib, properties_facade=None):
    """
    Commandline options:
      * -f - CIB file
    """
    # update of pcs_options will change output of constraint show and
    # displaying resources and operations defaults
    utils.pcs_options["--full"] = 1
    # get latest modifiers object after updating pcs_options
    modifiers = utils.get_input_modifiers()
    cib_dom = utils.get_cib_dom()

    resources_facade = ResourcesConfigurationFacade.from_resources_dto(
        lib.resource.get_configured_resources()
    )

    all_lines = []

    all_lines.append("Resources:")
    all_lines.extend(
        smart_wrap_text(
            indent(
                resources_to_text(resources_facade.filter_stonith(False)),
                indent_step=INDENT_STEP,
            )
        )
    )
    all_lines.append("")
    all_lines.append("Stonith Devices:")
    all_lines.extend(
        smart_wrap_text(
            indent(
                resources_to_text(resources_facade.filter_stonith(True)),
                indent_step=INDENT_STEP,
            )
        )
    )
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
                ).meta_attributes,
                nvset_label="Meta Attrs",
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
                ).meta_attributes,
                nvset_label="Meta Attrs",
                with_ids=modifiers.get("--full"),
                text_if_empty="No defaults set",
            )
        )
    )

    if not properties_facade:
        properties_facade = PropertyConfigurationFacade.from_properties_config(
            lib.cluster_property.get_properties()
        )
    properties_lines = properties_to_text_legacy(properties_facade)
    all_lines.append("")
    all_lines.extend(properties_lines)

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
        usage.config(["restore"])
        sys.exit(1)

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
            if (
                _status["corosync"]
                or _status["pacemaker"]
                or
                # not supported by older pcsd, do not fail if not present
                _status.get("pacemaker_remote", False)
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
        print("No checkpoints available")
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
    orig_env = lib.env
    # configure old code to read the CIB from a file
    utils.usefile = True
    utils.filename = os.path.join(
        settings.cib_dir, "cib-%s.raw" % checkpoint_number
    )
    # configure new code to read the CIB from a file
    lib.middleware_factory = orig_middleware._replace(
        cib=middleware.cib(utils.filename, utils.touch_cib_file)
    )
    lib.env = utils.get_cli_env()
    # export the CIB to text
    result = False, []
    if os.path.isfile(utils.filename):
        result = True, _config_show_cib_lines(lib)
    # restore original settings
    utils.usefile = orig_usefile
    utils.filename = orig_filename
    lib.middleware_factory = orig_middleware
    lib.env = orig_env
    return result


def config_checkpoint_view(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        usage.config(["checkpoint view"])
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
        usage.config(["checkpoint diff"])
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
        usage.config(["checkpoint restore"])
        sys.exit(1)

    cib_path = os.path.join(settings.cib_dir, "cib-%s.raw" % argv[0])
    try:
        snapshot_dom = parse(cib_path)
    except Exception as e:
        utils.err("unable to read the checkpoint: %s" % e)
    utils.replace_cib_configuration(snapshot_dom)


# TODO remove, deprecated command
def config_import_cman(lib, argv, modifiers):
    """
    Options:
      * --force - skip checks, overwrite files
      * --interactive - interactive issue resolving
      * --request-timeout - effective only when output is not specified
    """
    # pylint: disable=no-member
    del lib
    warn("This command is deprecated and will be removed.")
    modifiers.ensure_only_supported(
        "--force",
        "interactive",
        "--request-timeout",
    )
    if no_clufter:
        utils.err(
            "Unable to perform a CMAN cluster conversion due to missing "
            "python-clufter package"
        )
    clufter_supports_corosync3 = hasattr(clufter.facts, "cluster_pcs_camelback")

    # prepare convertor options
    cluster_conf = settings.cluster_conf_file
    dry_run_output = None
    output_format = "corosync.conf"
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
                    "corosync.conf",
                    "pcs-commands",
                    "pcs-commands-verbose",
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
    if output_format not in ("pcs-commands", "pcs-commands-verbose") and (
        dry_run_output and not dry_run_output.endswith(".tar.bz2")
    ):
        dry_run_output += ".tar.bz2"
    if invalid_args or not dry_run_output:
        usage.config(["import-cman"])
        sys.exit(1)
    debug = modifiers.get("--debug")
    force = modifiers.get("--force")
    interactive = modifiers.get("--interactive")

    if dist is not None:
        if not clufter_supports_corosync3:
            utils.err(
                "Unable to perform a CMAN cluster conversion due to clufter "
                "not supporting Corosync 3. Please, upgrade clufter packages."
            )
        if not clufter.facts.cluster_pcs_camelback("linux", dist.split(",")):
            utils.err("dist does not match output-format")
    elif output_format == "corosync.conf":
        dist = _get_linux_dist()
    else:
        # for output-format=pcs-command[-verbose]
        dist = _get_linux_dist()

    clufter_args = {
        "input": str(cluster_conf),
        "cib": {"passin": "bytestring"},
        "nocheck": force,
        "batch": True,
        "sys": "linux",
        "dist": dist,
    }
    if interactive:
        if "EDITOR" not in os.environ:
            utils.err("$EDITOR environment variable is not set")
        clufter_args["batch"] = False
        clufter_args["editor"] = os.environ["EDITOR"]
    if debug:
        logging.getLogger("clufter").setLevel(logging.DEBUG)
    if output_format == "corosync.conf":
        clufter_args["coro"] = {"passin": "struct"}
        cmd_name = "ccs2pcs-camelback"
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
        elif clufter_supports_corosync3 and clufter.facts.cluster_pcs_camelback(
            "linux", dist.split(",")
        ):
            cmd_name = "ccs2pcscmd-camelback"
        else:
            utils.err(
                "unrecognized dist, try something recognized"
                + " (e. g. rhel,6.8 or redhat,7.3 or debian,7 or ubuntu,trusty)"
            )
    clufter_args_obj = type(str("ClufterOptions"), (object,), clufter_args)

    # run convertor
    run_clufter(
        cmd_name,
        clufter_args_obj,
        debug,
        force,
        "Error: unable to import cluster configuration",
    )

    # save commands
    if output_format in ("pcs-commands", "pcs-commands-verbose"):
        ok, message = utils.write_file(
            dry_run_output, clufter_args_obj.output["passout"].decode()
        )
        if not ok:
            utils.err(message)
        return

    # put new config files into tarball
    file_list = config_backup_path_list()
    for file_item in file_list.values():
        file_item["attrs"]["uname"] = "root"
        file_item["attrs"]["gname"] = "root"
        file_item["attrs"]["uid"] = 0
        file_item["attrs"]["gid"] = 0
        file_item["attrs"]["mode"] = 0o600
    tar_data = BytesIO()
    try:
        with tarfile.open(fileobj=tar_data, mode="w|bz2") as tarball:
            config_backup_add_version_to_tarball(tarball)
            utils.tar_add_file_data(
                tarball,
                clufter_args_obj.cib["passout"],
                "cib.xml",
                **file_list["cib.xml"]["attrs"],
            )
            # put uidgid into separate files
            fmt_simpleconfig = clufter.format_manager.FormatManager.init_lookup(
                "simpleconfig"
            ).plugins["simpleconfig"]
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
                corosync_conf_data,
                "corosync.conf",
                **file_list["corosync.conf"]["attrs"],
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
                    uidgid_data,
                    "uidgid.d/" + filename,
                    **file_list["uidgid.d"]["attrs"],
                )
    except (tarfile.TarError, EnvironmentError) as e:
        utils.err("unable to create tarball: %s" % e)
    tar_data.seek(0)

    # save tarball / remote restore
    if dry_run_output:
        ok, message = utils.write_file(
            dry_run_output, tar_data.read(), permissions=0o600, binary=True
        )
        if not ok:
            utils.err(message)
    else:
        config_restore_remote(None, tar_data)
    tar_data.close()


def _get_linux_dist():
    if no_distro_package:
        # For Python 3.8+, python3-distro is a required dependency and we
        # should never get here. Pylint, of course, cannot know that.
        # pylint: disable=deprecated-method
        # pylint: disable=no-member
        # pylint: disable=used-before-assignment
        distribution = platform.linux_distribution(full_distribution_name=False)
    else:
        distribution = distro.linux_distribution(full_distribution_name=False)
    return ",".join(distribution)


# TODO remove, deprecated command
def config_export_pcs_commands(lib, argv, modifiers, verbose=False):
    """
    Options:
      * --force - skip checks, overwrite files
      * --interactive - interactive issue resolving
      * -f - CIB file
      * --corosync_conf
    """
    del lib
    warn("This command is deprecated and will be removed.")
    modifiers.ensure_only_supported(
        "--force", "--interactive", "-f", "--corosync_conf"
    )
    if no_clufter:
        utils.err(
            "Unable to perform export due to missing python-clufter package"
        )

    # parse options
    debug = modifiers.get("--debug")
    force = modifiers.get("--force")
    interactive = modifiers.get("--interactive")
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
        usage.config(["export pcs-commands"])
        sys.exit(1)
    # complete optional options
    if dist is None:
        dist = _get_linux_dist()

    # prepare convertor options
    clufter_args = {
        "nocheck": force,
        "batch": True,
        "sys": "linux",
        "dist": dist,
        "coro": settings.corosync_conf_file,
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
    clufter_args_obj = type(str("ClufterOptions"), (object,), clufter_args)
    cmd_name = "pcs2pcscmd-camelback"

    # run convertor
    run_clufter(
        cmd_name,
        clufter_args_obj,
        debug,
        force,
        "Error: unable to export cluster configuration",
    )

    # save commands if not printed to stdout by clufter
    if output_file:
        # pylint: disable=no-member
        ok, message = utils.write_file(
            output_file, clufter_args_obj.output["passout"].decode()
        )
        if not ok:
            utils.err(message)


# TODO remove, deprecated
def run_clufter(cmd_name, cmd_args, debug, force, err_prefix):
    """
    Commandline options: no options used but messages which include --force,
      --debug and --interactive are generated
    """
    # pylint: disable=broad-except
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
