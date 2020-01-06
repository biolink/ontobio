import pytest
import datetime

from ontobio.io import qc
from ontobio.io import gaference
from ontobio.io import assocparser
from ontobio.io import gafparser
from ontobio import ontol_factory

import copy

ontology = ontol_factory.OntologyFactory().create("tests/resources/goslim_generic.json")

def make_annotation(goid, evidence):
    annotation = ["blah", "blah", "blah", "blah", goid, "blah", evidence, "blah", "blah", "blah", "blah", "blah", "blah", "blah", "blah"]
    return annotation

def test_qc_result():
    assert qc.result(True, qc.FailMode.HARD) == qc.ResultType.PASS
    assert qc.result(False, qc.FailMode.HARD) == qc.ResultType.ERROR
    assert qc.result(False, qc.FailMode.SOFT) == qc.ResultType.WARNING

def test_go_rule02():
    a = ["blah"] * 15
    a[3] = "NOT"
    a[4] = "GO:0005515"
    a[8] = "F"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule02().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.negated = False
    test_result = qc.GoRule02().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    assoc.negated = True
    assoc.object.id = "GO:0003674"
    test_result = qc.GoRule02().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule_06():
    a = ["blah"] * 15
    a[3] = ""
    a[4] = "GO:0005575" # Cellular component
    a[6] = "HEP"
    a[8] = "C"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule06().test(assoc, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.ERROR

    assoc.aspect = "P"
    assoc.object.id = "GO:0008150"
    test_result = qc.GoRule06().test(assoc, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.type = "ECO:0000501"
    test_result = qc.GoRule06().test(assoc, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule_07():
    a = ["blah"] * 15
    a[3] = ""
    a[4] = "GO:0003824"
    a[6] = "IPI"
    a[8] = "F"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule07().test(assoc, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.object.id = "GO:1234567"
    test_result = qc.GoRule07().test(assoc, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

    assoc.object.id = "GO:0003824"
    assoc.evidence.type = "ECO:0000501" # Not IPI
    test_result = qc.GoRule07().test(assoc, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule08():
    a = ["blah"] * 15
    a[3] = ""
    a[4] = "GO:0006810" # do not annotate
    a[6] = "IEA"
    a[8] = "P"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule08().test(assoc, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.evidence.type = "ECO:0000305"
    test_result = qc.GoRule08().test(assoc, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.object.id = "GO:0007049" # do not manually annotate
    # evidence is IC, non IEA
    test_result = qc.GoRule08().test(assoc, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.evidence.type = "ECO:0000501" #IEA
    # IEA, but on not manual, so should pass
    test_result = qc.GoRule08().test(assoc, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

    assoc.object.id = "GO:0034655" # neither
    assoc.evidence.type = "ECO:0000305"
    test_result = qc.GoRule08().test(assoc, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule11():
    a = ["blah"] * 15
    a[3] = ""
    a[4] = "GO:0003674"
    a[6] = "ND"
    a[8] = "F"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule11().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    # Bad GO ID
    a = ["blah"] * 15
    a[3] = ""
    a[4] = "GO:1234567"
    a[6] = "ND"
    a[8] = "F"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule11().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

    # Not ND and not Root
    a[3] = ""
    a[4] = "GO:1234567"
    a[6] = "IEA"
    a[8] = "F"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule11().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    # Root, but not ND
    a = ["blah"] * 15
    a[3] = ""
    a[4] = "GO:0003674"
    a[6] = "IEA"
    a[8] = "F"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule11().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

def test_go_rules_13():

    a = ["PomBase", "SPBC11B10.09", "cdc2", "", "GO:0007275", "PMID:21873635", "IBA", "PANTHER:PTN000623979|TAIR:locus:2099478", "P", "Cyclin-dependent kinase 1", "UniProtKB:P04551|PTN000624043", "protein", "taxon:284812", "20170228", "GO_Central", "", ""]
    assoc = gafparser.to_association(a).associations[0]
    gaferences = gaference.load_gaferencer_inferences_from_file("tests/resources/test.inferences.json")
    test_result = qc.GoRule13().test(assoc, assocparser.AssocParserConfig(annotation_inferences=gaferences))
    assert test_result.result_type == qc.ResultType.WARNING

def test_go_rules_15():

    a = ["blah"] * 15
    a[3] = ""
    a[4] = "GO:0044419"
    a[6] = "IEA"
    a[8] = "P"
    a[12] = "taxon:123|taxon:456"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule15().test(assoc, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

    assoc.object.id = "GO:1234567"
    test_result = qc.GoRule15().test(assoc, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.object.id = "GO:0044215"
    assoc.object.id = "NCBITaxon:123"
    assoc.interacting_taxon = None # This is the important part, no interacting taxon
    test_result = qc.GoRule15().test(assoc, assocparser.AssocParserConfig(ontology=ontology))
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule_16():
    # No GO term w/ID
    a = ["blah"] * 15
    a[3] = ""
    a[4] = "GO:1234567"
    a[6] = "IC"
    a[7] = "BLAH:12345"
    a[8] = "P"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule16().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

    # withfrom has GO term
    assoc.evidence.with_support_from = ["GO:0023456"]

    test_result = qc.GoRule16().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    # Pipe
    assoc.evidence.with_support_from = ["GO:0012345", "BLAH:54321"]

    test_result = qc.GoRule16().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    # Empty withfrom
    assoc.evidence.with_support_from = []

    test_result = qc.GoRule16().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

    # Not IC
    assoc.evidence.type = "ECO:0000501"
    assoc.evidence.with_support_from = ["BLAH:5555555", "FOO:999999"]

    test_result = qc.GoRule16().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS


def test_go_rule_17():
    # IDA with anything in withfrom
    a = ["blah"] * 15
    a[3] = ""
    a[6] = "IDA"
    a[7] = "BLAH:12345"
    a[8] = "P"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule17().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.WARNING

    # Nothing in withfrom, passes
    assoc.evidence.with_support_from = []
    test_result = qc.GoRule17().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule_18():
    # IDA with nothing in withfrom
    a = ["blah"] * 15
    a[3] = ""
    a[6] = "IPI"
    a[7] = ""
    a[8] = "P"
    assoc = gafparser.to_association(a).associations[0]
    assoc.evidence.with_support_from = []

    test_result = qc.GoRule18().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.WARNING

    # Something in withfrom, passes
    assoc.evidence.with_support_from = ["BLAH:12345"]
    test_result = qc.GoRule18().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

def test_go_rule26():

    config = assocparser.AssocParserConfig(
        ontology=ontology,
        paint=True
    )
    a = make_annotation("GO:BLAHBLAH", "IBA")
    a[8] = "P"
    a[3] = ""
    assoc = gafparser.to_association(a).associations[0]
    # Pass due to IBA in paint
    test_result = qc.GoRule26().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

    config = assocparser.AssocParserConfig(
        ontology=ontology,
        paint=False
    )
    a = make_annotation("GO:BLAHBLAH", "IPI")
    a[8] = "P"
    a[3] = ""
    assoc = gafparser.to_association(a).associations[0]
    # Pass due to non IBA
    test_result = qc.GoRule26().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

    config = assocparser.AssocParserConfig(
        ontology=ontology,
        paint=False
    )
    a = make_annotation("GO:BLAHBLAH", "IBA")
    a[8] = "P"
    a[3] = ""
    assoc = gafparser.to_association(a).associations[0]
    # Pass due to non IBA
    test_result = qc.GoRule26().test(assoc, config)
    assert test_result.result_type == qc.ResultType.ERROR

def test_go_rule28():

    config = assocparser.AssocParserConfig(
        ontology=ontology
    )

    a = ["blah"] * 15
    a[3] = ""
    a[4] = "GO:0005975"
    a[8] = "P"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule28().test(assoc, config)

    assert test_result.result_type == qc.ResultType.PASS
    assert test_result.result == assoc

    a = ["blah"] * 15
    a[3] = ""
    a[4] = "GO:0005975"
    a[8] = "C"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule28().test(assoc, config)

    assert test_result.result_type == qc.ResultType.WARNING
    fixed_assoc = copy.deepcopy(assoc)
    fixed_assoc.aspect = "P"
    assert test_result.result == fixed_assoc
    assert test_result.message == "Found violation of: `Aspect can only be one of C, P, F` but was repaired"

def test_go_rule29():
    a = ["blah"] * 15
    a[3] = ""
    a[6] = "IEA"
    a[8] = "P"
    a[13] = "19901111" # Nov 11, 1990, more than a year old
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule29().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

    assoc.evidence.type = "ECO:0000305" #Not IEA

    test_result = qc.GoRule29().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    now = datetime.datetime.now()
    six_months_ago = now - datetime.timedelta(days=180)
    assoc.date = six_months_ago.strftime("%Y%m%d")
    assoc.evidence.type = "ECO:0000501"

    test_result = qc.GoRule29().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

def test_gorule30():
    a = ["blah"] * 15
    a[3] = ""
    a[5] = "GO_REF:0000033"
    a[8] = "P"
    assoc = gafparser.to_association(a).associations[0]

    config = assocparser.AssocParserConfig(
        goref_metadata={
            "goref-0000033": {
                "authors": "Pascale Gaudet, Michael Livstone, Paul Thomas, The Reference Genome Project",
                "id": "GO_REF:0000033",
                "is_obsolete": True
            }
        }
    )

    test_result = qc.GoRule30().test(assoc, config)
    assert test_result.result_type == qc.ResultType.ERROR

    assoc.evidence.has_supporting_reference = ["GO_PAINT:0000000"]
    test_result = qc.GoRule30().test(assoc, config)
    assert test_result.result_type == qc.ResultType.ERROR

    assoc.evidence.has_supporting_reference = ["FOO:123", "GO_REF:0000033"]
    test_result = qc.GoRule30().test(assoc, config)
    assert test_result.result_type == qc.ResultType.ERROR

    assoc.evidence.has_supporting_reference = ["FOO:123"]
    test_result = qc.GoRule30().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

def test_gorule37():
    a = ["blah"] * 15
    a[3] = ""
    a[6] = "IBA"
    a[5] = "PMID:21873635"
    a[8] = "P"
    a[14] = "GO_Central"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule37().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.type = "ECO:0000305" # Rule doesn't apply, not IBA
    test_result = qc.GoRule37().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.type = "ECO:0000318"
    assoc.evidence.has_supporting_reference = ["GO_REF:123"]  # IBA, but wrong ref
    test_result = qc.GoRule37().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

    assoc.evidence.has_supporting_reference = ["PMID:21873635"]
    assoc.provided_by = "Pascale"  # IBA, but wrong assigned_by
    test_result = qc.GoRule37().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

def test_gorule39():
    a = ["blah"] * 15
    a[0] = "ComplexPortal"
    a[3] = ""
    a[4] = "GO:0032991"
    a[8] = "C"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule39().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

    assoc.subject.id = "FB:1234"
    test_result = qc.GoRule39().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    assoc.subject.id = "ComplexPortal:12345"
    assoc.object.id = "GO:0000023"
    test_result = qc.GoRule39().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

def test_gorule42():
    a = ["blah"] * 15
    a[3] = "NOT"
    a[6] = "IKR"
    a[8] = "P"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule42().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.type = "ECO:0000305" # Not IKR so this rule is fine
    test_result = qc.GoRule42().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.type = "ECO:0000320"
    assoc.negated = False  # Not negated, so wrong
    test_result = qc.GoRule42().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.ERROR

def test_gorule43():
    a = ["blah"] * 15
    a[3] = ""
    a[5] = "GO_REF:0000024"
    a[6] = "ISO"
    a[8] = "P"
    assoc = gafparser.to_association(a).associations[0]

    config = assocparser.AssocParserConfig(
        goref_metadata={
            "goref-0000024": {
                "authors": "Pascale Gaudet, Michael Livstone, Paul Thomas, The Reference Genome Project",
                "id": "GO_REF:0000024",
                "evidence_codes": ["ECO:0000266"]
            }
        }
    )

    test_result = qc.GoRule43().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.type = "ECO:0000501"
    test_result = qc.GoRule43().test(assoc, config)
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.evidence.type = "ECO:0000266"
    assoc.evidence.has_supporting_reference = "FOO:123"
    test_result = qc.GoRule43().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

def test_gorule46():
    config = assocparser.AssocParserConfig(ontology=ontology)

    a = ["blah"] * 15
    a[0] = "PomBase"
    a[1] = "SPAC25B8.17"
    a[3] = ""
    a[4] = "GO:0051260" # Self-binding, yes
    a[7] = "PomBase:SPAC25B8.17"
    a[8] = "P"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule46().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

    assoc.evidence.with_support_from = ["PomBase:BLAH123"]
    test_result = qc.GoRule46().test(assoc, config)
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.evidence.with_support_from = ["PomBase:SPAC25B8.17", "PomBase:BLAH123"]
    test_result = qc.GoRule46().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

    assoc.object.id = "GO:0000123"
    # Not in a self-binding mode
    test_result = qc.GoRule46().test(assoc, config)
    assert test_result.result_type == qc.ResultType.PASS

    # Test no ontology should just pass
    assoc.object.id = "GO:0051260"
    test_result = qc.GoRule46().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

def test_gorule50():
    a = ["blah"] * 15
    a[0] = "HELLO"
    a[1] = "123"
    a[3] = ""
    a[6] = "ISS"
    a[7] = "HELLO:123"
    a[8] = "P"
    assoc = gafparser.to_association(a).associations[0]

    test_result = qc.GoRule50().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.WARNING

    assoc.subject.id = "BYE:567"
    test_result = qc.GoRule50().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS

    a[1] = "HELLO:123"
    a[6] = "ECO:0000501"
    # Not ISS, so fine to have repeated columns
    test_result = qc.GoRule50().test(assoc, assocparser.AssocParserConfig())
    assert test_result.result_type == qc.ResultType.PASS



def test_all_rules():
    # pass
    config = assocparser.AssocParserConfig(
        ontology=ontology
    )
    a = ["blah"] * 15
    a[3] = ""
    a[4] = "GO:0006397"
    a[6] = "ISS"
    a[8] = "P"
    a[13] = "20180330"
    assoc = gafparser.to_association(a).associations[0]

    test_results = qc.test_go_rules(assoc, config).all_results
    assert len(test_results.keys()) == 20
    assert test_results[qc.GoRules.GoRule26.value].result_type == qc.ResultType.PASS
    assert test_results[qc.GoRules.GoRule29.value].result_type == qc.ResultType.PASS


if __name__ == "__main__":
    pytest.main(args=["tests/test_qc.py"])
