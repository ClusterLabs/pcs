from pcs import usage
from pcs.cli.cib.element import command as cib_element_cmd
from pcs.cli.common.routing import create_router

cib_cmd = create_router(
    {
        "element": create_router(
            {
                "description": cib_element_cmd.description,
            },
            ["cib", "element"],
        ),
        "help": lambda lib, argv, modifiers: print(usage.cib(argv)),
    },
    ["cib"],
)
