from ontobio.io.gpadparser import GpadParser

POMBASE = "tests/resources/truncated-pombase.gpad"

def test_skim():
    p = GpadParser()
    results = p.skim(open(POMBASE,"r"))
    print(str(results))


def test_parse():
    p = GpadParser()
    results = p.parse(open(POMBASE,"r"))
    for r in results:
        print(str(r))
