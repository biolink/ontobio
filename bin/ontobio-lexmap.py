#!/usr/bin/env python

"""
Command line wrapper to ontobio lexmap library

Type:

    ogr -h

For instructions

"""

import argparse
import networkx as nx
import pandas as pd
import numpy as np
from networkx.algorithms.dag import ancestors, descendants
from ontobio.ontol import Ontology
from ontobio.ontol_factory import OntologyFactory
from ontobio.io.ontol_renderers import GraphRenderer
from ontobio.slimmer import get_minimal_subgraph
from prefixcommons.curie_util import contract_uri, expand_uri
from ontobio.lexmap import LexicalMapEngine
import logging
import yaml
import json

def main():
    """
    Wrapper for OGR
    """
    parser = argparse.ArgumentParser(description='Wrapper for ontobio lexical mapping'
                                                 """
                                                 Lexically maps one or more ontologies. Ontologies can be local or remote,
                                                 any input handle can be specified, see docs for more details on handles.

                                                 If multiple ontologies are specified, then each ontology in the list is compared against the first one.

                                                 If a simgle ontology is specified, then all pairs in that ontology will be compared
                                                 
                                                 Output format to be documented - see lexmap.py for the various scoring attributes for now.
                                                 """,
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-o', '--outfile', type=str, nargs='*', default=[], required=False,
                        help='Path to output file')
    parser.add_argument('-t', '--to', type=str, required=False, default='tsv',
                        help='Output to (tree, dot, ...)')
    parser.add_argument('-l', '--labels', type=str,
                        help='If set, then include node labels in results. DEPRECATED')
    parser.add_argument('-s', '--scoring', default='sim', type=str,
                        help='Score weighting scheme. Default=sim')
    parser.add_argument('-P', '--prefix', type=str, required=False,
                        help='Prefix to constrain traversal on, e.g. PATO, ENVO')
    parser.add_argument('-c', '--config', type=str, required=False,
                        help='lexmap configuration file (yaml). See schema for details')
    parser.add_argument('-X', '--xref_weights', type=str, required=False,
                        help='csv of curated per-xref weights')
    parser.add_argument('-e', '--eval_xrefs', default=False, action='store_true', dest='eval_xrefs',
                        help='only compare xrefs')
    parser.add_argument('-u', '--unmapped', type=str, required=False,
                        help='File to export unmapped nodes to')
    parser.add_argument('-A', '--all-by-all', dest='all_by_all', action='store_true',
                        help='compare all ontologies against all.')
    parser.add_argument('-v', '--verbosity', default=0, action='count',
                        help='Increase output verbosity')

    parser.add_argument('ontologies',nargs='*',
                        help='one or more ontologies to be aligned. Any input handle can be specified')

    args = parser.parse_args()

    if args.verbosity >= 2:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbosity == 1:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
        
    logging.info("Welcome!")

    factory = OntologyFactory()
    onts = [filter_by_prefix(factory.create(h)) for h in args.ontologies]

    
    config = {}
    if args.config is not None:
        f = open(args.config,'r')
        config = yaml.load(f, Loader=yaml.FullLoader)
        f.close()

    # add pre-defined weights to config
    if args.xref_weights is not None:
        if 'xref_weights' not in config:
            config['xref_weights'] = []
        xws = config['xref_weights']
        df = pd.read_csv(args.xref_weights)
        df = df.fillna(0.0)
        for _, row in df.iterrows():
            w = float(row['weight'])
            WA = np.array((0.0, 0.0, 0.0, 0.0))
            if w < 0:
                WA[2] = w
                WA[3] = abs(w)
            else:
                WA[2] = w
                WA[3] = -w
            xws.append({'left':row['left'],
                        'right':row['right'],
                        'weights':WA})
        
    logging.info("ALL: {}".format(args.all_by_all))
    
    lexmap = LexicalMapEngine(config=config)

    if args.eval_xrefs:
        cpairs = []
        for n in onts[0].nodes():
            for x in onts[0].xrefs(n):
                cpairs.append((n,x))
        lexmap.class_pairs = cpairs
        logging.info("Comparing {} class pairs. Sample: {}".format(len(cpairs), cpairs[0:50]))
    
    
    
    if len(onts) == 0:
        raise ValueException("must pass one or more ontologies")
    else:
        logging.info("Indexing ontologies: {}".format(onts))
        for ont in onts:
            lexmap.index_ontology(ont)
        oid0 = onts[0].id
        pairs = [(oid0,oid0)]
        if len(onts) > 1:
            if args.all_by_all:
                logging.info("All vs ALL: {}".format(onts))
                pairs = []
                for i in onts:
                    for j in onts:
                        if i.id < j.id:
                            pairs.append((i.id, j.id))
            else:
                logging.info("All vs first in list: {}".format(oid0))
                pairs = [(oid0, ont.id) for ont in onts[1:]]
        logging.info("Comparing the following pairs of ontologies: {}".format(pairs))
        lexmap.ontology_pairs = pairs
    mo = Ontology()
    mo.merge(onts)

    g = lexmap.get_xref_graph()
    
    
    if args.to == 'obo':
        write_obo(g,mo,args)
    else:
        write_tsv(lexmap,g,mo,args)

        
    if args.unmapped:
        udf = lexmap.unmapped_dataframe(g)
        udf.to_csv(args.unmapped, sep="\t", index=False)
        
def write_tsv(lexmap,g,mo,args):
    df=lexmap.as_dataframe(g)
    print(df.to_csv(sep="\t", index=False))

# TODO    
def write_json(lexmap,g,fn,args):
    nodes = []
    for x,y,d in g.edges_iter(data=True):
        nodes.append({'id':x,
                      'meta':{
                      }})
    f = open(fn,'write')
    json.dump({'graphs':{'nodes':nodes}},f)
    f.close()
    
def write_obo(g,mo,args):
    for x,y,d in g.edges_iter(data=True):
        score=str(d['score'])
        (s1,s2)=d['syns']
        print('[Term]')
        print('id: {} ! {}'.format(x,mo.label(x)))
        print('xref: {} ! {} // {} {} {}'.format(y,mo.label(y),score,s1.val,s2.val))
        print()

def in_clique(x, cliques):
    for s in cliques:
        if x in s:
            return s
    return set()

def filter_by_prefix(ont):
    if ont.handle:
        pfx = ont.handle
        nids = [n for n in ont.nodes() if ont.prefix(n).lower() == pfx]
        if len(nids) > 20:
            logging.info("filtering {} to {} nodes with prefix {}".format(ont,len(nids),pfx))
            ont = ont.subontology(nids)
    return ont

if __name__ == "__main__":
    main()
