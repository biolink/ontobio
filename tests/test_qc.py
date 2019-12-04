import pytest
import datetime

from ontobio.io import qc
from ontobio.io import gaference
from ontobio.io import assocparser
from ontobio import ontol_factory

ontology = ontol_factory.OntologyFactory().create("tests/resources/goslim_generic.json")

def make_annotation(goid, evidence):
    annotation = ["blah", "blah", "blah", "blah", goid, "blah", evidence]
    return annotation

def test_qc_result():
    assert qc.result(True, qc.FailMode.HARD) == qc.ResultType.PASS
    assert qc.result(False, qc.FailMode.HARD) == qc.ResultType.ERROR
    assert qc.result(False, qc.FailMode.SOFT) == qc.ResultType.WARNING

def test_go_rule02():
    a = ["blah"] * 16
    a[3] = "NOT"
    a[4] = "GO:0005515"

    test_result = qc.GoRule02().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.WARNING

    a[3] = ""
    test_result = qc.GoRule02().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    a[3] = "NOT"
    a[4] = "GO:0003674"
    test_result = qc.GoRule02().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule_06():
    a = ["blah"] * 16
    a[6] = "HEP"
    a[8] = "C"
    test_result = qc.GoRule06().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

    a = ["blah"] * 16
    a[6] = "HEP"
    a[8] = "P"
    test_result = qc.GoRule06().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    a = ["blah"] * 16
    a[6] = "IEA"
    a[8] = "P"
    test_result = qc.GoRule06().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule_07():
    a = ["blah"] * 16
    a[4] = "GO:0003824"
    a[6] = "IPI"

    test_result = qc.GoRule07().test(a, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING

    a[4] = "GO:1234567"
    test_result = qc.GoRule07().test(a, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

    a[4] = "GO:0003824"
    a[6] = "BLA"
    test_result = qc.GoRule07().test(a, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule08():
    a = ["blah"] * 16
    a[4] = "GO:0006810" # do not annotate
    a[6] = "IEA"

    test_result = qc.GoRule08().test(a, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING

    a[6] = "IC"
    test_result = qc.GoRule08().test(a, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING

    a[4] = "GO:0007049" # do not manually annotate
    # evidence is IC, non IEA
    test_result = qc.GoRule08().test(a, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING

    a[6] = "IEA"
    # IEA, but on not manual, so should pass
    test_result = qc.GoRule08().test(a, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

    a[4] = "GO:0034655" # neither
    a[6] = "IC"
    test_result = qc.GoRule08().test(a, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule11():
    a = ["blah"] * 16
    a[4] = "GO:0003674"
    a[6] = "ND"

    test_result = qc.GoRule11().test(a, assocparser.AssocParserConfig())
    print("first test, we have {}".format(test_result))
    assert test_result.result_type == qc.ResultType.PASS

    # Bad GO ID
    a = ["blah"] * 16
    a[4] = "GO:1234567"
    a[6] = "ND"

    test_result = qc.GoRule11().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

    # Not ND and not Root
    a = ["blah"] * 16
    a[4] = "GO:1234567"
    a[6] = "FOO"

    test_result = qc.GoRule11().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    # Root, but not ND
    a = ["blah"] * 16
    a[4] = "GO:0003674"
    a[6] = "FOO"
    test_result = qc.GoRule11().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

def test_go_rules_13():

    a = ["PomBase", "SPBC11B10.09", "cdc2", "", "GO:0007275", "PMID:21873635", "IBA", "PANTHER:PTN000623979|TAIR:locus:2099478", "P", "Cyclin-dependent kinase 1", "UniProtKB:P04551|PTN000624043", "protein", "taxon:284812", "20170228", "GO_Central", "", ""]
    gaferences = gaference.load_gaferencer_inferences_from_file("tests/resources/test.inferences.json")
    test_result = qc.GoRule13().test(a, assocparser.AssocParserConfig(annotation_inferences=gaferences))
    assert test_result.result_type == qc.ResultType.WARNING

def test_go_rules_15():

    a = ["blah"] * 16
    a[4] = "GO:0044419"
    a[12] = "taxon:123|taxon:456"

    test_result = qc.GoRule15().test(a, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

    a[4] = "GO:123456"
    test_result = qc.GoRule15().test(a, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING

    a[4] = "GO:0044215"
    a[12] = "taxon:123"
    test_result = qc.GoRule15().test(a, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule_16():
    # No GO term w/ID
    a = ["blah"] * 16
    a[6] = "IC"
    a[7] = "BLAH:12345"

    test_result = qc.GoRule16().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

    # withfrom has GO term
    a = ["blah"] * 16
    a[6] = "IC"
    a[7] = "GO:12345"

    test_result = qc.GoRule16().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    # Pipe
    a = ["blah"] * 16
    a[6] = "IC"
    a[7] = "GO:12345|BLAH:54321"

    test_result = qc.GoRule16().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    # Empty withfrom
    a = ["blah"] * 16
    a[6] = "IC"
    a[7] = ""

    test_result = qc.GoRule16().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

    # Not IC
    a = ["blah"] * 16
    a[6] = "GOT"
    a[7] = "BLAH:5555555|FOO:999999"

    test_result = qc.GoRule16().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule_16_list_terms():
    gr16 = qc.GoRule16()

    withfrom = "GO:12345"
    assert gr16._list_terms(withfrom) == ["GO:12345"]

    withfrom = ""
    assert gr16._list_terms(withfrom) == []

    withfrom = "GO:12345|GO:2223334"
    assert gr16._list_terms(withfrom) == ["GO:12345", "GO:2223334"]

def test_go_rule_17():
    # IDA with anything in withfrom
    a = ["blah"] * 16
    a[6] = "IDA"
    a[7] = "BLAH:12345"

    test_result = qc.GoRule17().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.WARNING

    # Nothing in withfrom, passes
    a[7] = ""
    test_result = qc.GoRule17().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule_18():
    # IDA with nothing in withfrom
    a = ["blah"] * 16
    a[6] = "IPI"
    a[7] = ""

    test_result = qc.GoRule18().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.WARNING

    # Something in withfrom, passes
    a[7] = "BLAH:12345"
    test_result = qc.GoRule18().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

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

def test_go_rule28():

    config = assocparser.AssocParserConfig(
        ontology=ontology
    )

    a = ["blah"] * 16
    a[4] = "GO:0005975"
    a[8] = "P"

    test_result = qc.GoRule28().test(a, config)

    assert test_result.result_type == qc.ResultType.PASS
    assert test_result.result == a

    a = ["blah"] * 16
    a[4] = "GO:0005975"
    a[8] = "C"

    test_result = qc.GoRule28().test(a, config)

    assert test_result.result_type == qc.ResultType.WARNING
    fixed_a = a
    fixed_a[8] = "P"
    assert test_result.result == fixed_a
    assert test_result.message == "Found violation of: `Aspect can only be one of C, P, F` but was repaired"

def test_go_rule29():
    a = ["blah"] * 16
    a[6] = "IEA"
    a[13] = "19901111" # Nov 11, 1990, more than a year old

    test_result = qc.GoRule29().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

    a = ["blah"] * 16
    a[6] = "FOO"
    a[13] = "19901111"

    test_result = qc.GoRule29().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    now = datetime.datetime.now()
    six_months_ago = now - datetime.timedelta(days=180)
    a = ["blah"] * 16
    a[6] = "IEA"
    a[13] = six_months_ago.strftime("%Y%m%d")

    test_result = qc.GoRule29().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

def test_gorule30():
    a = ["blah"] * 16
    a[5] = "GO_REF:0000033"

    config = assocparser.AssocParserConfig(
        goref_metadata={
            "goref-0000033": {
                "authors": "Pascale Gaudet, Michael Livstone, Paul Thomas, The Reference Genome Project",
                "id": "GO_REF:0000033",
                "is_obsolete": True
            }
        }
    )

    test_result = qc.GoRule30().test(a, config)
    assert test_result.result_type == qc.ResultType.ERROR

    a[5] = "GO_PAINT:0000000"
    test_result = qc.GoRule30().test(a, config)
    assert test_result.result_type == qc.ResultType.ERROR

    a[5] = "FOO:123|GO_REF:0000033"
    test_result = qc.GoRule30().test(a, config)
    assert test_result.result_type == qc.ResultType.ERROR

    a[5] = "FOO:123"
    test_result = qc.GoRule30().test(a, config)
    assert test_result.result_type == qc.ResultType.PASS

def test_gorule36():
    a = ["blah"] * 16
    a[6] = "IBA"
    a[5] = "PMID:21873635"
    a[14] = "GO_Central"

    test_result = qc.GoRule37().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    a[6] = "BLA" # Rule doesn't apply
    test_result = qc.GoRule37().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    a[6] = "IBA"
    a[5] = "GO_REF:123"  # IBA, but wrong ref
    test_result = qc.GoRule37().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

    a[5] = "PMID:21873635"
    a[14] = "Pascale"  # IBA, but wrong assigned_by
    test_result = qc.GoRule37().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

def test_gorule39():
    a = ["blah"] * 16
    a[0] = "ComplexPortal"
    a[4] = "GO:0032991"

    test_result = qc.GoRule39().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

    a[0] = "FB"
    test_result = qc.GoRule39().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    a[0] = "ComplexPortal"
    a[4] = "GO:0000023"
    test_result = qc.GoRule39().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

def test_gorule42():
    a = ["blah"] * 16
    a[6] = "IKR"
    a[3] = "NOT"

    test_result = qc.GoRule42().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    a[6] = "BLA" # Not IKR so this rule is fine
    test_result = qc.GoRule42().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    a[6] = "IKR"
    a[3] = ""  # No NOT qualifier, so wrong
    test_result = qc.GoRule42().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

def test_gorule43():
    a = ["blah"] * 16
    a[5] = "GO_REF:0000024"
    a[6] = "ISO"

    config = assocparser.AssocParserConfig(
        goref_metadata={
            "goref-0000024": {
                "authors": "Pascale Gaudet, Michael Livstone, Paul Thomas, The Reference Genome Project",
                "id": "GO_REF:0000024",
                "evidence_codes": ["ECO:0000266"]
            }
        }
    )

    test_result = qc.GoRule43().test(a, config)
    assert test_result.result_type == qc.ResultType.PASS

    a[6] = "FOO"
    test_result = qc.GoRule43().test(a, config)
    assert test_result.result_type == qc.ResultType.WARNING

    a[6] = "ISO"
    a[5] = "FOO:123"
    test_result = qc.GoRule43().test(a, config)
    assert test_result.result_type == qc.ResultType.PASS

def test_gorule46():
    config = assocparser.AssocParserConfig(ontology=ontology)

    a = ["blah"] * 16
    a[1] = "SPAC25B8.17"
    a[4] = "GO:0051260" # Self-binding, yes
    a[7] = "SPAC25B8.17"

    test_result = qc.GoRule46().test(a, config)
    assert test_result.result_type == qc.ResultType.PASS

    a[7] = "BLAH123"
    test_result = qc.GoRule46().test(a, config)
    assert test_result.result_type == qc.ResultType.WARNING

    a[7] = "SPAC25B8.17|BLAH123"
    test_result = qc.GoRule46().test(a, config)
    assert test_result.result_type == qc.ResultType.PASS

    a[4] = "GO:0000123"
    # Not in a self-binding mode
    test_result = qc.GoRule46().test(a, config)
    assert test_result.result_type == qc.ResultType.PASS

    # Test no ontology should just pass
    a[4] = "GO:0051260"
    test_result = qc.GoRule46().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

def test_gorule50():
    a = ["blah"] * 16
    a[6] = "ISS"
    a[1] = "HELLO:123"
    a[7] = "HELLO:123"

    test_result = qc.GoRule50().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.WARNING

    a[1] = "BYE:567"
    test_result = qc.GoRule50().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    a[1] = "HELLO:123"
    a[6] = "BLA"
    # Not ISS, so fine to have repeated columns
    test_result = qc.GoRule50().test(a, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS



def test_all_rules():
    # pass
    config = assocparser.AssocParserConfig(
        ontology=ontology
    )
    a = make_annotation("GO:0006397", "ANY")
    a = ["blah"] * 16
    a[4] = "GO:0006397"
    a[6] = "ANY"
    a[13] = "20180330"

    test_results = qc.test_go_rules(a, config).all_results
    assert len(test_results.keys()) == 20
    assert test_results[qc.GoRules.GoRule26.value].result_type == qc.ResultType.PASS
    assert test_results[qc.GoRules.GoRule29.value].result_type == qc.ResultType.PASS


if __name__ == "__main__":
    pytest.main(args=["tests/test_qc.py"])
