from ontobio.io import assocparser
from ontobio.io.gpadparser import GpadParser
from ontobio.io import gafparser, gafgpibridge
from ontobio.io.gafparser import GafParser
from ontobio.io import GafWriter
from ontobio.io.assocwriter import GpadWriter
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory
from ontobio.model import association
from ontobio.rdfgen import relations
from ontobio.model.association import ConjunctiveSet, ExtensionUnit, Curie
from ontobio.ecomap import EcoMap

import tempfile
import logging
import pytest
import io
import json
import re
import yaml
ecomap = EcoMap()
ecomap.mappings()

POMBASE = "tests/resources/truncated-pombase.gaf"
POMBASE_GPAD = "tests/resources/truncated-pombase.gpad"
ONT = "tests/resources/go-truncated-pombase.json"
QGAF = "tests/resources/test-qualifiers.gaf"
ALT_ID_ONT = "tests/resources/obsolete.json"
ZFIN_GAF = "tests/resources/zfin_test_gaf.gaf"
OBSOLETE_ONT = "tests/resources/obsolete.json"


def test_skim_gaf():
    p = GafParser()
    p.config.ecomap = EcoMap()
    results = p.skim(open(POMBASE, "r"))
    assert len(results) == 370
    for r in results:
        print(str(r))
        (s, sn, o) = r
        assert o.startswith('GO:')
        assert s.startswith('PomBase:')


def test_skim_gaf_qualifiers():
    p = GafParser()
    p.config.ecomap = EcoMap()
    p.config.remove_double_prefixes = True
    results = p.skim(open(QGAF, "r"))
    for r in results:
        print(str(r))
        (s, sn, o) = r
        assert o.startswith('GO:')
        assert s.startswith('MGI:') or s.startswith('PomBase')
    assert len(results) == 5  # ensure NOTs are skipped

    p.config.exclude_relations = ['contributes_to', 'colocalizes_with']
    results = p.skim(open(QGAF, "r"))
    for r in results:
        (s, sn, o) = r
        assert o.startswith('GO:')
        assert s.startswith('MGI:') or s.startswith('PomBase')
    assert len(results) == 3 # ensure NOTs and excludes relations skipped


def test_one_line():
    p = GafParser(config=assocparser.AssocParserConfig(
        ontology=OntologyFactory().create("tests/resources/goslim_generic.json")))

    parsed = p.parse_line("PomBase	SPBC16D10.09	pcn1		GO:0009536	PMID:8663159	IDA		C	PCNA	pcn	protein	taxon:4896	20150326	PomBase")


def test_skim_gpad():
    p = GpadParser()
    p.config.ecomap = EcoMap()
    results = p.skim(open(POMBASE_GPAD, "r"))
    assert len(results) == 1984
    for r in results:
        print(str(r))
        (s, sn, o) = r
        assert o.startswith('GO:')
        assert s.startswith('PomBase:') or s.startswith('PR:')


def test_parse_gaf():
    parse_with(POMBASE, GafParser())


def test_parse_gpad():
    parse_with(POMBASE_GPAD, GpadParser())


def test_gaf_association_generator_header_report():
    p = GpadParser(config=assocparser.AssocParserConfig(group_metadata=yaml.load(open("tests/resources/mgi.dataset.yaml"),
                                                                                 Loader=yaml.FullLoader)))
    test_gaf_file = "tests/resources/test-qualifiers-2.2.gaf"
    assert len(p.report.header) == 0
    for a in p.association_generator(open(test_gaf_file, "r")):
        continue
    assert len(p.report.header) > 0
    print(p.report.header)

def parse_with(f, p):
    p.config.ecomap = EcoMap()
    is_gaf = f == POMBASE
    ont = OntologyFactory().create(ONT)

    if is_gaf:
        # only do ontology checking on GAF parse;
        # this is because ontology is made from GAF
        p.config.ontology = ont
    else:
        p.config.ontology = None

    results = p.parse(open(f, "r"), skipheader=True)
    print(p.report.to_markdown())
    r1 = results[0]
    # TODO: test datafile does not have ECOs yet!!
    assert ecomap.ecoclass_to_coderef(str(r1.evidence.type))[0] == 'ISO' or str(r1.evidence.type) == 'ECO:0000201'
    assert r1.evidence.with_support_from == [association.ConjunctiveSet([association.Curie.from_str('SGD:S000001583')])]
    assert r1.evidence.has_supporting_reference == [association.Curie.from_str('GO_REF:0000024')]

    if is_gaf:
        assert r1.subject.label == 'ypf1'
        assert association.ymd_str(r1.date, "") == '20150305'

    for r in results:
        #print(str(r))
        sid = r.subject.id
        prov = r.provided_by
        assert prov == 'PomBase' or prov == 'UniProt'
        assert r.object.id.namespace == "GO"
        assert sid.namespace == 'PomBase' or (not is_gaf and sid.namespace == 'PR')
        if is_gaf:
            assert str(r.subject.taxon) =='NCBITaxon:4896'

    # for m in p.report.messages:
    #     print("MESSAGE: {}".format(m))
    print("MESSAGES (sample): {}".format(p.report.messages[0:5]))
    # Messages that aren't about upgrading qualifiers in rule 59 should be 0
    assert len([msg for msg in p.report.messages if msg["rule"] != 59 and msg["rule"] != 27]) == 0
    # print(p.report.to_markdown())


def test_flag_invalid_id():
    ont = OntologyFactory().create(ONT)
    p = GafParser()
    p.config.ontology = ont
    p._validate_ontology_class_id("FAKE:1", assocparser.SplitLine("fake", [""]*17, taxon="foo"))
    assert len(p.report.messages) == 1


def test_no_flag_valid_id():
    ont = OntologyFactory().create(ONT)
    p = GafParser()
    p.config.ontology = ont
    p._validate_ontology_class_id("GO:0000785", assocparser.SplitLine("fake", [""]*17, taxon="foo"))
    assert len(p.report.messages) == 0


def test_convert_gaf_to_gpad():
    p = GafParser()
    p.config.ecomap = EcoMap()
    w = GpadWriter()
    p2 = GpadParser()
    convert(POMBASE, p, w, p2)


def convert(file, p, w, p2):
    assocs = p.parse(file, skipheader=True)
    outfile = tempfile.NamedTemporaryFile(mode='w', delete=False)
    w.file = outfile
    for a in assocs:
        w.write_assoc(a)
    outfile.close()
    assocs2 = p2.parse(outfile.name)
    for a in assocs2:
        print("REPARSED: {}".format(a))
    assert len(assocs) == len(assocs2)


def test_invalid_goid_in_gpad():
    # Note: this ontology is a subset of GO extracted using the GAF, not GPAD
    p = GpadParser()
    p.config.ontology = OntologyFactory().create(ONT)
    results = p.parse(open(POMBASE_GPAD, "r"), skipheader=True)

    # we expect errors since ONT is not tuned for the GPAD file
    # for m in p.report.messages:
    #     print("MESSAGE: {}".format(m))
    assert len(p.report.messages) > 500
    print(p.report.to_markdown())


def test_validate_go_idspaces():
    ont = OntologyFactory().create(ONT)
    p = GafParser()
    p.config.class_idspaces = ['FOOZ']
    assocs = p.parse(open(POMBASE, "r"), skipheader=True)
    for m in p.report.messages:
        print("MESSAGE: {}".format(m))
    assert len(assocs) == 0
    assert len(p.report.messages) > 1
    summary = p.report.to_report_json()
    assert summary['associations'] == 0
    assert summary['lines'] > 300
    print(p.report.to_markdown())

    # ensure config is not preserved
    p = GafParser()
    assert p.config.class_idspaces is None


def test_qualifiers_gaf():
    p = GafParser()
    assocs = p.parse(open(QGAF, "r"), skipheader=True)
    neg_assocs = [a for a in assocs if a.negated == True]
    assert len(neg_assocs) == 3
    for a in assocs:
        print('REL: {}'.format(str(a.relation)))

    assert len([a for a in assocs if str(a.relation) == 'RO:0002326']) == 1

    # For the space in `colocalizes with`
    assert len(list(filter(lambda e: e["obj"] == "colocalizes with", p.report.to_report_json()["messages"]["gorule-0000001"]))) == 1
    assert len(list(filter(lambda e: e["obj"] == "involved_in", p.report.to_report_json()["messages"]["gorule-0000001"]))) == 1


def test_gaf_2_1_unknown_qualifier():
    line = ["UniProtKB", "P0AFI2", "parC", "Contributes_to", "GO:0003916", "PMID:1334483", "IDA", "", "F", "", "", "gene", "taxon:83333", "20081208", "EcoliWiki"]
    parsed = gafparser.to_association(line)

    assert parsed.skipped is True
    assert parsed.report.to_report_json()["messages"]["gorule-0000001"][0]["type"] == parsed.report.INVALID_QUALIFIER


def test_qualifiers_gaf_2_2():

    p = GafParser()

    assocs = p.parse(open("tests/resources/test-qualifiers-2.2.gaf"), skipheader=True)
    # NOT by itself is not allowed
    assert len(list(filter(lambda e: e["obj"] == "NOT", p.report.to_report_json()["messages"]["gorule-0000001"]))) == 1
    assert len(list(filter(lambda e: e["obj"] == "contributes_to|enables", p.report.to_report_json()["messages"]["gorule-0000001"]))) == 1
    assert len([a for a in assocs if association.Curie.from_str("RO:0004035") in a.qualifiers]) == 1


def test_gaf_2_1_creates_cell_component_closure():
    ontology = OntologyFactory().create("tests/resources/goslim_generic.json")
    closure = gafparser.protein_complex_sublcass_closure(ontology)
    # "GO:1902494" as an example that should be in the set
    assert "GO:0005840" in closure

    p = GafParser(config=assocparser.AssocParserConfig(ontology=ontology))
    with open("tests/resources/pombase_single.gaf") as gaf:
        # First line will be version declaration, triggering closure computation
        p.parse_line(gaf.readline())

    assert "GO:0005840" in p.cell_component_descendants_closure


def test_gaf_2_1_qualifiers_upconvert():
    line = ["SGD", "S000000819", "AFG3", "", "GO:0005840", "PMID:8681382|SGD_REF:S000055187", "IMP", "", "P", "Mitochondrial inner membrane m-AAA protease component", "YER017C|AAA family ATPase AFG3|YTA10", "gene", "taxon:559292", "20170428", "SGD"]
    parsed = gafparser.to_association(line)
    assoc = parsed.associations[0]

    ontology = OntologyFactory().create("tests/resources/goslim_generic.json")
    p = GafParser(config=assocparser.AssocParserConfig(ontology=ontology))
    p.make_internal_cell_component_closure()

    assoc = p.upgrade_empty_qualifier(assoc)
    assert assoc.qualifiers[0] == association.Curie(namespace="BFO", identity="0000050")


def test_gaf_2_1_upconvert_in_parse():
    gaf = io.StringIO("!gaf-version: 2.1\nSGD\tS000000819\tAFG3\t\tGO:0005840\tPMID:8681382|SGD_REF:S000055187\tIMP\t\tP\tMitochondrial inner membrane m-AAA protease component\tYER017C|AAA family ATPase AFG3|YTA10\tgene\ttaxon:559292\t20170428\tSGD")
    ontology = OntologyFactory().create("tests/resources/goslim_generic.json")
    p = GafParser(config=assocparser.AssocParserConfig(ontology=ontology))

    # We're 2.1, qualifier blank, cell component term from above, ontology defined: should upgrade
    assocs = p.parse(gaf, skipheader=True)
    assert assocs[0].relation == association.Curie(namespace="BFO", identity="0000050")


def test_gaf_2_1_simple_terms():
    line = ["SGD", "S000000819", "AFG3", "", "GO:0006259", "PMID:8681382|SGD_REF:S000055187", "IMP", "", "P", "Mitochondrial inner membrane m-AAA protease component", "YER017C|AAA family ATPase AFG3|YTA10", "gene", "taxon:559292", "20170428", "SGD"]
    ontology = OntologyFactory().create("tests/resources/goslim_generic.json")
    p = GafParser(config=assocparser.AssocParserConfig(ontology=ontology))
    p.make_internal_cell_component_closure()

    parsed = gafparser.to_association(line)
    assoc = p.upgrade_empty_qualifier(parsed.associations[0])
    assert assoc.qualifiers[0] == association.Curie(namespace="RO", identity="0002264")

    line = ["SGD", "S000000819", "AFG3", "", "GO:0042393", "PMID:8681382|SGD_REF:S000055187", "IMP", "", "P",
            "Mitochondrial inner membrane m-AAA protease component", "YER017C|AAA family ATPase AFG3|YTA10", "gene",
            "taxon:559292", "20170428", "SGD"]
    ontology = OntologyFactory().create("tests/resources/goslim_generic.json")
    p = GafParser(config=assocparser.AssocParserConfig(ontology=ontology))
    p.make_internal_cell_component_closure()

    parsed = gafparser.to_association(line)
    assoc = p.upgrade_empty_qualifier(parsed.associations[0])
    assert assoc.qualifiers[0] == association.Curie(namespace="RO", identity="0002327")

    line = ["SGD", "S000000819", "AFG3", "", "GO:0005773", "PMID:8681382|SGD_REF:S000055187", "IMP", "", "P",
            "Mitochondrial inner membrane m-AAA protease component", "YER017C|AAA family ATPase AFG3|YTA10", "gene",
            "taxon:559292", "20170428", "SGD"]
    ontology = OntologyFactory().create("tests/resources/goslim_generic.json")
    p = GafParser(config=assocparser.AssocParserConfig(ontology=ontology))
    p.make_internal_cell_component_closure()

    parsed = gafparser.to_association(line)
    assoc = p.upgrade_empty_qualifier(parsed.associations[0])
    assert assoc.qualifiers[0] == association.Curie(namespace="RO", identity="0001025")


def test_upgrade_qualifiers_for_biological_process():
    line = ["SGD", "S000000819", "AFG3", "", "GO:0008150", "PMID:8681382|SGD_REF:S000055187", "IMP", "", "P",
            "Mitochondrial inner membrane m-AAA protease component", "YER017C|AAA family ATPase AFG3|YTA10", "gene",
            "taxon:559292", "20170428", "SGD"]
    ontology = OntologyFactory().create("tests/resources/goslim_generic.json")
    p = GafParser(config=assocparser.AssocParserConfig(ontology=ontology))
    p.make_internal_cell_component_closure()

    parsed = gafparser.to_association(line)
    assoc = p.upgrade_empty_qualifier(parsed.associations[0])
    assert assoc.qualifiers[0] == association.Curie(namespace="RO", identity="0002331")


def test_upgrade_qualifiers_for_cell_component():
    line = ["SGD", "S000000819", "AFG3", "", "GO:0008372", "PMID:8681382|SGD_REF:S000055187", "IMP", "", "P",
            "Mitochondrial inner membrane m-AAA protease component", "YER017C|AAA family ATPase AFG3|YTA10", "gene",
            "taxon:559292", "20170428", "SGD"]
    ontology = OntologyFactory().create("tests/resources/goslim_generic.json")
    p = GafParser(config=assocparser.AssocParserConfig(ontology=ontology))
    p.make_internal_cell_component_closure()

    parsed = gafparser.to_association(line)
    assoc = p.upgrade_empty_qualifier(parsed.associations[0])
    assert assoc.qualifiers[0] == association.Curie(namespace="RO", identity="0002432")


def test_default_gaf_version():
    p = GafParser()
    assocs = p.parse(open("tests/resources/test-qualifiers-no-version.gaf"), skipheader=True)
    assert p.version == "2.1"


def parse_with2(f, p):
    ont = OntologyFactory().create(ONT)

    p.config.ontology = ont
    assocs = p.parse(open(f, "r"), skipheader=True)
    neg_assocs = [a for a in assocs if a.negated == True]
    assert len(neg_assocs) == 3
    for a in assocs:
        print('REL: {}'.format(a.relation))
    assert len([a for a in assocs if str(a.relation) == relations.lookup_label('involved_in')]) == 1
    assert len([a for a in assocs if str(a.relation) == relations.lookup_label('contributes_to')]) == 1


def test_errors_gaf():
    config = assocparser.AssocParserConfig(
        ecomap=EcoMap()
    )
    p = GafParser(config=config)
    assocs = p.parse(open("tests/resources/errors.gaf", "r"), skipheader=True)
    msgs = p.report.messages
    print(json.dumps(p.report.to_report_json(), indent=4))
    # print("MESSAGES: {}".format(len(msgs)))
    n_invalid_idspace = 0
    for m in msgs:
        print("MESSAGE: {}".format(m))
        if m['type'] == assocparser.Report.INVALID_IDSPACE:
            n_invalid_idspace += 1
    assert len(msgs) == 13
    assert n_invalid_idspace == 1
    assert len(assocs) == 1

    w = GafWriter()
    w.write(assocs)
    for a in assocs:
        if a.object_extensions != []:
            # our test file has no ORs, so in DNF this is always the first
            xs = a.object_extensions[0].elements
            print(xs)
            for x in xs:

                print('X: {}'.format(x))
                # ensure that invalid expressions have been eliminated
                assert x.relation == association.Curie("BFO", "0000050")
                assert x.term == association.Curie.from_str('X:1')
            assert len(xs) == 1


def test_alt_id_repair():
    p = GafParser()
    ont = OntologyFactory().create(ALT_ID_ONT)
    p.config.ecomap = EcoMap()
    p.config.ontology = ont

    gaf = io.StringIO("SGD\tS000000819\tAFG3\t\tGO:1\tPMID:8681382|SGD_REF:S000055187\tIMP\t\tP\tMitochondrial inner membrane m-AAA protease component\tYER017C|AAA family ATPase AFG3|YTA10\tgene\ttaxon:559292\t20170428\tSGD")
    assocs = p.parse(gaf, skipheader=True)
    # GO:1 is obsolete, and has replaced by GO:0034622, so we should see that class ID.
    assert assocs[0].object.id == association.Curie.from_str("GO:2")

    gaf = io.StringIO("SGD\tS000000819\tAFG3\t\tGO:4\tPMID:8681382|SGD_REF:S000055187\tIMP\t\tP\tMitochondrial inner membrane m-AAA protease component\tYER017C|AAA family ATPase AFG3|YTA10\tgene\ttaxon:559292\t20170428\tSGD")
    assocs = p.parse(gaf, skipheader=True)
    # GO:4 is obsolete due to it being merged into GO:3
    assert assocs[0].object.id == association.Curie.from_str("GO:3")


def test_gorule_repair():
    config = assocparser.AssocParserConfig(
        ontology=OntologyFactory().create("tests/resources/goslim_generic.json"),
        rule_set=assocparser.RuleSet.ALL
    )
    p = GafParser(config=config)
    # Here this gaf line has the wrong aspect, and should be picked up by gorule 28
    gaf = io.StringIO("PomBase\tSPCC962.06c\tbpb1\t\tGO:0005634\tPMID:20970342\tIPI\t\tP\tKH and CC/hC domain splicing factor Bpb1\tsf1|ods3\tprotein\ttaxon:4896\t20110804\tPomBase\tpart_of(GO:0007137)")
    assocs = p.parse(gaf, skipheader=True)

    assert assocs[0].aspect == "C"
    assert len(p.report.to_report_json()["messages"]["gorule-0000028"]) == 1
    assert p.report.to_report_json()["messages"]["gorule-0000028"][0]["type"] == assocparser.Report.VIOLATES_GO_RULE


def test_bad_date():
    p = GafParser()
    assoc_result = p.parse_line("PomBase\tSPAC25B8.17\typf1\t\tGO:0000007\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:4896\tTODAY\tPomBase\tfoo(X:1)")
    assert assoc_result.skipped == True
    assert assoc_result.associations == []
    
def test_bad_gene_symbol():
    p = GafParser()
    assoc_result = p.parse_line("PomBase\tSPAC25B8.17\ta|pipeisnotallowed\t\tGO:0000007\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:4896\t20231110\tPomBase\tfoo(X:1)")
    assert assoc_result.skipped == True
    assert assoc_result.associations == []     
    
def test_bad_go_id():
    p = GafParser()
    assoc_result = p.parse_line("PomBase\tSPAC25B8.17\typf1\t\tINVALID:0000007\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:4896\t20231110\tPomBase\tfoo(X:1)")
    assert assoc_result.skipped == True
    assert assoc_result.associations == []    

def test_bad_taxon():
    p = GafParser()
    assoc_result = p.parse_line("PomBase\tSPAC25B8.17\typf1\t\tGO:0000007\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:1abc\t20231003\tPomBase\tfoo(X:1)")
    assert assoc_result.skipped == True
    assert assoc_result.associations == []

def test_subject_extensions():
    p = GafParser()
    assoc_result = p.parse_line("PomBase\tSPAC25B8.17\typf1\t\tGO:0000007\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:4896\t20181024\tPomBase\tpart_of(X:1)\tUniProtKB:P12345")
    assert len(assoc_result.associations[0].subject_extensions) == 1

    subject_extensions = assoc_result.associations[0].subject_extensions
    gene_product_form_id = subject_extensions[0].term
    assert gene_product_form_id == association.Curie.from_str("UniProtKB:P12345")


def test_bad_withfrom():
    p = GafParser()
    # With/from has no identity portion after the namespace
    assoc_result = p.parse_line("PomBase\tSPAC25B8.17\typf1\t\tGO:0000007\tGO_REF:0000024\tISO\tSGD:\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:4896\t20181024\tPomBase")
    assert assoc_result.associations == []
    assert p.report.to_report_json()["messages"]["gorule-0000001"][0]["obj"] == "SGD:"


def test_obsolete_replair_of_withfrom():
    p = GafParser(config=assocparser.AssocParserConfig(
        ontology=OntologyFactory().create(OBSOLETE_ONT)))
    assocs = p.parse(open(ZFIN_GAF, "r"), skipheader=True)
    assert assocs[0].evidence.with_support_from == [ConjunctiveSet(elements=[Curie(namespace='GO', identity='0005912')])]

    # Reset parser report
    p = GafParser(config=assocparser.AssocParserConfig(
        ontology=OntologyFactory().create(OBSOLETE_ONT)))
    p.version = "2.2"
    obsolete_no_replacement_line = "FB\tFBgn0003334\tScm\tlocated_in\tGO:0005634\tFB:FBrf0179383|PMID:15280237\tIC\tGO:0016458\tC\tSex comb on midleg\tCG9495|SCM|Sex Comb on Midleg|Sex Comb on the Midleg|Sex combs on midleg|Sex combs on midlegs|Su(z)302|l(3)85Ef|scm|sex comb on midleg\tprotein\ttaxon:7227\t20050203\tUniProt\t\t"
    assoc_result = p.parse_line(obsolete_no_replacement_line)
    assert assoc_result.associations == []
    assert p.report.to_report_json()["messages"]["gorule-0000020"][0]["obj"] == "GO:0016458"
    
    
def test_invalid_db_type():
    #gene_product gets mapped to gene_product
    line = ["UniProtKB", "P0AFI2", "parC", "", "GO:0003916", "PMID:1334483", "IDA", "", "F", "", "", "gene_product", "taxon:83333", "20081208", "EcoliWiki"]
    parsed = gafparser.to_association(line)
    assoc = parsed.associations[0]
    assert assoc.subject.type == [association.map_gp_type_label_to_curie('gene_product')]

    #protein gets mapped to protein
    line = ["UniProtKB", "P0AFI2", "parC", "", "GO:0003916", "PMID:1334483", "IDA", "", "F", "", "", "protein", "taxon:83333", "20081208", "EcoliWiki"]
    parsed = gafparser.to_association(line)
    assoc = parsed.associations[0]
    assert assoc.subject.type == [association.map_gp_type_label_to_curie('protein')]
    
    #Unhandled types get mapped to 'gene_product'
    line = ["UniProtKB", "P0AFI2", "parC", "", "GO:0003916", "PMID:1334483", "IDA", "", "F", "", "", "invalid_gene_product", "taxon:83333", "20081208", "EcoliWiki"]
    parsed = gafparser.to_association(line)
    assoc = parsed.associations[0]
    assert assoc.subject.type == [association.map_gp_type_label_to_curie('gene_product')]
    assert parsed.report.to_report_json()["messages"]["gorule-0000001"][0]["type"] == parsed.report.INVALID_SUBJECT_TYPE
    
    #'lnc_RNA' gets repaired to 'lncRNA'
    line = ["UniProtKB", "P0AFI2", "parC", "", "GO:0003916", "PMID:1334483", "IDA", "", "F", "", "", "lnc_RNA", "taxon:83333", "20081208", "EcoliWiki"]
    parsed = gafparser.to_association(line)
    assoc = parsed.associations[0]
    assert assoc.subject.type == [association.map_gp_type_label_to_curie('lncRNA')]                
    assert parsed.report.to_report_json()["messages"]["gorule-0000001"][0]["type"] == parsed.report.INVALID_SUBJECT_TYPE
    
 

def test_subject_extensions_bad_curie():
    """
    Offending field is `GDP_bound`
    """
    p = GafParser()
    assoc_result = p.parse_line("PomBase\tSPBC1289.03c\tspi1\t\tGO:0005515\tPMID:18422602\tIPI\tPomBase:SPAC25A8.01c\tF\tRan GTPase Spi1\t\tprotein\ttaxon:4896\t20080718\tPomBase\t\tGDP_bound")
    assert assoc_result.associations == []
    assert assoc_result.skipped == True
    assert len(p.report.to_report_json()["messages"]["gorule-0000001"]) == 1
    assert p.report.to_report_json()["messages"]["gorule-0000001"][0]["type"] == p.report.INVALID_ID
    assert p.report.to_report_json()["messages"]["gorule-0000001"][0]["obj"] == "GDP_bound"
    print(json.dumps(p.report.to_report_json(), indent=4))


def test_object_extensions():
    p = GafParser()
    assoc_result = p.parse_line("PomBase\tSPAC25B8.17\typf1\t\tGO:0000007\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:4896\t20181024\tPomBase\tpart_of(X:1)\tUniProtKB:P12345")
    print(p.report.to_markdown())
    assert len(assoc_result.associations[0].object_extensions) > 0
    object_extensions = [
        association.ConjunctiveSet([
            association.ExtensionUnit(association.Curie("BFO", "0000050"), association.Curie("X", "1"))
        ])
    ]
    assert assoc_result.associations[0].object_extensions == object_extensions


def test_object_extensions_error():
    p = GafParser()
    assoc_result = p.parse_line("PomBase\tSPAC25B8.17\typf1\t\tGO:0000007\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:4896\t20181024\tPomBase\tpart_of(X)\tUniProtKB:P12345")
    assert len(p.report.to_report_json()["messages"]["gorule-0000001"]) == 1


def test_obsolete_replair_of_extensions():
    p = GafParser(config=assocparser.AssocParserConfig(
        ontology=OntologyFactory().create(OBSOLETE_ONT))) 
    assoc_result = p.parse_line("ZFIN\tZDB-GENE-980526-362\tctnnb1\t\tGO:0007155\tPMID:15494018\tIC\tGO:0005913\tP\tcatenin (cadherin-associated protein), beta 1\tctnnb|id:ibd2058|wu:fb73e10|wu:fi81c06|wu:fk25h01\tprotein_coding_gene\ttaxon:7955\t20041026\tZFIN\tpart_of(GO:0005913)\tUniProtKB:P12345")
    print(p.report.to_markdown())
    assert len(assoc_result.associations[0].object_extensions) > 0
    object_extensions = [
        association.ConjunctiveSet([
            association.ExtensionUnit(association.Curie("BFO", "0000050"), association.Curie("GO", "0005912"))
        ])
    ]
    assert assoc_result.associations[0].object_extensions == object_extensions
    
    #Reset the report
    p = GafParser(config=assocparser.AssocParserConfig(
        ontology=OntologyFactory().create(OBSOLETE_ONT))) 
    assoc_result = p.parse_line("ZFIN\tZDB-GENE-980526-362\tctnnb1\t\tGO:0007155\tPMID:15494018\tIC\tGO:0005912\tP\tcatenin (cadherin-associated protein), beta 1\tctnnb|id:ibd2058|wu:fb73e10|wu:fi81c06|wu:fk25h01\tprotein_coding_gene\ttaxon:7955\t20041026\tZFIN\tpart_of(GO:0005913)|part_of(GO:0016458)\tUniProtKB:P12345")
    print(p.report.to_markdown())
    assert assoc_result.associations == []
    assert p.report.to_report_json()["messages"]["gorule-0000020"][0]["obj"] == "GO:0016458"    
    assert p.report.to_report_json()["messages"]["gorule-0000020"][1]["obj"] == "GO:0005913"
    
    #Reset the report
    p = GafParser(config=assocparser.AssocParserConfig(
        ontology=OntologyFactory().create(OBSOLETE_ONT))) 
    assoc_result = p.parse_line("ZFIN\tZDB-GENE-980526-362\tctnnb1\t\tGO:0007155\tPMID:15494018\tIC\tGO:0005912\tP\tcatenin (cadherin-associated protein), beta 1\tctnnb|id:ibd2058|wu:fb73e10|wu:fi81c06|wu:fk25h01\tprotein_coding_gene\ttaxon:7955\t20041026\tZFIN\tpart_of(GO:0005913)|part_of(GO:0007155),occurs_in(Y:1)\tUniProtKB:P12345")
    print(p.report.to_markdown())
    assert len(assoc_result.associations[0].object_extensions) > 0
    object_extensions = [
        association.ConjunctiveSet([association.ExtensionUnit(association.Curie("BFO", "0000050"), association.Curie("GO", "0005912"))]),
        association.ConjunctiveSet([association.ExtensionUnit(association.Curie("BFO", "0000050"), association.Curie("GO", "0007155")),association.ExtensionUnit(association.Curie("BFO", "0000066"), association.Curie("Y", "1"))])        
    ]
    assert assoc_result.associations[0].object_extensions == object_extensions    
    
    #Reset the report
    p = GafParser(config=assocparser.AssocParserConfig(
        ontology=OntologyFactory().create(OBSOLETE_ONT)))
    assoc_result = p.parse_line("ZFIN\tZDB-GENE-980526-362\tctnnb1\t\tGO:0007155\tPMID:15494018\tIC\tGO:0005912\tP\tcatenin (cadherin-associated protein), beta 1\tctnnb|id:ibd2058|wu:fb73e10|wu:fi81c06|wu:fk25h01\tprotein_coding_gene\ttaxon:7955\t20041026\tZFIN\tpart_of(GO:0016458)\tUniProtKB:P12345")
    print(p.report.to_markdown())
    assert assoc_result.associations == []
    assert p.report.to_report_json()["messages"]["gorule-0000020"][0]["obj"] == "GO:0016458"    
    

def test_factory():
    afa = AssociationSetFactory()
    ont = OntologyFactory().create(ONT)
    aset = afa.create_from_file(POMBASE, ontology=ont, skim=False)

    found = 0
    for s in aset.subjects:
        print('{} {}'.format(s, aset.label(s)))
        for c in aset.annotations(s):
            print('  {} {}'.format(c, ont.label(c)))
            for a in aset.associations(s, c):
                e = a['evidence']
                print('    {} {} {}'.format(e['type'], e['with_support_from'], e['has_supporting_reference']))
                if s == 'PomBase:SPBC2D10.10c' and c == 'GO:0005730':
                    if e['type'] == 'ISO':
                        if e['with_support_from'] == ['SGD:S000002172'] and e['has_supporting_reference'] == ['GO_REF:0000024']:
                            found +=1
                            logging.info('** FOUND: {}'.format(a))
                    if e['type'] == 'IDA':
                        if e['has_supporting_reference'] == ['PMID:16823372']:
                            found +=1
                            logging.info('** FOUND: {}'.format(a))

    assert len(aset.associations_by_subj) > 0
    assert found == 2
    
def test_id_syntax():
    database_id_syntax_lookups = {}
    go_types = {}
    pattern = '\\d{7}'
    go_types['molecular_function'] = re.compile(pattern)
    go_types['biological_process'] = re.compile(pattern)
    go_types['cellular_component'] = re.compile(pattern)      
    database_id_syntax_lookups['GO'] = go_types
    
    pmid_types = {}
    pmid_types['entity'] = re.compile('[0-9]+')
    database_id_syntax_lookups['PMID'] = pmid_types
    
    pombase_types = {}
    pombase_types['entity'] = re.compile('S\\w+(\\.)?\\w+(\\.)?')
    database_id_syntax_lookups['PomBase'] = pombase_types
    
    wb_ref_types = {}
    database_id_syntax_lookups['WB_REF'] = wb_ref_types
    
    mgi_types = {}
    mgi_types['entity'] = re.compile('MGI:[0-9]{5,}')
    database_id_syntax_lookups['MGI'] = mgi_types
        
    p = GafParser(config=assocparser.AssocParserConfig(
        ontology=OntologyFactory().create(ONT), db_type_name_regex_id_syntax=database_id_syntax_lookups))

    assoc_result = p.parse_line("PomBase\tSPBC1289.03c\tspi1\t\tGO:0005515\tPMID:18422602\tIPI\tPomBase:SPAC25A8.01c\tF\tRan GTPase Spi1\t\tprotein\ttaxon:4896\t20080718\tPomBase\t")
    assert len(assoc_result.associations) == 1
    assert assoc_result.skipped == False
    messages = p.report.to_report_json()["messages"]
    assert "gorule-0000027" not in messages
    
    assoc_result = p.parse_line("PomBase\tSPBC1289.03c\tspi1\t\tGO:0005515\tWB_REF:WBPaper00006408|PMID:18422602\tIPI\tPomBase:SPAC25A8.01c\tF\tRan GTPase Spi1\t\tprotein\ttaxon:4896\t20080718\tPomBase\t")
    assert len(assoc_result.associations) == 1
    assert assoc_result.skipped == False
    messages = p.report.to_report_json()["messages"]
    assert "gorule-0000027" not in messages
    
    assoc_result = p.parse_line("PomBase\tSPBC1289.03c\tspi1\t\tGO:0005515\tWB_REF:WBPaper00006408|PMID:18422602\tIPI\tMGI:MGI:1298204\tF\tRan GTPase Spi1\t\tprotein\ttaxon:4896\t20080718\tPomBase\t")
    assert len(assoc_result.associations) == 1
    assert assoc_result.skipped == False
    messages = p.report.to_report_json()["messages"]
    assert "gorule-0000027" not in messages        

    p = GafParser(config=assocparser.AssocParserConfig(
        ontology=OntologyFactory().create(ONT), db_type_name_regex_id_syntax=database_id_syntax_lookups))
    assoc_result = p.parse_line("PomBase\tSPBC1289.03c\tspi1\t\tGO:0005515\tPMID:PMID:18422602\tIPI\tPomBase:SPAC25A8.01c\tF\tRan GTPase Spi1\t\tprotein\ttaxon:4896\t20080718\tPomBase\t")
    assert len(assoc_result.associations) == 1
    assert assoc_result.skipped == False
    messages = p.report.to_report_json()["messages"]
    assert len(messages["gorule-0000027"]) == 1
    assert messages["gorule-0000027"][0]["obj"] == "PMID:PMID:18422602" 
    
    p = GafParser(config=assocparser.AssocParserConfig(
        ontology=OntologyFactory().create(ONT), db_type_name_regex_id_syntax=database_id_syntax_lookups))
    assoc_result = p.parse_line("PomBase\tSPBC1289.03c\tspi1\t\tGO:0005515\tPMID:0.\tIPI\tPomBase:SPAC25A8.01c\tF\tRan GTPase Spi1\t\tprotein\ttaxon:4896\t20080718\tPomBase\t")
    assert len(assoc_result.associations) == 1
    assert assoc_result.skipped == False
    messages = p.report.to_report_json()["messages"]
    assert len(messages["gorule-0000027"]) == 1
    assert messages["gorule-0000027"][0]["obj"] == "PMID:0."

    p = GafParser(config=assocparser.AssocParserConfig(
        ontology=OntologyFactory().create(ONT), db_type_name_regex_id_syntax=database_id_syntax_lookups))
    assoc_result = p.parse_line("PomBase\tSPBC1289.03c\tspi1\t\tGO:0005515\tPMID:x18422602\tIPI\tPomBase:SPAC25A8.01c\tF\tRan GTPase Spi1\t\tprotein\ttaxon:4896\t20080718\tPomBase\t")
    assert len(assoc_result.associations) == 1
    assert assoc_result.skipped == False
    messages = p.report.to_report_json()["messages"]
    assert len(messages["gorule-0000027"]) == 1
    assert messages["gorule-0000027"][0]["obj"] == "PMID:x18422602"

    p = GafParser(config=assocparser.AssocParserConfig(
        ontology=OntologyFactory().create(ONT), db_type_name_regex_id_syntax=database_id_syntax_lookups))
    assoc_result = p.parse_line("PomBase\tSPBC1289.03c\tspi1\t\tGO:0005515\tBLA:18422602\tIPI\tPomBase:SPAC25A8.01c\tF\tRan GTPase Spi1\t\tprotein\ttaxon:4896\t20080718\tPomBase\t")
    assert len(assoc_result.associations) == 1
    assert assoc_result.skipped == False
    messages = p.report.to_report_json()["messages"]    
    assert len(messages["gorule-0000027"]) == 1
    assert messages["gorule-0000027"][0]["obj"] == "BLA:18422602" 

    p = GafParser(config=assocparser.AssocParserConfig(
        ontology=OntologyFactory().create(ONT), db_type_name_regex_id_syntax=database_id_syntax_lookups))    
    assoc_result = p.parse_line("PomBase\tSPBC1289.03c\tspi1\t\tGO:0005515\tWB_REF:WBPaper00006408|PMID:18422602\tIPI\tMGI:1298204\tF\tRan GTPase Spi1\t\tprotein\ttaxon:4896\t20080718\tPomBase\t")
    assert len(assoc_result.associations) == 1
    assert assoc_result.skipped == False
    messages = p.report.to_report_json()["messages"]
    assert len(messages["gorule-0000027"]) == 1
    assert messages["gorule-0000027"][0]["obj"] == "MGI:1298204"  


def test_gaf_gpi_bridge():
    gaf = ["MGI", "MGI:1923503", "0610006L08Rik", "enables", "GO:0003674", "MGI:MGI:2156816|GO_REF:0000015", "ND", "",
           "F", "RIKEN cDNA 0610006L08 gene", "", "gene", "taxon:10090", "20120430", "MGI", "", ""]
    association = gafparser.to_association(gaf, qualifier_parser=assocparser.Qualifier2_2()).associations[0]
    bridge = gafgpibridge
    entity = bridge.convert_association(association)
    assert entity.get("type") == ["gene"]


if __name__ == "__main__":
    pytest.main(args=["tests/test_gafparser.py::test_parse_gaf"])
