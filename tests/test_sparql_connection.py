from ontobio.ontol_factory import OntologyFactory
from networkx.algorithms.dag import ancestors
from ontobio.io.ontol_renderers import GraphRenderer

PLOIDY = 'PATO:0001374'

Y_SHAPED = 'PATO:0001201'

def test_remote_sparql():
    """
    reconstitution test
    """
    factory = OntologyFactory()
    # default method is sparql
    ont = factory.create('pato')
    g = ont.get_graph()
    info = g.node[PLOIDY]
    print(str(info))
    nodes = g.nodes()
    print(len(nodes))
    assert len(nodes) > 100
    nbrs = g.successors(PLOIDY)
    print("SUCC:"+str(nbrs))
    parents = g.predecessors(PLOIDY)
    print("PRED:"+str(parents))
    assert parents == ['PATO:0001396']
    ancs = ancestors(g, PLOIDY)
    print("ANCS:"+str(ancs))
    assert 'PATO:0000001' in ancs
    print(g)
    Q = ['.*shape.*']
    w = GraphRenderer.create('tree')

    shapes1 = ont.resolve_names(Q, is_regex=True, is_remote=False)
    print("SHAPE Q:"+str(shapes1))
    show_nodes(w, ont, shapes1)
    assert Y_SHAPED in shapes1
    
    shapes2 = ont.resolve_names(Q, is_regex=True, is_remote=True)
    print("SHAPE Q:"+str(shapes2))
    show_nodes(w, ont, shapes2)
    assert Y_SHAPED in shapes2

def show_nodes(w, ont, ids):
    for id in ids:
        print(w.render_noderef(ont, id))
