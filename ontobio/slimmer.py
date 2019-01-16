import networkx as nx
import logging


def get_minimal_subgraph(g, nodes):
    """
    given a set of nodes, extract a subgraph that excludes non-informative nodes - i.e.
    those that are not MRCAs of pairs of existing nodes.
    
    Note: no property chain reasoning is performed. As a result, edge labels are lost.
    """
    logging.info("Slimming {} to {}".format(g,nodes))
    # maps ancestor nodes to members of the focus node set they subsume
    mm = {}
    subnodes = set()
    for n in nodes:
        subnodes.add(n)
        ancs = nx.ancestors(g, n)
        ancs.add(n)
        for a in ancs:
            subnodes.add(a)
            if a not in mm:
                mm[a] = set()
            mm[a].add(n)

    # merge graph
    egraph = nx.MultiDiGraph()

    # TODO: ensure edge labels are preserved
    for a, aset in mm.items():
        for p in g.predecessors(a):
            logging.info(" cmp {} -> {} // {} {}".format(len(aset),len(mm[p]), a, p))
            if p in mm and len(aset) == len(mm[p]):
                egraph.add_edge(p, a)
                egraph.add_edge(a, p)
                logging.info("will merge {} <-> {} (members identical)".format(p,a))

    nmap = {}
    leafmap = {}
    disposable = set()
    for cliq in nx.strongly_connected_components(egraph):
        leaders = set()
        leafs = set()
        for n in cliq:
            is_src = False
            if n in nodes:
                logging.info("Preserving: {} in {}".format(n,cliq))
                leaders.add(n)
                is_src = True
                
            is_leaf = True
            for p in g.successors(n):
                if p in cliq:
                    is_leaf = False

            if not(is_leaf or is_src):
                disposable.add(n)
                
            if is_leaf:
                logging.info("Clique leaf: {} in {}".format(n,cliq))
                leafs.add(n)

                
        leader = None
        if len(leaders) > 1:
            logging.info("UHOH: {}".format(leaders))
        if len(leaders) > 0:
            leader = list(leaders)[0]
        else:
            leader = list(leafs)[0]
        leafmap[n] = leafs

    subg = g.subgraph(subnodes)
    fg = remove_nodes(subg, disposable)
    return fg

def remove_nodes(g, rmnodes):
    logging.info("Removing {} from {}".format(rmnodes,g))
    newg = nx.MultiDiGraph()
    for (n,nd) in g.nodes(data=True):
        if n not in rmnodes:
            newg.add_node(n, **nd)
            parents = _traverse(g, set([n]), set(rmnodes), set())
            for p in parents:
                newg.add_edge(p,n,**{'pred':'subClassOf'})
    return newg     

def _traverse(g, nset, rmnodes, acc):
    if len(nset) == 0:
        return acc
    n = nset.pop()
    parents = set(g.predecessors(n))
    acc = acc.union(parents - rmnodes)
    nset = nset.union(parents.intersection(rmnodes))
    return _traverse(g, nset, rmnodes, acc)

