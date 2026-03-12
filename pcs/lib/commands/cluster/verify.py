from pcs.common import reports
from pcs.lib.cib import fencing_topology
from pcs.lib.cib.resource.bundle import verify as verify_bundles
from pcs.lib.cib.tools import get_resources
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.live import get_cib, get_cib_xml, get_cib_xml_cmd_results
from pcs.lib.pacemaker.live import verify as verify_cmd
from pcs.lib.pacemaker.state import ClusterState


def verify(env: LibraryEnvironment, verbose=False):
    runner = env.cmd_runner()
    (
        dummy_stdout,
        verify_stderr,
        verify_returncode,
        can_be_more_verbose,
    ) = verify_cmd(runner, verbose=verbose)

    # 1) Do not even try to think about upgrading!
    # 2) We do not need cib management in env (no need for push...).
    # So env.get_cib is not best choice here (there were considerations to
    # upgrade cib at all times inside env.get_cib). Go to a lower level here.
    if verify_returncode != 0:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.InvalidCibContent(
                    verify_stderr,
                    can_be_more_verbose,
                )
            )
        )

        # Cib is sometimes loadable even if `crm_verify` fails (e.g. when
        # fencing topology is invalid). On the other hand cib with id
        # duplication is not loadable.
        # We try extra checks when cib is possible to load.
        cib_xml, dummy_stderr, returncode = get_cib_xml_cmd_results(runner)
        if returncode != 0:
            raise LibraryError()
    else:
        cib_xml = get_cib_xml(runner)

    cib = get_cib(cib_xml)
    env.report_processor.report_list(
        fencing_topology.verify(
            cib,
            ClusterState(env.get_cluster_state()).node_section.nodes,
        )
    )
    env.report_processor.report_list(verify_bundles(get_resources(cib)))
    if env.report_processor.has_errors:
        raise LibraryError()
