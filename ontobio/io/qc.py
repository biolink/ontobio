import json
import enum
import collections
import datetime

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


class GoRule11(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000011", "ND annotations to root nodes only", FailMode.HARD)
        self.root_go_classes = ["GO:0003674", "GO:0005575", "GO:0008150"]

    def test(self, annotation: List, config: assocparser.AssocParserConfig) -> TestResult:
        goclass = annotation[4]
        evidence = annotation[6]

        # If we see a bad evidence, and we're not in a paint file then fail.
        if evidence == "ND" and goclass not in self.root_go_classes:
            return TestResult(result(False, self.fail_mode), self.title)
        else:
            return TestResult(result(True, self.fail_mode), self.title)


class GoRule16(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000016", "All IC annotations should include a GO ID in the \"With/From\" column", FailMode.SOFT)

    def test(self, annotation: List, config: assocparser.AssocParserConfig) -> TestResult:
        evidence = annotation[6]
        withfrom = self._list_terms(annotation[7])

        if evidence == "IC":
            only_go = [t for t in withfrom if t.startswith("GO:")] # Filter terms that aren't GO terms
            return TestResult(result(len(only_go) >= 1, self.fail_mode), self.title)

        else:
            return TestResult(result(True, self.fail_mode), self.title)

    def _list_terms(self, pipe_separated):
        terms = pipe_separated.split("|")
        terms = [t for t in terms if t != ""] # Remove empty strings
        return terms



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

class GoRule29(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000029", "All IEAs over a year old are removed", FailMode.HARD)

    def test(self, annotation: List, config: assocparser.AssocParserConfig) -> TestResult:
        evidence = annotation[6]
        annotation_date = annotation[13]

        now = datetime.datetime.today()

        if evidence == "IEA" and now - datetime.datetime.strptime(annotation_date, "%Y%m%d") > datetime.timedelta(days=365):
            return TestResult(result(False, self.fail_mode), self.title)
        else:
            return TestResult(result(True, self.fail_mode), self.title)


GoRules = enum.Enum("GoRules", {
    "GoRule11": GoRule11(),
    "GoRule16": GoRule16(),
    "GoRule26": GoRule26(),
    "GoRule29": GoRule29()
})

def test_go_rules(annotation: List, ontology: ontol.Ontology) -> Dict[str, TestResult]:
    all_results = {}
    for rule in list(GoRules):
        result = rule.value.test(annotation, ontology)
        all_results[rule.value.id] = result

    return all_results
