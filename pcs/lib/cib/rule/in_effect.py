from lxml.etree import _Element

from pcs.common import reports
from pcs.common.types import CibRuleInEffectStatus
from pcs.lib.external import CommandRunner
from pcs.lib.pacemaker.live import (
    get_rule_in_effect_status,
    has_rule_in_effect_status_tool,
)
from pcs.lib.xml_tools import etree_to_str


class RuleInEffectEval:
    """
    Base class for evaluating if a rule is in effect. Use one of its descendants
    based on which one suits your needs and environment the best.
    """

    def get_rule_status(self, rule_id: str) -> CibRuleInEffectStatus:
        """
        Figure out if a rule is expired, in effect, not yet in effect

        rule_id -- ID of the rule to be evaluated
        """
        raise NotImplementedError()


class RuleInEffectEvalDummy(RuleInEffectEval):
    """
    Evaluate all rules to UNKNOWN status. This is useful for example when we
    don't want to get slowed down by evaluating the rules.
    """

    def get_rule_status(self, rule_id: str) -> CibRuleInEffectStatus:
        return CibRuleInEffectStatus.UNKNOWN


class RuleInEffectEvalOneByOne(RuleInEffectEval):
    """
    Evaluate a rule by running a pacemaker tool.
    """

    def __init__(self, cib: _Element, runner: CommandRunner):
        """
        cib -- the whole cib containing the rule expressions
        runner -- a class for running external processes
        """
        self._runner = runner
        self._cib = cib
        self._cib_xml = etree_to_str(cib)

    def get_rule_status(self, rule_id: str) -> CibRuleInEffectStatus:
        return get_rule_in_effect_status(self._runner, self._cib_xml, rule_id)


# TODO Implement this once the pacemaker tool is capable of evaluating more
# than one rule per go. If we can eval all rules by running the tool once, it
# would be a significant speedup comparing to running the tool for each rule.
# class RuleInEffectEvalAllAtOnce(RuleInEffectEval):
#     pass


def get_rule_evaluator(
    cib: _Element,
    runner: CommandRunner,
    report_processor: reports.ReportProcessor,
    evaluate_expired: bool,
) -> RuleInEffectEval:
    if evaluate_expired:
        if has_rule_in_effect_status_tool():
            return RuleInEffectEvalOneByOne(cib, runner)
        report_processor.report(
            reports.ReportItem.warning(
                reports.messages.RuleInEffectStatusDetectionNotSupported()
            )
        )
    return RuleInEffectEvalDummy()
