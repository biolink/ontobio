from ontobio.io.gafparser import GafParser

def test_skim():
    p = GafParser()
    results = p.skim(open("tests/resources/truncated-pombase.gaf","r"))
    print(str(results))

def test_parse():
    p = GafParser()
    results = p.parse(open("tests/resources/truncated-pombase.gaf","r"))
    for r in results:
        print(str(r))
    
