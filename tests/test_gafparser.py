from ontobio.io.gafparser import GafParser
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory

POMBASE = "tests/resources/truncated-pombase.gaf"
ONT = "tests/resources/go-truncated-pombase.json"

def test_factory():
    ont = OntologyFactory().create(ONT)
    f = AssociationSetFactory()
    aset = f.create(ontology=ont, file=POMBASE)
    print("SUBJS: {}".format(aset.subjects))
    assert len(aset.subjects) > 100

def test_skim():
    p = GafParser()
    results = p.skim(open(POMBASE,"r"))
    for r in results:
        print(str(r))
        (s,sn,o) = r
        assert o.startswith('GO:')
        assert s.startswith('PomBase:')
    
    
def test_parse():
    ont = OntologyFactory().create(ONT)
    p = GafParser()
    results = p.parse(open(POMBASE,"r"))
    r1 = results[0]
    assert r1['evidence']['with_support_from'] == 'SGD:S000001583'
    assert r1['evidence']['has_supporting_reference'] == 'GO_REF:0000024'
    assert r1['subject']['label'] == 'ypf1'
    for r in results:
        print(str(r))
        prov = r['provided_by']
        assert prov == 'PomBase' or prov == 'UniProt'
        assert r['object']['id'].startswith('GO:')
        assert r['subject']['id'].startswith('PomBase:')
        assert r['subject']['taxon']['id'] =='NCBITaxon:4896'
        
