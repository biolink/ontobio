import pytest

from ontobio.io import qc
from ontobio import ontol_factory

ontology = ontol_factory.OntologyFactory().create("tests/resources/goslim_generic.json")

def make_annotation(goid, evidence):
    annotation = ["blah", "blah", "blah", "blah", goid, "blah", evidence]
    return annotation

def test_result():
    assert qc.result(True, qc.FailMode.HARD) == qc.ResultType.PASS
    assert qc.result(False, qc.FailMode.HARD) == qc.ResultType.ERROR
    assert qc.result(False, qc.FailMode.SOFT) == qc.ResultType.WARNING

def test_go_rule08():
    # pass
    a = make_annotation("GO:0006397", "ANY")
    test_result = qc.GoRule08().test(a, ontology)
    assert test_result.result_type == qc.ResultType.PASS

    # fail with manual evidence and do_not_manually_annotate
    a = make_annotation("GO:0006950", "ANY")
    test_result = qc.GoRule08().test(a, ontology)
    assert test_result.result_type == qc.ResultType.ERROR

    a = make_annotation("GO:0006810", "IEA")
    test_result = qc.GoRule08().test(a, ontology)
    assert test_result.result_type == qc.ResultType.ERROR

def test_all_rules():
    # pass
    a = make_annotation("GO:0006397", "ANY")
    test_results = qc.test_go_rules(a, ontology)
    assert len(test_results.keys()) == 1
    assert test_results["GORULE:0000008"].result_type == qc.ResultType.PASS


if __name__ == "__main__":
    pytest.main(args=["tests/test_qc.py"])
