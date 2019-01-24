from ontobio.ontol_factory import OntologyFactory
import logging
from ontobio.io.ontol_renderers import GraphRenderer

PART_OF = 'BFO:0000050'

QUALITY = 'PATO:0000001'
PLOIDY = 'PATO:0001374'
EUPLOID = 'PATO:0001393'
SHAPE = 'PATO:0000052'
Y_SHAPED = 'PATO:0001201'

def test_local_json_parse():
    """
    Load ontology from JSON
    """
    factory = OntologyFactory()
    print("Creating ont")
    #tbox_ontology = factory.create('go')
    # TODO: create test module for this example
    tbox_ontology = factory.create('tests/resources/go-truncated-pombase.json')
    ont = factory.create('tests/resources/gocam-example.ttl', tbox_ontology=tbox_ontology)
    g = ont.get_graph()
    nodes = ont.search('%')
    print("NODES: {}".format(nodes))
    w = GraphRenderer.create(None)
    w.write_subgraph(ont, nodes)
    i = 'http://model.geneontology.org/0000000300000001/0000000300000007'
    ni = g.nodes[i]
    print(str(ni))
    ['GO:0060070'] == ni['types']
    nbrs = ont.neighbors(i)
    print("NEIGHBORS: {}".format(nbrs))
    subont = tbox_ontology.subontology(nodes, minimal=False)
    w = GraphRenderer.create('obo')
    print(w.render(subont))


