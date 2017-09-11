
def materialize_xrefs_as_edges(ont, xref_graph=None):
    if xref_graph is None:
        xref_graph = ont.xref_graph
    for x,y in xref_graph.edges_iter():
        nodes = ont.nodes()
        if x in nodes and y in nodes:
            ont.add_parent(x,y,'xref')
            ont.add_parent(y,x,'xref')


