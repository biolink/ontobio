from ontobio.io.gafparser import GafParser, GpadParser
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory

POMBASE = "tests/resources/truncated-pombase.gaf"
POMBASE_GPAD = "tests/resources/truncated-pombase.gpad"
ONT = "tests/resources/go-truncated-pombase.json"


def test_skim():
    p = GafParser()
    results = p.skim(open(POMBASE,"r"))
    for r in results:
        print(str(r))
        (s,sn,o) = r
        assert o.startswith('GO:')
        assert s.startswith('PomBase:')
    
def test_parse_gaf():
    parse_with(POMBASE, GafParser())
def test_parse_gpad():
    parse_with(POMBASE_GPAD, GpadParser())
    
def parse_with(f, p):
    is_gaf = f == POMBASE
    ont = OntologyFactory().create(ONT)

    if is_gaf:
        # only do ontology checking on GAF parse;
        # this is because ontology is made from GAF
        p.config.ontology = ont
    results = p.parse(open(f,"r"))
    r1 = results[0]
    assert r1['evidence']['with_support_from'] == ['SGD:S000001583']
    assert r1['evidence']['has_supporting_reference'] == ['GO_REF:0000024']

    if is_gaf:
        assert r1['subject']['label'] == 'ypf1'
    for r in results:
        #print(str(r))
        sid = r['subject']['id']
        prov = r['provided_by']
        assert prov == 'PomBase' or prov == 'UniProt'
        assert r['object']['id'].startswith('GO:')
        assert sid.startswith('PomBase:') or (not is_gaf and sid.startswith('PR'))
        if is_gaf:
            assert r['subject']['taxon']['id'] =='NCBITaxon:4896'

    for m in p.report.messages:
        print("MESSAGE: {}".format(m))
    assert len(p.report.messages) == 0
    print(p.report.to_markdown())

def test_invalid_goid():
    # Note: this ontology is a subset of GO extracted using the GAF, not GPAD
    ont = OntologyFactory().create(ONT)
    p = GpadParser()
    p.config.ontology = ont
    results = p.parse(open(POMBASE_GPAD,"r"))

    # we expect errors since ONT is not tuned for the GPAD file
    for m in p.report.messages:
        print("MESSAGE: {}".format(m))
    assert len(p.report.messages) > 500
    print(p.report.to_markdown())
    
def test_validate_go_idspaces():
    ont = OntologyFactory().create(ONT)
    p = GafParser()
    p.config.class_idspaces = ['FOOZ']
    assocs = p.parse(open(POMBASE,"r"))
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
    
