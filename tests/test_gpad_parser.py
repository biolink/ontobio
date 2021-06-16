from ontobio.io.gpadparser import GpadParser, to_association
from ontobio.io import assocparser
from ontobio.model import association
from ontobio.model.association import ConjunctiveSet, ExtensionUnit, Curie
from ontobio.ontol_factory import OntologyFactory

import yaml

POMBASE = "tests/resources/truncated-pombase.gpad"

def test_skim():
    p = GpadParser()
    results = p.skim(open(POMBASE,"r"))
    print(str(results))


def test_parse():
    p = GpadParser(config=assocparser.AssocParserConfig(group_metadata=yaml.load(open("tests/resources/mgi.dataset.yaml"), Loader=yaml.FullLoader)))
    test_gpad_file = "tests/resources/mgi.test.gpad"
    results = p.parse(open(test_gpad_file, "r"))
    print(p.report.to_markdown())


def test_parse_1_2():
    report = assocparser.Report(group="unknown", dataset="unknown")
    vals = [
        "MGI",
        "MGI:1918911",
        "enables",
        "GO:0003674",
        "MGI:MGI:2156816|GO_REF:0000015",
        "ECO:0000307",
        "",
        "",
        "20100209",
        "MGI",
        "",
        "creation-date=2020-09-17|modification-date=2020-09-17|contributor-id=http://orcid.org/0000-0003-2689-5511"
    ]
    result = to_association(list(vals), report=report, version="1.2")
    assert result.skipped == 0
    assert len([m for m in result.report.messages if m["level"] == "ERROR"]) == 0
    assert len(result.associations) == 1

def test_parse_interacting_taxon():
    report = assocparser.Report(group="unknown", dataset="unknown")
    vals = [
        "MGI",
        "MGI:1918911",
        "enables",
        "GO:0003674",
        "MGI:MGI:2156816|GO_REF:0000015",
        "ECO:0000307",
        "",
        "taxon:5678",
        "20100209",
        "MGI",
        "",
        "creation-date=2020-09-17|modification-date=2020-09-17|contributor-id=http://orcid.org/0000-0003-2689-5511"
    ]
    result = to_association(list(vals), report=report, version="1.2")
    assert result.associations[0].interacting_taxon == Curie(namespace="NCBITaxon", identity="5678")

def test_duplicate_key_annot_properties():
    properties_str = "creation-date=2008-02-07|modification-date=2010-12-01|comment=v-KIND domain binding of Kndc1;MGI:1923734|contributor-id=http://orcid.org/0000-0003-2689-5511|contributor-id=http://orcid.org/0000-0003-3394-9805"
    prop_list = association.parse_annotation_properties(properties_str)
    contributor_ids = [value for key, value in prop_list if key == "contributor-id"]
    assert set(contributor_ids) == {"http://orcid.org/0000-0003-2689-5511", "http://orcid.org/0000-0003-3394-9805"}

def test_parse_2_0():
    version = "2.0"
    report = assocparser.Report(group="unknown", dataset="unknown")
    vals = [
        "MGI:MGI:1918911",
        "",
        "RO:0002327",
        "GO:0003674",
        "MGI:MGI:2156816|GO_REF:0000015",
        "ECO:0000307",
        "",
        "",
        "2020-09-17",
        "MGI",
        "",
        "creation-date=2020-09-17|modification-date=2020-09-17|contributor-id=http://orcid.org/0000-0003-2689-5511"
    ]
    result = to_association(list(vals), report=report, version=version)
    assert result.skipped == 0
    assert len([m for m in result.report.messages if m["level"] == "ERROR"]) == 0
    assert len(result.associations) == 1

    # Annotation_Extensions
    vals[10] = "BFO:0000066(CL:0000010),GOREL:0001004(CL:0000010)"
    result = to_association(list(vals), report=report, version=version)
    assert result.associations[0].object_extensions == [ConjunctiveSet([
            ExtensionUnit(Curie("BFO", "0000066"), Curie("CL", "0000010")),
            ExtensionUnit(Curie("GOREL", "0001004"), Curie("CL", "0000010"))
        ])]

    # With_or_From
    vals[6] = "PR:Q505B8|PR:Q8CHK4"
    result = to_association(list(vals), report=report, version=version)
    assert result.associations[0].evidence.with_support_from == [
        ConjunctiveSet([Curie("PR", "Q505B8")]),
        ConjunctiveSet([Curie("PR", "Q8CHK4")])
    ]

    # Interacting taxon - this example should fail
    vals[7] = "Staphylococcus aureus ; NCBITaxon:1280"
    result = to_association(list(vals), report=report, version=version)
    assert len([m for m in result.report.messages if m["level"] == "ERROR"]) > 0
    assert len(result.associations) == 0
    # Now test valid interacting taxon value
    vals[7] = "NCBITaxon:1280"
    result = to_association(list(vals), report=report, version=version)
    assert result.associations[0].interacting_taxon == Curie("NCBITaxon", "1280")

    # Confirm non-"MGI:MGI:" IDs will parse
    vals[0] = "WB:WBGene00001189"
    result = to_association(list(vals), report=report, version=version)
    assert result.associations[0].subject.id == Curie("WB", "WBGene00001189")

    # Test annotation property retrieval
    contributors = result.associations[0].annotation_property_values(property_key="contributor-id")
    assert set(contributors) == {"http://orcid.org/0000-0003-2689-5511"}

ALT_ID_ONT = "tests/resources/obsolete.json"

def test_aspect_fill_for_obsolete_terms():
    # Test null aspect on an obsolete term
    # GO:4 is obsolete and has no aspect (hasOBONamespace) in obsolete.json ontology
    # GO:3 is it's replacement term
    # Note that GPAD lines contain no aspect data
    vals = [
        "MGI",
        "MGI:105128",
        "involved_in",
        "GO:4",
        "PMID:25901318",
        "ECO:0000314",
        "",
        "",
        "20190517",
        "MGI",
        "",
        "contributor=http://orcid.org/0000-0002-9796-7693|model-state=production|noctua-model-id=gomodel:5c4605cc00004132"
    ]
    ont = OntologyFactory().create(ALT_ID_ONT)
    config = assocparser.AssocParserConfig(ontology=ont, rule_set=assocparser.RuleSet.ALL)
    parser = GpadParser(config=config)
    result = parser.parse_line("\t".join(vals))
    assoc = result.associations[0]

    assert assoc.object.id == Curie("GO", "3")  # GO:4 should be repaired to its replacement term, GO:3
    assert assoc.aspect == 'P'  # Aspect should not be empty
