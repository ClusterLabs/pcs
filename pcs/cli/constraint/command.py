from pcs.cli.constraint import parse_args


def create_with_set(create_with_set_library_call, argv, modifiers):
    """
    callable create_with_set_library_call create constraint with set
    list argv part of comandline args
        see usage for  "constraint (colocation|resource|ticket) set"
    dict like object modifiers can contain
        "force" allows resource in clone/master and constraint duplicity

    Commandline options:
      * --force - allow resource inside clone (or master), allow duplicate
        element
      * -f - CIB file
    """
    resource_set_list, constraint_options = parse_args.prepare_set_args(argv)
    create_with_set_library_call(
        resource_set_list,
        constraint_options,
        resource_in_clone_alowed=modifiers.get("--force"),
        duplication_alowed=modifiers.get("--force"),
    )
