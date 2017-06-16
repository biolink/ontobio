#!/usr/bin/env python

"""
Command line wrapper to obographs library.

Type:

    ogr -h

For instructions

"""

import argparse
import networkx as nx
from networkx.algorithms.dag import ancestors, descendants
from ontobio.ontol_factory import OntologyFactory
from ontobio.io.ontol_renderers import GraphRenderer
from ontobio.slimmer import get_minimal_subgraph
from prefixcommons.curie_util import contract_uri, expand_uri
import logging

def main():
    """
    Wrapper for OGR
    """
    parser = argparse.ArgumentParser(description='Wrapper for obographs library'
                                                 """
                                                 By default, ontologies are cached locally and synced from a remote sparql endpoint
                                                 """,
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-r', '--resource', type=str, required=False,
                        help='Name of ontology')
    parser.add_argument('-o', '--outfile', type=str, required=False,
                        help='Path to output file')
    parser.add_argument('-t', '--to', type=str, required=False,
                        help='Output to (tree, dot, ...)')
    parser.add_argument('-d', '--direction', type=str, default='', required=False,
                        help='u = up, d = down, ud = up and down')
    parser.add_argument('-p', '--properties', nargs='*', type=str, required=False,
                        help='Properties')
    parser.add_argument('-P', '--prefix', type=str, required=False,
                        help='Prefix to constrain traversal on, e.g. PATO, ENVO')
    parser.add_argument('-Q', '--query', type=str, required=False,
                        help='SPARQL query body (only works with sparql handle)')
    parser.add_argument('-s', '--search', type=str, default='', required=False,
                        help='Search type. p=partial, r=regex')
    parser.add_argument('-S', '--slim', type=str, default='', required=False,
                        help='Slim type. m=minimal')
    parser.add_argument('--insubset', type=str, default='', required=False,
                        help='Name of subset to use as seed set of terms. For multiple subsets use comma for intersection and pipe for union')
    parser.add_argument('-L', '--level', type=int, required=False,
                        help='Query all nodes at level L in graph')
    parser.add_argument('-c', '--container_properties', nargs='*', type=str, required=False,
                        help='Properties to nest in graph')
    parser.add_argument('-v', '--verbosity', default=0, action='count',
                        help='Increase output verbosity')

    parser.add_argument('ids',nargs='*')

    args = parser.parse_args()

    if args.verbosity >= 2:
        logging.basicConfig(level=logging.DEBUG)
    if args.verbosity == 1:
        logging.basicConfig(level=logging.INFO)
    logging.info("Welcome!")
    
    handle = args.resource
    
    factory = OntologyFactory()
    logging.info("Creating ont object from: {} {}".format(handle, factory))
    ont = factory.create(handle)
    logging.info("ont: {}".format(ont))

    qids = []
    dirn = args.direction
    if dirn == '' and args.to is not None:
        dirn = 'u'
    searchp = args.search
    
    if args.level is not None:
        logging.info("Query for level: {}".format(args.level))
        qids = qids + ont.get_level(args.level, relations=args.properties, prefix=args.prefix)

    if args.insubset is not None and args.insubset != "":
        disjs = args.insubset.split("|")
        dset = set()
        for i in disjs:
            cset = None
            conjs = i.split(",")
            for j in conjs:
                terms = set(ont.extract_subset(j))
                if cset is None:
                    cset = terms
                else:
                    cset = cset.intersection(terms)
            dset = dset.union(cset)
        qids = qids + list(dset)
                    
        
    if args.query is not None:
        qids = qids + ont.sparql(select='*',
                                 body=args.query,
                                 inject_prefixes = ont.prefixes(),
                                 single_column=True)
        
    for id in ont.resolve_names(args.ids,
                                is_remote = searchp.find('x') > -1,
                                is_partial_match = searchp.find('p') > -1,
                                is_regex = searchp.find('r') > -1):
        qids.append(id)
    logging.info("Query IDs: {} Rels: {}".format(qids, args.properties))

    nodes = ont.traverse_nodes(qids, up=dirn.find("u") > -1, down=dirn.find("d") > -1,
                               relations=args.properties)

    # deprecated
    #g = ont.get_filtered_graph(relations=args.properties)
    subont = ont.subontology(nodes, relations=args.properties)
    show_subgraph(subont, qids, args)


def cmd_cycles(handle, args):
    g = retrieve_filtered_graph(handle, args)

    cycles = nx.simple_cycles(g)
    print(list(cycles))
    
def cmd_search(handle, args):
    for t in args.terms:
        results = search(handle, t)
        for r in results:
            print(r)

def show_subgraph(ont, query_ids, args):
    """
    Writes or displays graph
    """
    if args.slim.find('m') > -1:
        logging.info("SLIMMING")
        g = get_minimal_subgraph(g, query_ids)
    w = GraphRenderer.create(args.to)
    if args.outfile is not None:
        w.outfile = args.outfile
    w.write(ont, query_ids=query_ids, container_predicates=args.container_properties)
    #logging.info("Writing subgraph for {}, |nodes|={}".format(ont,len(nodes)))
    #w.write_subgraph(ont, nodes, query_ids=query_ids, container_predicates=args.container_properties)
            
def resolve_ids(ont, ids, args):
    r_ids = []
    for id in ids:
        if len(id.split(":")) ==2:
            r_ids.append(id)
        else:
            matches = [n for n in g.nodes() if g.node[n].get('label') == id]
            r_ids += matches
    return r_ids

    
if __name__ == "__main__":
    main()
