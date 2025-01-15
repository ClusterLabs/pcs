import os.path
import sys
from textwrap import dedent

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(CURRENT_DIR, "{}.d".format(sys.argv[0]))


def get_arg_values(argv, name):
    values = []
    next_value = len(argv)
    for i, value in enumerate(argv):
        if value == name:
            next_value = i + 1
        elif i == next_value:
            values.append(value)
    return values


def main():
    argv = sys.argv[1:]
    if not argv:
        raise AssertionError()

    arg = argv.pop(0)

    if arg == "--validate":
        if get_arg_values(argv, "--output-as")[0] != "xml":
            raise AssertionError()
        is_invalid = False
        for arg in argv:
            if "=" in arg and arg.split("=", 1)[1] == "is_invalid=True":
                is_invalid = True
                break
        output = ""
        if is_invalid:
            output = """<output source="stderr">pcsmock validation failure</output>"""
        cmd_str = " ".join(sys.argv)
        agent_type = get_arg_values(argv, "--agent")[0]
        stdout = dedent(
            f"""
            <pacemaker-result api-version="2.15" request="{cmd_str}">
              <validate agent="{agent_type}" valid="{str(is_invalid).lower()}">
                <command code="{-201 if is_invalid else 0}">
                {output}
                </command>
              </validate>
              <status code="{1 if is_invalid else 0}" message="{"Error" if is_invalid else "OK"}"/>
            </pacemaker-result>
            """
        )
        sys.stdout.write(stdout)
        if is_invalid:
            raise SystemExit(1)
    else:
        raise AssertionError()


if __name__ == "__main__":
    main()
