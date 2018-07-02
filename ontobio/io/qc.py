import json
import enum
import collections

from typing import List, Dict
from ontobio import ontol
from ontobio.io import assocparser

FailMode = enum.Enum("FailMode", {"SOFT": "soft", "HARD": "hard"})
ResultType = enum.Enum("Result", {"PASS": "Pass", "WARNING": "Warning", "ERROR": "Error"})
TestResult = collections.namedtuple("TestResult", ["result_type", "message"])

"""
Send True for passes, and this returns the PASS ResultType, and if False, then
depending on the fail mode it returns either WARNING or ERROR ResultType.
"""
def result(passes: bool, fail_mode: FailMode) -> ResultType:
    if passes:
        return ResultType.PASS

    # Else we didn't pass
    if fail_mode == FailMode.SOFT:
        return ResultType.WARNING

    if fail_mode == FailMode.HARD:
        return ResultType.ERROR


class GoRule(object):

    def __init__(self, id, title, fail_mode: FailMode):
        self.id = id
        self.title = title
        self.fail_mode = fail_mode
        

class GoRule26(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000026", "IBA evidence codes should be filtered from main MOD gaf sources", FailMode.HARD)
        self.offending_evidence = ["IBA"]

    def test(self, annotation: List, config: assocparser.AssocParserConfig) -> TestResult:
        evidence = annotation[6]
        # If we see a bad evidence, and we're not in a paint file then fail.
        if evidence in self.offending_evidence and not config.paint:
            return TestResult(result(False, self.fail_mode), self.title)
        else:
            return TestResult(result(True, self.fail_mode), self.title)


GoRules = enum.Enum("GoRules", {
    "GoRule26": GoRule26()
})

def test_go_rules(annotation: List, ontology: ontol.Ontology) -> Dict[str, TestResult]:
    all_results = {}
    for rule in list(GoRules):
        result = rule.value.test(annotation, ontology)
        all_results[rule.value.id] = result

    return all_results
