#!/usr/bin/env python

"""
Search queries

Type:

    biogorl-search -h

For instructions

Examples:


biogolr-search.py -vv -f relation -P subject_category object_category
biogolr-search.py -vv -f relation -P subject_taxon object_category
biogolr-search.py -vv -f relation -P subject_taxon is_defined_by

"""

import argparse
from ontobio.golr.golr_associations import search_query_as_matrix
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
    parser.add_argument('-f', '--facet', type=str, required=True,
                        help='Facet field to query')
    parser.add_argument('-q', '--fq', type=json.loads, default={}, required=False,
                        help='Facet query (solr fq) - should be json')
    parser.add_argument('-Q', '--qargs', type=json.loads, default={}, required=False,
                        help='Query to be passed directly to python golr_associations query')
    parser.add_argument('-P', '--search', nargs='*', type=str, required=False,
                        help='Search fields. E.f subject_category object_category, relation')
    parser.add_argument('-u', '--url', type=str, required=False,
                        help='Solr URL. E.g. http://localhost:8983/solr/golr')
    parser.add_argument('-v', '--verbosity', default=0, action='count',
                        help='Increase output verbosity')


    args = parser.parse_args()

    if args.verbosity >= 2:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbosity == 1:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
        
    logging.info("Welcome!")

    r = search_query_as_matrix(facet=args.facet,
                               fq=args.fq,
                               facet_search_fields=args.search,
                               url=args.url,
                               **args.qargs)

    print(str(r))
    trace = go.Heatmap(z=r['z'],
                       x=r['xaxis'],
                       y=r['yaxis'])
    data=[trace]
    py.plot(data, filename='search-heatmap')


if __name__ == "__main__":
    main()
