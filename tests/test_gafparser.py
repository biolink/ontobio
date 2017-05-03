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
    print(str(results))
    
    
def test_parse():
    p = GafParser()
    results = p.parse(open(POMBASE,"r"))
    for r in results:
        print(str(r))
    
