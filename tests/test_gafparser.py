from ontobio.io.gafparser import GafParser, GpadParser
from ontobio.io.assocwriter import GpadWriter
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory
import tempfile

POMBASE = "tests/resources/truncated-pombase.gaf"
POMBASE_GPAD = "tests/resources/truncated-pombase.gpad"
ONT = "tests/resources/go-truncated-pombase.json"
QGAF = "tests/resources/test-qualifiers.gaf"

def test_skim_gaf():
    p = GafParser()
    results = p.skim(open(POMBASE,"r"))
    assert len(results) == 375
    for r in results:
        print(str(r))
        (s,sn,o) = r
        assert o.startswith('GO:')
        assert s.startswith('PomBase:')

def test_skim_gaf_qualifiers():
    p = GafParser()
    p.config.remove_double_prefixes = True
    results = p.skim(open(QGAF,"r"))
    for r in results:
        print(str(r))
        (s,sn,o) = r
        assert o.startswith('GO:')
        assert s.startswith('MGI:') or s.startswith('PomBase')
    assert len(results) == 4  # ensure NOTs are skipped

    p.config.exclude_relations = ['contributes_to', 'colocalizes_with']
    results = p.skim(open(QGAF,"r"))
    for r in results:
        print(str(r))
        (s,sn,o) = r
        assert o.startswith('GO:')
        assert s.startswith('MGI:') or s.startswith('PomBase')
    assert len(results) == 2 # ensure NOTs and excludes relations skipped
    
    
        
def test_skim_gpad():
    p = GpadParser()
    results = p.skim(open(POMBASE_GPAD,"r"))
    assert len(results) == 1984
    for r in results:
        print(str(r))
        (s,sn,o) = r
        assert o.startswith('GO:')
        assert s.startswith('PomBase:') or s.startswith('PR:')
        
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
    # TODO: test datafile does not have ECOs yet!!
    assert r1['evidence']['type'] == 'ISO' or r1['evidence']['type'] == ''
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


def test_convert_gaf_to_gpad():
    p = GafParser()
    w  = GpadWriter()
    p2 = GpadParser()
    convert(POMBASE, p, w, p2)

def convert(file, p, w, p2):
    assocs = p.parse(file)
    outfile = tempfile.NamedTemporaryFile(mode='w', delete=False)
    w.file = outfile
    for a in assocs:
        w.write_assoc(a)
    outfile.close()
    assocs2 = p2.parse(outfile.name)
    for a in assocs2:
        print("REPARSED: {}".format(a))
    len(assocs) == len(assocs2)
    

        
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
    
#POMBASE_GPAD = "tests/resources/truncated-pombase.gpad"

def test_qualifiers_gaf():
    parse_with2(QGAF, GafParser())
#def test_qualifiers_gpad():
#    parse_with2(POMBASE_GPAD, GpadParser())
    
def parse_with2(f, p):
    is_gaf = f == POMBASE
    ont = OntologyFactory().create(ONT)
    
    p.config.ontology = ont
    assocs = p.parse(open(f,"r"))
    neg_assocs = [a for a in assocs if a['negated'] == True]
    assert len(neg_assocs) == 3
    for a in assocs:
        print('REL: {}'.format(a['relation']))
    assert len([a for a in assocs if a['relation']['id'] == 'involved_in']) == 1
    assert len([a for a in assocs if a['relation']['id'] == 'contributes_to']) == 1
    
    
