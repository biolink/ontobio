from ontobio.io.gafparser import GafParser
from ontobio.assoc_factory import AssociationSetFactory

POMBASE = "tests/resources/truncated-pombase.gaf"

def test_skim():
    p = GafParser()
    results = p.skim(open(POMBASE,"r"))
    print(str(results))

    
def test_parse():
    p = GafParser()
    results = p.parse(open(POMBASE,"r"))
    for r in results:
        print(str(r))
    
