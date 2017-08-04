#!/usr/bin/env python

"""
Command line wrapper to ontobio lexmap library

Type:

    ogr -h

For instructions

"""

import argparse
import networkx as nx
from networkx.algorithms.dag import ancestors, descendants
from ontobio.ontol import Ontology
from ontobio.ontol_factory import OntologyFactory
from ontobio.io.ontol_renderers import GraphRenderer
from ontobio.slimmer import get_minimal_subgraph
from prefixcommons.curie_util import contract_uri, expand_uri
from ontobio.lexmap import LexicalMapEngine
import logging

def main():
    """
    Wrapper for OGR
    """
    parser = argparse.ArgumentParser(description='Wrapper for ontobio lexical mapping'
                                                 """
                                                 ...
                                                 """,
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-o', '--outfile', type=str, required=False,
                        help='Path to output file')
    parser.add_argument('-t', '--to', type=str, required=False, default='tsv',
                        help='Output to (tree, dot, ...)')
    parser.add_argument('-l', '--labels', type=str,
                        help='If set, then include node labels in results')
    parser.add_argument('-P', '--prefix', type=str, required=False,
                        help='Prefix to constrain traversal on, e.g. PATO, ENVO')
    parser.add_argument('-v', '--verbosity', default=0, action='count',
                        help='Increase output verbosity')

    parser.add_argument('ontologies',nargs='*')

    args = parser.parse_args()

    if args.verbosity >= 2:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbosity == 1:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
        
    logging.info("Welcome!")

    factory = OntologyFactory()
    onts = [factory.create(h) for h in args.ontologies]

    lexmap = LexicalMapEngine()
    if len(onts) == 0:
        raise ValueException("must pass one or more ontologies")
    else:
        for ont in onts:
            lexmap.index_ontology(ont)

    mo = Ontology()
    mo.merge(onts)
    
    g = lexmap.get_xref_graph()

    if args.to == 'obo':
        write_obo(g,mo,args)
    else:
        write_tsv(g,mo,args)

def write_tsv(g,mo,args):
    for x,y,d in g.edges_iter(data=True):
        vals = [x,y]
        if args.labels:
            vals = [x,mo.label(x),y,mo.label(y)]
        score=str(d['best'])
        (s1,s2)=d['syns']
        vals += [score,s1.val,s2.val]
        print("{}".format("\t".join(vals)))
        
def write_obo(g,mo,args):
    for x,y,d in g.edges_iter(data=True):
        score=str(d['best'])
        (s1,s2)=d['syns']
        print('[Term]')
        print('id: {} ! {}'.format(x,mo.label(x)))
        print('xref: {} ! {} // {} {} {}'.format(y,mo.label(y),score,s1.val,s2.val))
        print()

if __name__ == "__main__":
    main()
