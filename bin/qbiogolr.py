#!/usr/bin/env python

"""
Command line wrapper to ontobio.golr library.

Type:

    qbiogolr -h

For instructions

"""

import argparse
from ontobio.golr.golr_associations import search_associations
from ontobio.ontol_factory import OntologyFactory
from ontobio.io.ontol_renderers import *
import networkx as nx
from networkx.algorithms.dag import ancestors, descendants
from networkx.drawing.nx_pydot import write_dot
from prefixcommons.curie_util import expand_uri
from ontobio.slimmer import get_minimal_subgraph
#from ontobio.golr.golr_associations import search_associations, search_associations_compact, GolrFields, select_distinct_subjects, get_objects_for_subject, get_subjects_for_object
import logging

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

    parser.add_argument('-r', '--resource', type=str, required=False,
                        help='Name of ontology')
    parser.add_argument('-d', '--display', type=str, default='o', required=False,
                        help='What to display: some combination of o, s, r. o=object ancestors, s=subject ancestors. If r present, draws s<->o relations ')
    parser.add_argument('-o', '--outfile', type=str, required=False,
                        help='Path to output file')
    parser.add_argument('-t', '--to', type=str, required=False,
                        help='Output to (tree, dot, ...)')
    parser.add_argument('-C', '--category', type=str, required=False,
                        help='Category')
    parser.add_argument('-c', '--container_properties', nargs='*', type=str, required=False,
                        help='Properties to nest in graph')
    parser.add_argument('-s', '--species', type=str, required=False,
                        help='NCBITaxon ID')
    parser.add_argument('-e', '--evidence', type=str, required=False,
                        help='ECO ID')
    parser.add_argument('-G', '--graph', type=str, default='', required=False,
                        help='Graph type. m=minimal')
    parser.add_argument('-S', '--slim', nargs='*', type=str, required=False,
                        help='Slim IDs')
    parser.add_argument('-M', '--mapids', type=str, required=False,
                        help='Map identifiers to this ID space, e.g. ENSEMBL')
    parser.add_argument('-p', '--properties', nargs='*', type=str, required=False,
                        help='Properties')
    parser.add_argument('-v', '--verbosity', default=0, action='count',
                        help='Increase output verbosity')

    parser.add_argument('ids',nargs='*')

    # ontology
    args = parser.parse_args()

    if args.verbosity >= 2:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbosity == 1:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
        
    logging.info("Welcome!")

    ont = None
    g = None
    handle = args.resource
    if handle is not None:
        logging.info("Handle: {}".format(handle))
        factory = OntologyFactory()
        logging.info("Factory: {}".format(factory))
        ont = factory.create(handle)
        logging.info("Created ont: {}".format(ont))
        g = ont.get_filtered_graph(relations=args.properties)

    w = GraphRenderer.create(args.to)

    nodes = set()

    display = args.display

    # query all IDs, gathering associations
    assocs = []
    for id in args.ids:
        this_assocs, facets = search_golr_wrap(id,
                                               args.category,
                                               subject_taxon=args.species,
                                               rows=1000,
                                               slim=args.slim,
                                               evidence=args.evidence,
                                               map_identifiers=args.mapids)

        assocs += this_assocs

    logging.info("Num assocs: {}".format(len(assocs)))

    for a in assocs:
        print("{}\t{}\t{}\t{}".format(a['subject'],
                                  a['subject_label'],
                                  a['relation'],
                                  ";".join(a['objects'])))

    if ont is not None:
        # gather all ontology classes used
        for a in assocs:
            objs = a['objects']

            if display.find('r') > -1:
                pass

            if display.find('o') > -1:
                for obj in objs:
                    nodes.add(obj)
                    if ont is not None:
                        nodes.update(ont.ancestors(obj))

            if display.find('s') > -1:
                sub = a['subject']
                nodes.add(sub)
                if ont is not None:
                    nodes.update(ont.ancestors(sub))

        # create a subgraph
        subg = g.subgraph(nodes)

        # optionally add edges between subj and obj nodes
        if display.find('r') > -1:
            for a in assocs:
                rel = a['relation']
                sub = a['subject']
                objs = a['objects']
                if rel is None:
                    rel = 'rdfs:seeAlso'
                for obj in objs:
                    logging.info("Adding assoc rel {} {} {}".format(sub,obj,rel))
                    subg.add_edge(obj,sub,pred=rel)

        # display tree/graph
        show_graph(subg, nodes, objs, args)

# TODO
def cmd_map2slim(ont, args):

    subset_term_ids = ont.extract_subset(args.slim)
    nodes = set()
    for id in resolve_ids(g, args.ids, args):
        nodes.add(id)
        assocs = search_associations(object=id,
                                     subject_taxon=args.species,
                                     slim=subset_term_ids,
                                     rows=0,
                                     subject_category=args.category)
        for a in assocs:
            print(a)
            for x in a['objects']:
                print('  '+pp_node(g,x,args))


def show_graph(g, nodes, query_ids, args):
    """
    Writes graph
    """
    if args.graph.find('m') > -1:
        logging.info("SLIMMING")
        g = get_minimal_subgraph(g, query_ids)
    w = GraphRenderer.create(args.to)
    if args.outfile is not None:
        w.outfile = args.outfile
    logging.info("Writing subg from "+str(g))
    w.write(g, query_ids=query_ids, container_predicates=args.container_properties)

def search_golr_wrap(id, category, **args):
    """
    performs searches in both directions
    """
    #assocs1 = search_associations_compact(object=id, subject_category=category, **args)
    #assocs2 = search_associations_compact(subject=id, object_category=category, **args)
    assocs1, facets1 = search_compact_wrap(object=id, subject_category=category, **args)
    assocs2, facets2 = search_compact_wrap(subject=id, object_category=category, **args)
    facets = facets1
    if len(assocs2) > 0:
        facets = facets2
    return assocs1 + assocs2, facets

def search_compact_wrap(**args):
    searchresult = search_associations(use_compact_associations=True,
                                       facet_fields=[],
                                       **args
    )
    return searchresult['compact_associations'], searchresult['facet_counts']


if __name__ == "__main__":
    main()
