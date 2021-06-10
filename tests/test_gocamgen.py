import pytest
from ontobio.io import assocparser
from ontobio.io.gpadparser import to_association
from ontobio.ontol_factory import OntologyFactory
from ontobio.rdfgen.gocamgen import collapsed_assoc, gocam_builder, gocamgen

GO_ONTO = OntologyFactory().create("tests/resources/go-binding.json")


def test_evidence_max_date():
    ev1 = gocamgen.GoCamEvidence(code="ECO:0000314", references=["PMID:12345"], date="2008-08-14")
    ev2 = gocamgen.GoCamEvidence(code="ECO:0000314", references=["PMID:12345"], date="2011-04-12")
    ev3 = gocamgen.GoCamEvidence(code="ECO:0000314", references=["PMID:12345"], date="2021-03-01")
    max_date = gocamgen.GoCamEvidence.max_date([ev1, ev2, ev3])
    assert max_date == "2021-03-01"


def test_get_with_froms():
    gpi_ents = gocam_builder.GoCamBuilder.parse_gpi(gpi_file="tests/resources/mgi2.test_entities.gpi")
    report = assocparser.Report(group="unknown", dataset="unknown")
    vals = [
        "MGI:MGI:1929608",
        "",
        "RO:0001025",
        "GO:0005515",
        "MGI:MGI:3028747|PMID:14627703",
        "ECO:0000353",
        "MGI:MGI:1915834",  # with/from
        "",
        "2004-04-30",
        "MGI",
        "",
        "creation-date=2004-04-30|modification-date=2004-04-30|contributor-id=http://orcid.org/0000-0002-9796-7693"
    ]
    result = to_association(list(vals), report=report, version="2.0")
    go_assoc = result.associations[0]
    ca_set = collapsed_assoc.CollapsedAssociationSet(GO_ONTO, gpi_ents)
    with_froms = ca_set.get_with_froms(go_assoc)
    assert len(with_froms) == 1 and \
           with_froms[0].header == ["MGI:MGI:1915834"] and \
           with_froms[0].line == ["MGI:MGI:1915834"]

    vals[6] = "MGI:MGI:1915834|FAKE:12345"
    result = to_association(list(vals), report=report, version="2.0")
    go_assoc = result.associations[0]
    ca_set = collapsed_assoc.CollapsedAssociationSet(GO_ONTO, gpi_ents)
    with_froms = ca_set.get_with_froms(go_assoc)
    # FAKE:12345 should be on line since not in GPI nor does it have same taxon as subject MGI:MGI:1929608
    assert len(with_froms) == 2 and \
           with_froms[0].header == ["MGI:MGI:1915834"] and \
           with_froms[0].line == ["MGI:MGI:1915834"] and \
           with_froms[1].header == [] and \
           with_froms[1].line == ["FAKE:12345"]

    # Test merging of same-header with/from values in different order
    ca_set = collapsed_assoc.CollapsedAssociationSet(GO_ONTO, gpi_ents)
    header1 = collapsed_assoc.GoAssocWithFrom(header=["MGI:MGI:1915834", "FAKE:12345"])
    header2 = collapsed_assoc.GoAssocWithFrom(header=["FAKE:12345", "MGI:MGI:1915834"])
    ca_set.find_or_create_collapsed_association(go_assoc, with_from=header1)
    ca_set.find_or_create_collapsed_association(go_assoc, with_from=header2)
    assert len(ca_set.collapsed_associations) == 1 and ca_set.collapsed_associations[0].with_froms == ["FAKE:12345", "MGI:MGI:1915834"]


def test_ref_picker():
    test_refs = [
        "GO_REF:0000483",
        "doi:485930",
        "WB_REF:WBPaper00003384",
        "PMID:9834189",
    ]
    result = gocamgen.ReferencePreference.pick(test_refs)
    assert result == "PMID:9834189"

    test_refs = [
        "GO_REF:0000483",
        "doi:485930",
        "PMID:9834189",
        "WB_REF:WBPaper00003384",
    ]
    result = gocamgen.ReferencePreference.pick(test_refs)
    assert result == "PMID:9834189"

    test_refs = ["ZFIN:ZDB-PUB-170709-3"]
    result = gocamgen.ReferencePreference.pick(test_refs)
    assert result == "ZFIN:ZDB-PUB-170709-3"
