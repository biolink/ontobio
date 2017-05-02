#!/usr/bin/env python

"""
Search queries

Type:

    biogorl-search -h

For instructions

Examples:

"""

import argparse
from ontobio.golr.golr_query import GolrSearchQuery
import networkx as nx
from networkx.algorithms.dag import ancestors, descendants
from networkx.drawing.nx_pydot import write_dot
from prefixcommons.curie_util import expand_uri
from ontobio.slimmer import get_minimal_subgraph
import yaml
import json
import logging
import plotly.plotly as py
import plotly.graph_objs as go

def main():
    """
    Wrapper for OGR
    """

    parser = argparse.ArgumentParser(
        description='Command line interface to python-ontobio.golr library'
        """

        Provides command line interface onto the ontobio.golr python library, a high level 
        abstraction layer over Monarch and GO solr indices.
        """,
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-o', '--outfile', type=str, required=False,
                        help='Path to output file')
    parser.add_argument('-f', '--facet', type=str, required=False,
                        help='Facet field to query')
    parser.add_argument('-q', '--fq', type=json.loads, default={}, required=False,
                        help='Facet query (solr fq) - should be json')
    parser.add_argument('-Q', '--qargs', type=json.loads, default={}, required=False,
                        help='Query to be passed directly to python golr_associations query')
    parser.add_argument('-l', '--legacy_solr', dest='legacy_solr', action='store_true', default=False,
                        help='Set for legacy solr schema (solr3 golr)')
    parser.add_argument('-u', '--url', type=str, required=False,
                        help='Solr URL. E.g. http://localhost:8983/solr/golr')
    parser.add_argument('-v', '--verbosity', default=0, action='count',
                        help='Increase output verbosity')

    parser.add_argument('search', type=str,
                        help='Search terms')
    
    args = parser.parse_args()

    if args.verbosity >= 2:
        logging.basicConfig(level=logging.DEBUG)
    if args.verbosity == 1:
        logging.basicConfig(level=logging.INFO)
    logging.info("Welcome!")

    q = GolrSearchQuery(args.search,
                        is_go=args.legacy_solr,
                        url=args.url)
    

    results = q.exec()
    #print("RESULTS={}".format(results))
    docs = results['docs']
    print("RESULTS: {}".format(len(docs)))
    for r in docs:
        print(" {} '{}' {} // {}".format(r['id'],r['label'],r['score'], r['category']))

    
if __name__ == "__main__":
    main()
