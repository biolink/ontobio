from ontobio.io import assocparser
from ontobio.io.gpadparser import GpadParser
from ontobio.io.gafparser import GafParser
from ontobio.io import GafWriter
from ontobio.io.assocwriter import GpadWriter
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory

from ontobio.ecomap import EcoMap
import tempfile
import logging
import pytest
import io

POMBASE = "tests/resources/truncated-pombase.gaf"
POMBASE_GPAD = "tests/resources/truncated-pombase.gpad"
ONT = "tests/resources/go-truncated-pombase.json"
QGAF = "tests/resources/test-qualifiers.gaf"

def test_skim_gaf():
    p = GafParser()
    p.config.ecomap = EcoMap()
    results = p.skim(open(POMBASE, "r"))
    assert len(results) == 375
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
    assert len(results) == 4  # ensure NOTs are skipped

    p.config.exclude_relations = ['contributes_to', 'colocalizes_with']
    results = p.skim(open(QGAF, "r"))
    for r in results:
        print(str(r))
        (s, sn, o) = r
        assert o.startswith('GO:')
        assert s.startswith('MGI:') or s.startswith('PomBase')
    assert len(results) == 2 # ensure NOTs and excludes relations skipped

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

def parse_with(f, p):
    p.config.ecomap = EcoMap()
    is_gaf = f == POMBASE
    ont = OntologyFactory().create(ONT)

    if is_gaf:
        # only do ontology checking on GAF parse;
        # this is because ontology is made from GAF
        p.config.ontology = ont

    results = p.parse(open(f, "r"), skipheader=True)
    r1 = results[0]
    # TODO: test datafile does not have ECOs yet!!
    assert r1['evidence']['type'] == 'ISO' or r1['evidence']['type'] == 'ECO:0000201'
    assert r1['evidence']['with_support_from'] == ['SGD:S000001583']
    assert r1['evidence']['has_supporting_reference'] == ['GO_REF:0000024']

    if is_gaf:
        assert r1['subject']['label'] == 'ypf1'
        assert r1['date'] == '20150305'

    for r in results:
        #print(str(r))
        sid = r['subject']['id']
        prov = r['provided_by']
        assert prov == 'PomBase' or prov == 'UniProt'
        assert r['object']['id'].startswith('GO:')
        assert sid.startswith('PomBase:') or (not is_gaf and sid.startswith('PR'))
        if is_gaf:
            assert r['subject']['taxon']['id'] =='NCBITaxon:4896'

    # for m in p.report.messages:
    #     print("MESSAGE: {}".format(m))
    print("MESSAGES (sample): {}".format(p.report.messages[0:5]))
    assert len(p.report.messages) == 0
    print(p.report.to_markdown())

def test_flag_invalid_id():
    ont = OntologyFactory().create(ONT)
    p = GafParser()
    p.config.ontology = ont
    p._validate_ontology_class_id("FAKE:1", "fake")
    assert len(p.report.messages) == 1

def test_no_flag_valid_id():
    ont = OntologyFactory().create(ONT)
    p = GafParser()
    p.config.ontology = ont
    p._validate_ontology_class_id("GO:0016070", "fake")
    assert len(p.report.messages) == 0

def test_convert_gaf_to_gpad():
    p = GafParser()
    p.config.ecomap = EcoMap()
    w  = GpadWriter()
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
    len(assocs) == len(assocs2)


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
    summary = p.report.to_report_json()['summary']
    assert summary['association_count'] == 0
    assert summary['line_count'] > 300
    print(p.report.to_markdown())

    # ensure config is not preserved
    p = GafParser()
    assert p.config.class_idspaces == None

#POMBASE_GPAD = "tests/resources/truncated-pombase.gpad"

def test_qualifiers_gaf():
    parse_with2(QGAF, GafParser())
#def test_qualifiers_gpad():
#    parse_with2(POMBASE_GPAD, GpadParser())

def parse_with2(f, p):
    ont = OntologyFactory().create(ONT)

    p.config.ontology = ont
    assocs = p.parse(open(f, "r"), skipheader=True)
    neg_assocs = [a for a in assocs if a['negated'] == True]
    assert len(neg_assocs) == 3
    for a in assocs:
        print('REL: {}'.format(a['relation']))
    assert len([a for a in assocs if a['relation']['id'] == 'involved_in']) == 1
    assert len([a for a in assocs if a['relation']['id'] == 'contributes_to']) == 1

def test_errors_gaf():
    p = GafParser()
    p.config.ecomap = EcoMap()
    assocs = p.parse(open("tests/resources/errors.gaf", "r"), skipheader=True)
    msgs = p.report.messages
    print("MESSAGES: {}".format(len(msgs)))
    n_invalid_idspace = 0
    for m in msgs:
        print("MESSAGE: {}".format(m))
        if m['type'] == assocparser.Report.INVALID_IDSPACE:
            n_invalid_idspace += 1
    assert len(msgs) == 17
    assert n_invalid_idspace == 1

    # we expect 7
    assert len(assocs) == 7

    w = GafWriter()
    w.write(assocs)
    for a in assocs:
        if 'object_extensions' in a:
            # our test file has no ORs, so in DNF this is always the first
            xs = a['object_extensions']['union_of'][0]['intersection_of']
            for x in xs:

                print('X: {}'.format(x))
                # ensure that invalid expressions have been eliminated
                assert x['property'] == 'foo'
                assert x['filler'] == 'X:1'
            assert len(xs) == 1

ALT_ID_ONT = "tests/resources/alt_id_ont.json"

def test_alt_id_repair():
    p = GafParser()
    ont = OntologyFactory().create(ALT_ID_ONT)
    p.config.ecomap = EcoMap()
    p.config.ontology = ont
    gaf = io.StringIO("SGD\tS000000819\tAFG3\t\tGO:0043623\tPMID:8681382|SGD_REF:S000055187\tIMP\t\tP\tMitochondrial inner membrane m-AAA protease component\tYER017C|AAA family ATPase AFG3|YTA10\tgene\ttaxon:559292\t20170428\tSGD")

    assocs = p.parse(gaf, skipheader=True)
    assert len(assocs) > 0
    assert assocs[0]["object"]["id"] == "GO:0043623"

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

if __name__ == "__main__":
    pytest.main(args=["tests/test_gafparser.py::test_parse_gaf"])
