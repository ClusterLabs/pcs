import os.path
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CURRENT_DIR, "{}.d".format(sys.argv[0]))


def write_file_to_stdout(file_name):
    with open(file_name) as file:
        sys.stdout.write(file.read())


def write_local_file_to_stdout(file_name):
    write_file_to_stdout(os.path.join(DATA_DIR, file_name))


def get_arg_values(argv, name):
    values = []
    next_value = len(argv)
    for i, value in enumerate(argv):
        if value == name:
            next_value = i + 1
        elif i == next_value:
            values.append(value)
    return values


def main():  # noqa: PLR0912,PLR0915
    # pylint: disable=too-many-branches
    argv = sys.argv[1:]
    if not argv:
        raise AssertionError()

    arg = argv.pop(0)

    option_file_map = {
        "--list-standards": "list_standards",
        "--list-ocf-providers": "list_ocf_providers",
    }
    list_options_type_to_file_map = {"primitive": "primitive-meta_metadata.xml"}

    if arg == "--show-metadata":
        if len(argv) != 1:
            raise AssertionError()
        arg = argv[0]
        known_agents = (
            "lsb:pcsmock",
            "ocf:heartbeat:pcsMock",
            "ocf:pacemaker:pcsMock",
            "ocf:pacemaker:remote",
            "ocf:pcsmock:action_method",
            "ocf:pcsmock:CamelCase",
            "ocf:pcsmock:duplicate_monitor",
            "ocf:pcsmock:minimal",
            "ocf:pcsmock:params",
            "ocf:pcsmock:stateful",
            "ocf:pcsmock:unique",
            "stonith:fence_pcsmock_action",
            "stonith:fence_pcsmock_method",
            "stonith:fence_pcsmock_minimal",
            "stonith:fence_pcsmock_params",
            "stonith:fence_pcsmock_unfencing",
            "stonith:fence_sbd",
            "systemd:pcsmock",
            "systemd:pcsmock@a:b",
        )
        # known_agents_map = {item.lower()}
        if arg in known_agents:
            write_local_file_to_stdout(
                "{}_metadata.xml".format(arg.replace(":", "__"))
            )
        else:
            sys.stderr.write(
                "pcs mock error message: unable to load agent metadata"
            )
            raise SystemExit(1)
    elif arg in option_file_map:
        if argv:
            raise AssertionError()
        write_local_file_to_stdout(option_file_map[arg])
    elif arg == "--list-agents":
        if len(argv) != 1:
            raise AssertionError()
        arg = argv[0]
        known_providers = ("ocf:heartbeat", "ocf:pacemaker", "ocf:pcsmock")
        if arg in known_providers:
            write_local_file_to_stdout(
                "list_agents_{}".format(arg.replace(":", "__"))
            )
        else:
            raise AssertionError()
    elif arg == "--list-options":
        if not len(argv) or get_arg_values(argv, "--output-as")[0] != "xml":
            raise AssertionError()
        option_type = argv[0]
        if option_type in list_options_type_to_file_map:
            write_local_file_to_stdout(
                list_options_type_to_file_map[option_type]
            )
        else:
            sys.stderr.write(
                "pcs mock error message: unable to load metadata for option "
                f"'{option_type}'"
            )
            raise SystemExit(1)
    elif arg == "--validate":
        if get_arg_values(argv, "--output-as")[0] != "xml":
            raise AssertionError()
        provider = get_arg_values(argv, "--provider")
        is_invalid = False
        for arg in argv:
            if "=" in arg and arg.split("=", 1)[1] == "is_invalid=True":
                is_invalid = True
                break
        output = ""
        if is_invalid:
            output = """<output source="stderr">pcsmock validation failure</output>"""
        stdout = """
            <pacemaker-result api-version="2.15" request="{cmd_str}">
              <resource-agent-action action="validate" class="{standard}" type="{agent_type}"{provider_str}>
                <overrides/>
                <agent-status code="5" message="not installed" execution_code="0" execution_message="complete" reason="environment is invalid, resource considered stopped"/>
                <command code="5">
                {output}
                </command>
              </resource-agent-action>
              <status code="5" message="Not installed">
                <errors>
                  <error>crm_resource: Error performing operation: Not installed</error>
                </errors>
              </status>
            </pacemaker-result>
        """.format(
            cmd_str=" ".join(sys.argv),
            standard=get_arg_values(argv, "--class")[0],
            agent_type=get_arg_values(argv, "--agent")[0],
            provider_str=f' provider="{provider[0]}"' if provider else "",
            output=output,
        )
        sys.stdout.write(stdout)
        if is_invalid:
            raise SystemExit(1)
    else:
        raise AssertionError()


if __name__ == "__main__":
    main()
