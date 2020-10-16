from ontobio.io.gpadparser import GpadParser, to_association
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


def test_parse_1_2():
    report = assocparser.Report(group="unknown", dataset="unknown")
    vals = [
        "MGI",
        "MGI:1918911",
        "enables",
        "GO:0003674",
        "MGI:MGI:2156816|GO_REF:0000015",
        "ECO:0000307",
        "",
        "",
        "20100209",
        "MGI",
        "",
        "creation-date=2020-09-17|modification-date=2020-09-17|contributor-id=http://orcid.org/0000-0003-2689-5511"
    ]
    result = to_association(list(vals), report=report, version="1.2")
    assert len(result.associations) > 0


def test_parse_2_0():
    version = "2.0"
    report = assocparser.Report(group="unknown", dataset="unknown")
    vals = [
        "MGI:MGI:1918911",
        "",
        "RO:0002327",
        "GO:0003674",
        "MGI:MGI:2156816|GO_REF:0000015",
        "ECO:0000307",
        "",
        "",
        "2020-09-17",
        "MGI",
        "",
        "creation-date=2020-09-17|modification-date=2020-09-17|contributor-id=http://orcid.org/0000-0003-2689-5511"
    ]
    result = to_association(list(vals), report=report, version=version)
    assert len(result.associations) > 0

    # Annotation_Extensions
    vals[10] = "BFO:0000066(CL:0000010),GOREL:0001004(CL:0000010)"
    result = to_association(list(vals), report=report, version=version)
    assert len(result.associations) > 0

    # With_or_From
    vals[6] = "PR:Q505B8|PR:Q8CHK4"
    result = to_association(list(vals), report=report, version=version)
    assert len(result.associations) > 0
