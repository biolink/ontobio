from ontobio.io.entityparser import BgiParser
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory

BGI = "tests/resources/fb-bgi.json"
    
def test_parse_gpi():
    p = BgiParser()
    results = p.parse(open(BGI, "r"))
    for r in results:
        print(r)
    r1 = results[0]
    assert r1['label'] == '4.5SRNA'
    assert r1['taxon']['id'] == 'NCBITaxon:7227'
    assert r1['full_name'] == '4.5SRNA'

    [r] = [r for r in results if r['full_name'] == 'Acetylcholine esterase']
    
    assert 'UniProtKB:P07140' in r['xrefs']
    assert "ace-2" in r['synonyms']

    for m in p.report.messages:
        print("MESSAGE: {}".format(m))
    assert len(p.report.messages) == 0
    print(p.report.to_markdown())
    
    
