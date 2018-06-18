import pytest

from ontobio.io import qc
from ontobio.io import assocparser
from ontobio import ontol_factory

ontology = ontol_factory.OntologyFactory().create("tests/resources/goslim_generic.json")

def make_annotation(goid, evidence):
    annotation = ["blah", "blah", "blah", "blah", goid, "blah", evidence]
    return annotation

def test_result():
    assert qc.result(True, qc.FailMode.HARD) == qc.ResultType.PASS
    assert qc.result(False, qc.FailMode.HARD) == qc.ResultType.ERROR
    assert qc.result(False, qc.FailMode.SOFT) == qc.ResultType.WARNING

def test_go_rule26():

    config = assocparser.AssocParserConfig(
        ontology=ontology,
        paint=True
    )
    a = make_annotation("GO:BLAHBLAH", "IBA")
    # Pass due to IBA in paint
    test_result = qc.GoRule26().test(a, config)
    assert test_result.result_type == qc.ResultType.PASS

    config = assocparser.AssocParserConfig(
        ontology=ontology,
        paint=False
    )
    a = make_annotation("GO:BLAHBLAH", "ANY")
    # Pass due to non IBA
    test_result = qc.GoRule26().test(a, config)
    assert test_result.result_type == qc.ResultType.PASS

    config = assocparser.AssocParserConfig(
        ontology=ontology,
        paint=False
    )
    a = make_annotation("GO:BLAHBLAH", "IBA")
    # Pass due to non IBA
    test_result = qc.GoRule26().test(a, config)
    assert test_result.result_type == qc.ResultType.ERROR

def test_all_rules():
    # pass
    config = assocparser.AssocParserConfig(
        ontology=ontology
    )
    a = make_annotation("GO:0006397", "ANY")
    test_results = qc.test_go_rules(a, config)
    assert len(test_results.keys()) == 1
    assert test_results["GORULE:0000026"].result_type == qc.ResultType.PASS


if __name__ == "__main__":
    pytest.main(args=["tests/test_qc.py"])
