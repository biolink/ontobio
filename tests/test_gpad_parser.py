from ontobio.io.gpadparser import GpadParser
from ontobio.io import assocparser

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
