"""
Test in-memory map2slim
"""
from ontobio.io.gafparser import GafParser
from ontobio.io.gpadparser import GpadParser
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
    'GO:0023052', ## signaling
    'GO:0003674', ## molecular_function
    'GO:0008150'  ## BP
]

NESRA = 'GO:0005049' ## nuclear export signal receptor activity

def test_map2slim_gaf():
    f = POMBASE
    p = GafParser()
    is_gaf = f == POMBASE
    ont = OntologyFactory().create(ONT)
    relations=['subClassOf', 'BFO:0000050']

    # creates a basic JSON dictionary
    m = ont.create_slim_mapping(subset_nodes=SUBSET, relations=relations)

    assert m['GO:0071423'] == ['GO:0006810']
    assert len(m[NESRA]) == 2
    assert 'GO:0051169' in m[NESRA]
    assert 'GO:0003674' in m[NESRA]
    outfile = tempfile.NamedTemporaryFile(mode='w', delete=False)
    p.map_to_subset(open(f,"r"), class_map=m, outfile=outfile)
    for m in p.report.messages:
        logging.debug("MESSAGE1: {}".format(m))
    for m in p.report.messages:
        logging.debug("MESSAGE1: {}".format(m))
    logging.info("MESSAGES: {}".format(len(p.report.messages)))
    p = GafParser()
    logging.info("CLOSING: {}".format(outfile))
    outfile.close()

    logging.info("Reading from: {}".format(outfile.name))
    assocs = p.parse(outfile.name)
    for m in p.report.messages:
        logging.debug("MESSAGE2: {}".format(m))
    assert len(assocs) > 100
    cls_ids = set()
    for a in assocs:
        cid = a['object']['id']
        assert cid in SUBSET
        cls_ids.add(cid)
        print(str(a))
    print(cls_ids)
