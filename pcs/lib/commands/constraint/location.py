from lxml import etree

from pcs.lib.env import LibraryEnvironment


def remove_rules(env: LibraryEnvironment, ids: list[str]) -> None:
    orig_cib = env.get_cib()
    report_processor = env.report_processor
    deletion_simulation_cib = etree.parse(etree.tostring(orig_cib))
