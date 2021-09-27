import pytest
import datetime
from ontobio.io import assocparser
from ontobio.io.gpadparser import to_association
from ontobio.ontol_factory import OntologyFactory
from ontobio.rdfgen.gocamgen import collapsed_assoc, gocam_builder, gocamgen

GO_ONTO = OntologyFactory().create("tests/resources/go-binding.json")  # Placeholder ontology to instantiate models
GO_ONTO.merge([OntologyFactory().create("tests/resources/ro-gp2term-20210723.json")])  # Truncated RO
PARSER_CONFIG = assocparser.AssocParserConfig(ontology=GO_ONTO,
                                              gpi_authority_path="tests/resources/mgi2.test_entities.gpi")


def test_evidence_max_date():
    ev1 = gocamgen.GoCamEvidence(code="ECO:0000314", references=["PMID:12345"], date="2008-08-14")
    ev2 = gocamgen.GoCamEvidence(code="ECO:0000314", references=["PMID:12345"], date="2011-04-12")
    ev3 = gocamgen.GoCamEvidence(code="ECO:0000314", references=["PMID:12345"], date="2021-03-01")
    max_date = gocamgen.GoCamEvidence.sort_date([ev1, ev2, ev3])[-1]
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


def test_model_title():
    builder = gocam_builder.GoCamBuilder(parser_config=PARSER_CONFIG, modelstate="test")
    title = builder.model_title(gene_id="MGI:MGI:1915834")
    assert title == "1110020C17Rik (MGI:MGI:1915834)"

    # Fallback to gene_id as title if not found in GPI
    title = builder.model_title(gene_id="FAKE:1915834")
    assert title == "FAKE:1915834"


def test_model_dates():
    model_associations = []
    version = "2.0"
    report = assocparser.Report(group="unknown", dataset="unknown")
    vals = [
        "MGI:MGI:1915834",
        "",
        "RO:0002327",
        "GO:0003674",
        "MGI:MGI:2156816|GO_REF:0000015",
        "ECO:0000307",
        "",
        "",
        "2020-10-09",
        "MGI",
        "",
        "creation-date=2020-09-17|modification-date=2020-10-09|contributor-id=http://orcid.org/0000-0003-2689-5511"
    ]
    model_associations = model_associations + to_association(list(vals), report=report, version=version).associations

    # Different term, earlier creation-date
    vals[3], vals[11] = "GO:0016301", "creation-date=2011-12-13"
    model_associations = model_associations + to_association(list(vals), report=report, version=version).associations

    # Different term, no annotation properties
    vals[3], vals[11] = "GO:0001962", ""
    model_associations = model_associations + to_association(list(vals), report=report, version=version).associations

    builder = gocam_builder.GoCamBuilder(parser_config=PARSER_CONFIG, modelstate="test")
    model = builder.translate_to_model(gene="MGI:MGI:1915834", assocs=model_associations)
    assert model.date == "2020-10-09"
    assert model.creation_date == "2011-12-13"
    assert model.import_date == datetime.date.today().isoformat()
