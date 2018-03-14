import json
import enum
import collections

from typing import List, Dict
from ontobio import ontol

FailMode = enum.Enum("FailMode", {"SOFT": "soft", "HARD": "hard"})
ResultType = enum.Enum("Result", {"PASS": "Pass", "WARNING": "Warning", "ERROR": "Error"})
TestResult = collections.namedtuple("TestResult", ["result_type", "message"])

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


class GoRule08(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000008", "No annotations should be made to uninformatively high level terms", FailMode.HARD)
        self.do_not_annotate = None
        self.do_not_manually_annotate = None

    def test(self, annotation: List, ontology: ontol.Ontology) -> TestResult:
        # Cache the subsets
        if self.do_not_annotate is None and ontology is not None:
            self.do_not_annotate = ontology.extract_subset("gocheck_do_not_annotate")
            self.do_not_manually_annotate = ontology.extract_subset("gocheck_do_not_manually_annotate")
        elif self.do_not_annotate is None and ontology is None:
            self.do_not_annotate = []
            self.do_not_manually_annotate = []

        goid = annotation[4]
        evidence = annotation[6]

        auto_annotated = goid in self.do_not_annotate
        manually_annotated = evidence != "IEA" and goid in self.do_not_manually_annotate
        not_high_level = not (auto_annotated or manually_annotated)

        t = result(not_high_level, self.fail_mode)
        return TestResult(t, self.title)

GoRules = enum.Enum("GoRules", {"GoRule08": GoRule08()})

def test_go_rules(annotation: List, ontology: ontol.Ontology) -> Dict[str, TestResult]:
    all_results = {}
    for rule in list(GoRules):
        result = rule.value.test(annotation, ontology)
        all_results[rule.value.id] = result

    return all_results
