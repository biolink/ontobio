from ontobio.io.gafparser import GafParser, GpadParser
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory
import tempfile
import logging

POMBASE = "tests/resources/truncated-pombase.gaf"
ONT = "tests/resources/go-truncated-pombase.json"

SUBSET = [
    'GO:0051169', ## nuclear transport
    'GO:0006810', ## transport
    'GO:0005730', ## nucleolus
    'GO:0016604', ## nuclear body
    'GO:0023052'  ## signaling
]
    
def test_map2slim_gaf():
    f = POMBASE
    p = GafParser()
    is_gaf = f == POMBASE
    ont = OntologyFactory().create(ONT)
    relations=['subClassOf', 'BFO:0000050']
    m = ont.create_slim_mapping(subset_nodes=SUBSET, relations=relations)
    print(str(m))
    assert m['GO:0071423'] == ['GO:0006810']
    outfile = tempfile.NamedTemporaryFile(mode='w', delete=False)
    p.map_to_subset(open(f,"r"), class_map=m, outfile=outfile)
    for m in p.report.messages:
        print("MESSAGE: {}".format(m))
    p = GafParser()
    outfile.close()
    logging.info("Reading from: {}".format(outfile.name))
    assocs = p.parse(outfile.name)
    assert len(assocs) > 100
    cls_ids = set()
    for a in assocs:
        cid = a['object']['id']
        assert cid in SUBSET
        cls_ids.add(cid)
        print(str(a))
    print(cls_ids)
