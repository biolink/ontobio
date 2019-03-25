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

    def _list_terms(self, pipe_separated):
        terms = pipe_separated.split("|")
        terms = [t for t in terms if t != ""] # Remove empty strings
        return terms

    def _result(self, passes: bool) -> TestResult:
        return TestResult(result(passes, self.fail_mode), self.title)

class GoRule02(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000002", "No 'NOT' annotations to 'protein binding ; GO:0005515'", FailMode.SOFT)


    def test(self, annotation: List, config: assocparser.AssocParserConfig) -> TestResult:

        qualifier = self._list_terms(annotation[3])
        goclass = annotation[4]

        fails = (goclass == "GO:0005515" and "NOT" in qualifier)
        return self._result(not fails)

class GoRule06(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000006", "IEP and HEP usage is restricted to terms from the Biological Process ontology", FailMode.HARD)

    def test(self, annotation: List, config: assocparser.AssocParserConfig) -> TestResult:

        aspect = annotation[8]
        evidence = annotation[6]
        fails = evidence in ["IEP", "HEP"] and aspect != "P"
        return self._result(not fails)


class GoRule08(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000008", "No annotations should be made to uninformatively high level terms", FailMode.SOFT)
        self.do_not_annotate = None
        self.do_not_manually_annotate = None

    def test(self, annotation: List, config: assocparser.AssocParserConfig) -> TestResult:
        # Cache the subsets
        if self.do_not_annotate is None and config.ontology is not None:
            self.do_not_annotate = set(config.ontology.extract_subset("gocheck_do_not_annotate"))
            self.do_not_manually_annotate = set(config.ontology.extract_subset("gocheck_do_not_manually_annotate"))
        elif self.do_not_annotate is None and config.ontology is None:
            self.do_not_annotate = []
            self.do_not_manually_annotate = []

        goid = annotation[4]
        evidence = annotation[6]

        auto_annotated = goid in self.do_not_annotate
        manually_annotated = evidence != "IEA" and goid in self.do_not_manually_annotate
        not_high_level = not (auto_annotated or manually_annotated)

        t = result(not_high_level, self.fail_mode)
        return TestResult(t, self.title)


class GoRule11(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000011", "ND annotations to root nodes only", FailMode.HARD)
        self.root_go_classes = ["GO:0003674", "GO:0005575", "GO:0008150"]

    def test(self, annotation: List, config: assocparser.AssocParserConfig) -> TestResult:
        goclass = annotation[4]
        evidence = annotation[6]

        # If we see a bad evidence, and we're not in a paint file then fail.
        fails = (evidence == "ND" and goclass not in self.root_go_classes)
        return self._result(not fails)


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


class GoRule17(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000017", "IDA annotations must not have a With/From entry", FailMode.SOFT)

    def test(self, annotation: List, config: assocparser.AssocParserConfig) -> TestResult:
        evidence = annotation[6]
        withfrom = annotation[7]

        if evidence == "IDA":
            return self._result(not bool(withfrom))
        else:
            return self._result(True)

class GoRule18(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000018", "IPI annotations require a With/From entry", FailMode.SOFT)

    def test(self, annotation: List, config: assocparser.AssocParserConfig) -> TestResult:
        evidence = annotation[6]
        withfrom = annotation[7]

        if evidence == "IPI":
            return self._result(bool(withfrom))
        else:
            return self._result(True)


class GoRule26(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000026", "IBA evidence codes should be filtered from main MOD gaf sources", FailMode.HARD)
        self.offending_evidence = ["IBA"]

    def test(self, annotation: List, config: assocparser.AssocParserConfig) -> TestResult:
        evidence = annotation[6]
        # If we see a bad evidence, and we're not in a paint file then fail.
        fails = (evidence in self.offending_evidence and not config.paint)
        return self._result(not fails)


class GoRule29(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000029", "All IEAs over a year old are removed", FailMode.HARD)
        self.one_year = datetime.timedelta(days=365)

    def test(self, annotation: List, config: assocparser.AssocParserConfig) -> TestResult:
        evidence = annotation[6]
        date = annotation[13]

        now = datetime.datetime.today()

        fails = (evidence == "IEA" and now - datetime.datetime(int(date[0:4]), int(date[4:6]), int(date[6:8]), 0, 0, 0, 0) > self.one_year)
        return self._result(not fails)


class GoRule30(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000030", "Deprecated GO_REFs are not allowed", FailMode.HARD)

    def test(self, annotation: List, config: assocparser.AssocParserConfig) -> TestResult:
        references = self._list_terms(annotation[5])
        # Not allowed is GO_REF:0000033 and GO_PAINT:x
        has_goref_33 = "GO_REF:0000033" in references
        has_go_paint = any([r.startswith("GO_PAINT") for r in references])
        # don't accept either of has_goref_33 or has_go_paint
        return self._result(not (has_goref_33 or has_go_paint))


GoRules = enum.Enum("GoRules", {
    "GoRule02": GoRule02(),
    "GoRule08": GoRule08(),
    "GoRule11": GoRule11(),
    "GoRule16": GoRule16(),
    "GoRule17": GoRule17(),
    "GoRule18": GoRule18(),
    "GoRule26": GoRule26(),
    "GoRule29": GoRule29(),
    "GoRule30": GoRule30()
})

def test_go_rules(annotation: List, config: assocparser.AssocParserConfig) -> Dict[str, TestResult]:
    all_results = {}
    for rule in list(GoRules):
        result = rule.value.test(annotation, config)
        all_results[rule.value.id] = result

    return all_results
