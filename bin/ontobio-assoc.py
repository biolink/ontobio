#!/usr/bin/env python

"""
Command line wrapper to obographs assocmodel library

Type:

    ogr-assoc -h

For instructions

Examples:

```

Find genes annotated to a GO class in human:

ontobio-assoc.py -v -r go -T NCBITaxon:9606 -C gene function query -q GO:1903010

Analogous query in planteome:

ontobio-assoc.py -v -y conf/planteome-config.yaml -r po -T NCBITaxon:3702 -C gene anatomy query -q PO:0025034

ontobio-assoc.py -v -r go -T NCBITaxon:9606 -C gene function enrichment -q GO:1903010

ontobio-assoc.py -v -r go -T NCBITaxon:10090 -C gene function dendrogram GO:0003700 GO:0005215 GO:0005634 GO:0005737 GO:0005739 GO:0005694 GO:0005730  GO:0000228 GO:0000262

ontobio-assoc.py -v -r go -T NCBITaxon:10090 -C gene function simmatrix MGI:1890081 MGI:97487 MGI:106593 MGI:97250 MGI:2151057 MGI:1347473

ontobio-assoc.py -C gene function -T pombe -r go -f tests/resources/truncated-pombase.gaf query -q GO:0005622

# requires files from ftp://ftp.rgd.mcw.edu/pub/ontology/annotated_rgd_objects_by_ontology
ontobio-assoc.py  -T . -C gene disease -r doid -f homo_genes_do phenolog -R pw -F homo_genes_pw > PAIRS.txt
```

"""

import argparse
import networkx as nx
from networkx.algorithms.dag import ancestors, descendants
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory
from ontobio.io.ontol_renderers import GraphRenderer
from ontobio.slimmer import get_minimal_subgraph
from ontobio import ecomap
import logging


ecomapping = ecomap.EcoMap()
iea_eco = ecomapping.coderef_to_ecoclass("IEA")


def main():
    """
    Wrapper for OGR Assocs
    """
    parser = argparse.ArgumentParser(description='Wrapper for obographs assocmodel library'
                                                 """
                                                 By default, ontologies and assocs are cached locally and synced from a remote sparql endpoint
                                                 """,
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-r', '--resource', type=str, required=False,
                        help='Name of ontology')
    parser.add_argument('-f', '--assocfile', type=str, required=False,
                        help='Name of input file for associations')
    parser.add_argument('-A', '--assocformat', type=str, default='gaf', required=False,
                        help='Format of association file, if passed (default: gaf)')
    parser.add_argument('-o', '--outfile', type=str, required=False,
                        help='Path to output file')
    parser.add_argument('-t', '--to', type=str, required=False,
                        help='Output to (tree, dot, ...)')
    parser.add_argument('-d', '--direction', type=str, default='u', required=False,
                        help='u = up, d = down, ud = up and down')
    parser.add_argument('-e', '--evidence', type=str, required=False,
                        help='ECO class')
    parser.add_argument('-p', '--properties', nargs='*', type=str, required=False,
                        help='Properties')
    parser.add_argument('-P', '--plot', type=bool, default=False,
                        help='if set, plot output (requires plotly)')
    parser.add_argument('-y', '--yamlconfig', type=str, required=False,
                        help='Path to setup/configuration yaml file')
    parser.add_argument('-S', '--slim', type=str, default='', required=False,
                        help='Slim type. m=minimal')
    parser.add_argument('-c', '--container_properties', nargs='*', type=str, required=False,
                        help='Properties to nest in graph')
    parser.add_argument('-C', '--category', nargs=2, type=str, required=False,
                        help='category tuple (SUBJECT OBJECT)')
    parser.add_argument('-T', '--taxon', type=str, required=False,
                        help='Taxon of associations')
    parser.add_argument('-v', '--verbosity', default=0, action='count',
                        help='Increase output verbosity')

    subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')

    # EXTRACT ONTOLOGY
    parser_n = subparsers.add_parser('subontology',
                                     help='Extract sub-ontology, include only annotated nodes or their descendants')
    parser_n.add_argument('-M', '--minimal', dest='minimal', action='store_true', default=False, help='If set, remove non-MRCA nodes')
    parser_n.set_defaults(function=extract_ontology)

    # ENRICHMENT
    parser_n = subparsers.add_parser('enrichment',
                                     help='Perform an enrichment test over a sample set of annotated entities')
    parser_n.add_argument('-q', '--query',type=str, help='query all genes for this class an use as subject')
    parser_n.add_argument('-H', '--hypotheses',nargs='*', help='list of classes to test against')
    parser_n.add_argument('-s', '--sample_file', type=str, help='file containing list of gene IDs in sample set')
    parser_n.add_argument('-b', '--background_file', type=str, help='file containing list of gene IDs in background set')
    parser_n.add_argument('-t', '--threshold', type=float, help='p-value threshold')
    parser_n.add_argument('sample_ids', nargs='*', help='list of gene IDs in sample set')
    parser_n.set_defaults(function=run_enrichment_test)

    # PHENOLOG
    parser_n = subparsers.add_parser('phenolog',
                                     help='Perform multiple enrichment tests, using a second ontology and assoc set to build gene sets')
    parser_n.add_argument('-R', '--resource2',type=str, required=True, help='path to second GAF')
    parser_n.add_argument('-F', '--file2',type=str, required=True, help='handle for second ontology')
    parser_n.set_defaults(function=run_phenolog)

    # QUERY
    parser_n = subparsers.add_parser('query',
                                     help='Query for entities (e.g. genes) based on positive and negative terms')
    parser_n.add_argument('-q', '--query',nargs='*', help='positive classes')
    parser_n.add_argument('-N', '--negative',type=str, help='negative classes')
    parser_n.set_defaults(function=run_query)

    # QUERY ASSOCIATIONS
    parser_n = subparsers.add_parser('associations',
                                     help='Query for associations for a set of entities (e.g. genes)')
    parser_n.add_argument('subjects',nargs='*', help='subject ids')
    parser_n.add_argument('-D', '--dendrogram',type=bool, default=False)
    parser_n.set_defaults(function=run_query_associations)

    # INTERSECTIONS
    parser_n = subparsers.add_parser('intersections',
                                     help='Query intersections')
    parser_n.add_argument('-X', '--xterms',nargs='*', help='x classes')
    parser_n.add_argument('-Y', '--yterms',nargs='*', help='y classes')
    parser_n.add_argument('--useids',type=bool, default=False, help='if true, use IDs not labels on axes')
    parser_n.add_argument('terms',nargs='*', help='all terms (x and y)')
    parser_n.set_defaults(function=plot_intersections)

    # INTERSECTION DENDROGRAM (TODO: merge into previous?)
    parser_n = subparsers.add_parser('intersection-dendrogram',
                                     help='Plot dendrogram from intersections')
    parser_n.add_argument('-X', '--xterms',nargs='*', help='x classes')
    parser_n.add_argument('-Y', '--yterms',nargs='*', help='y classes')
    parser_n.add_argument('--useids',type=bool, default=False, help='if true, use IDs not labels on axes')
    parser_n.add_argument('terms',nargs='*', help='all terms (x and y)')
    parser_n.set_defaults(function=plot_term_intersection_dendrogram)

    # SIMILARITY MATRIX (may move to another module)
    parser_n = subparsers.add_parser('simmatrix',
                                     help='Plot dendrogram for similarities between subjects')
    parser_n.add_argument('-X', '--xsubjects',nargs='*', help='x subjects')
    parser_n.add_argument('-Y', '--ysubjects',nargs='*', help='y subjects')
    parser_n.add_argument('--useids',type=bool, default=False, help='if true, use IDs not labels on axes')
    parser_n.add_argument('subjects',nargs='*', help='all terms (x and y)')
    parser_n.set_defaults(function=plot_simmatrix)

    args = parser.parse_args()

    if args.verbosity >= 2:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbosity == 1:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    if not args.assocfile:
        if not args.taxon or not args.category:
            raise ValueError("Must specify EITHER assocfile OR both taxon and category")
            
        
    logging.info("Welcome!")

    if args.yamlconfig is not None:
        logging.info("Setting config from: {}".format(args.yamlconfig))
        # note this sets a global:
        # we would not do this outside the context of a standalone script
        from ontobio.config import set_config
        set_config(args.yamlconfig)


    handle = args.resource

    # Ontology Factory
    ofactory = OntologyFactory()
    logging.info("Creating ont object from: {} {}".format(handle, ofactory))
    ont = ofactory.create(handle)
    logging.info("ont: {}".format(ont))

    evidence = args.evidence
    if evidence is not None and evidence.lower() == 'noiea':
        evidence = "-{}".format(iea_eco)


    # Association Factory
    afactory = AssociationSetFactory()
    aset = None
    if args.assocfile is not None:
        aset = afactory.create_from_file(file=args.assocfile,
                                         fmt=args.assocformat,
                                         ontology=ont)
    else:
        [subject_category, object_category] = args.category
        # create using GO/Monarch services
        aset = afactory.create(ontology=ont,
                               subject_category=subject_category,
                               object_category=object_category,
                               taxon=args.taxon)


    func = args.function
    func(ont, aset, args)

def extract_ontology(ont, aset, args):
    ont = aset.subontology(minimal=args.minimal)
    w = GraphRenderer.create('obo')
    w.outfile = args.outfile
    w.write(ont)

    
def run_enrichment_test(ont, aset, args):
    """
    Runs aset.enrichment_test, printing results
    """
    subjects = args.sample_ids
    background = None
    if args.sample_file is not None:
        subjects = read_ids_from_file(args.sample_file)
    if args.background_file is not None:
        subjects = read_ids_from_file(args.background_file)
    if args.query is not None:
        subjects = aset.query([args.query])
    print("SUBJECTS q={} : {}".format(args.query, subjects))
    enr = aset.enrichment_test(subjects=subjects, background=background, hypotheses=args.hypotheses, threshold=args.threshold, labels=True)
    print('ENRICHED_TERMS={}'.format(len(enr)))
    for r in enr:
        print("{:8.3g} {} {:40s}".format(r['p'],r['c'],str(r['n'])))

def run_phenolog(ont, aset, args):
    """
    Like run_enrichment_test, but uses classes from a 2nd ontology/assocset to build the gene set.
    """
    ofactory = OntologyFactory()
    ont2 = ofactory.create(args.resource2)

    afactory = AssociationSetFactory()
    aset2 = afactory.create(ontology=ont2,
                            file=args.file2)

    # only test for genes (or other subjects of statements) in common
    common = set(aset.subjects).intersection(aset2.subjects)
    num_common = len(common)
    logging.info("Genes in common between two KBs: {}/\{} = {}".format(len(aset.subjects), len(aset2.subjects), num_common))
    if num_common < 2:
        logging.error("TOO FEW")
        return None
    for n in aset.ontology.nodes():
        nl = ont.label(n, id_if_null=True)
        genes = aset.query([n])
        num_genes = len(genes)
        if num_genes > 2:
            logging.info("BASE: {} {} num={}".format(n,nl, num_genes))
            enr = aset2.enrichment_test(subjects=genes, background=aset2.subjects, labels=True)
            for r in enr:
                print("{:8.3g} {} {:20s} <-> {} {:20s}".format(r['p'],n,nl,r['c'],str(r['n'])))


def run_query(ont, aset, args):
    """
    Basic querying by positive/negative class lists
    """
    subjects = aset.query(args.query, args.negative)
    for s in subjects:
        print("{} {}".format(s, str(aset.label(s))))

    if args.plot:
        import plotly.plotly as py
        import plotly.graph_objs as go
        tups = aset.query_associations(subjects=subjects)
        z, xaxis, yaxis = tuple_to_matrix(tups)
        spacechar = " "
        xaxis = mk_axis(xaxis, aset, args, spacechar=" ")
        yaxis = mk_axis(yaxis, aset, args, spacechar=" ")
        logging.info("PLOTTING: {} x {} = {}".format(xaxis, yaxis, z))
        trace = go.Heatmap(z=z,
                           x=xaxis,
                           y=yaxis)
        data=[trace]
        py.plot(data, filename='labelled-heatmap')

def run_query_associations(ont, aset, args):
    if args.dendrogram:
        plot_subject_term_matrix(ont, aset, args)
        return
    import plotly.plotly as py
    import plotly.graph_objs as go
    tups = aset.query_associations(subjects=args.subjects)
    for (s,c) in tups:
        print("{} {}".format(s, c))
    z, xaxis, yaxis = tuple_to_matrix(tups)
    xaxis = mk_axis(xaxis, aset, args)
    yaxis = mk_axis(yaxis, aset, args)
    logging.info("PLOTTING: {} x {} = {}".format(xaxis, yaxis, z))
    trace = go.Heatmap(z=z,
                       x=xaxis,
                       y=yaxis)
    data=[trace]
    py.plot(data, filename='labelled-heatmap')
    #plot_dendrogram(z, xaxis, yaxis)
    
# TODO: fix this really dumb implementation
def tuple_to_matrix(tups):
    import numpy as np
    xset = set()
    yset = set()
    for (x,y) in tups:
        xset.add(x)
        yset.add(y)

    xset = list(xset)
    yset = list(yset)
    xmap = {}
    xi = 0
    for x in xset:
        xmap[x] = xi
        xi = xi+1

    ymap = {}
    yi = 0
    for y in yset:
        ymap[y] = yi
        yi = yi+1

    logging.info("Making {} x {}".format(len(xset), len(yset)))
    z = [ [0] * len(xset) for i1 in range(len(yset)) ]

    for (x,y) in tups:
        z[ymap[y]][xmap[x]] = 1
    z = np.array(z)
    #z = -z
    return (z, xset, yset)


def create_intersection_matrix(ont, aset, args):
    xterms = args.xterms
    yterms = args.yterms
    if args.terms is not None and len(args.terms) > 0:
        xterms = args.terms
    if yterms is None or len(yterms) == 0:
        yterms = xterms
    logging.info("X={} Y={}".format(xterms,yterms))
    ilist = aset.query_intersections(x_terms=xterms, y_terms=yterms)
    z, xaxis, yaxis = aset.intersectionlist_to_matrix(ilist, xterms, yterms)
    xaxis = mk_axis(xaxis, aset, args)
    yaxis = mk_axis(yaxis, aset, args)
    return (z, xaxis, yaxis)

def plot_intersections(ont, aset, args):
    import plotly.plotly as py
    import plotly.graph_objs as go
    (z, xaxis, yaxis) = create_intersection_matrix(ont, aset, args)
    trace = go.Heatmap(z=z,
                       x=xaxis,
                       y=yaxis)
    data=[trace]
    py.plot(data, filename='labelled-heatmap')

def plot_simmatrix(ont, aset, args):
    import numpy as np
    xsubjects = args.xsubjects
    ysubjects = args.ysubjects
    if args.subjects is not None and len(args.subjects) > 0:
        xsubjects = args.subjects
    if ysubjects is None or len(ysubjects) == 0:
        ysubjects = xsubjects
    (z, xaxis, yaxis) = aset.similarity_matrix(xsubjects, ysubjects)
    xaxis = mk_axis(xaxis, aset, args)
    yaxis = mk_axis(yaxis, aset, args)
    z = np.array(z)
    z = -z
    print("Z={}".format(z))
    logging.info("PLOTTING: {} x {} = {}".format(xaxis, yaxis, z))
    plot_dendrogram(z, xaxis, yaxis)

def plot_subject_term_matrix(ont, aset, args):
    import numpy as np
    import pandas as pd
    import scipy.cluster.hierarchy as sch
    import scipy.spatial as scs
    df = aset.as_dataframe(subjects=args.subjects)
    print('DF={}'.format(df))
    d = scs.distance.pdist(df)
    Z = sch.linkage(d, method='complete')
    P = sch.dendrogram(Z)
    print(P)

def old_plot_subject_term_matrix(ont, aset, args):
    import plotly.plotly as py
    import plotly.graph_objs as go
    tups = aset.query_associations(subjects=args.subjects)
    for (s,c) in tups:
        print("{} {}".format(s, c))
    z, xaxis, yaxis = tuple_to_matrix(tups)
    xaxis = mk_axis(xaxis, aset, args)
    yaxis = mk_axis(yaxis, aset, args)
    logging.info('z={}'.format(z))
    logging.info("PLOTTING: {} x {} = {}".format(xaxis, yaxis, z))
    plot_dendrogram(z, xaxis, yaxis)
    
def plot_term_intersection_dendrogram(ont, aset, args):
    import numpy as np
    # TODO: currently only works for xaxis=yaxis
    (z, xaxis, yaxis) = create_intersection_matrix(ont, aset, args)
    z = np.array(z)
    z = -z
    print("Z={}".format(z))
    plot_dendrogram(z, xaxis, yaxis)

def plot_dendrogram(z, xaxis, yaxis):
    import plotly.plotly as py
    import plotly.figure_factory as FF
    import plotly.graph_objs as go
    import numpy as np
    from scipy.cluster.hierarchy import linkage
    from scipy.spatial.distance import pdist, squareform


    # Initialize figure by creating upper dendrogram
    figure = FF.create_dendrogram(z, orientation='bottom', labels=xaxis)
    for i in range(len(figure['data'])):
        figure['data'][i]['yaxis'] = 'y2'

    # Create Side Dendrogram
    # TODO: figure out how to create labels for this axis
    dendro_side = FF.create_dendrogram(z, orientation='right', labels=xaxis)
    for i in range(len(dendro_side['data'])):
        dendro_side['data'][i]['xaxis'] = 'x2'

    # Add Side Dendrogram Data to Figure
    figure['data'].extend(dendro_side['data'])

    # Create Heatmap
    dendro_leaves = dendro_side['layout']['yaxis']['ticktext']
    #dendro_leaves = list(map(int, dendro_leaves))
    data_dist = pdist(z)
    heat_data = squareform(data_dist)
    #heat_data = heat_data[dendro_leaves,:]
    #heat_data = heat_data[:,dendro_leaves]

    heatmap = go.Data([
        go.Heatmap(
            x = dendro_leaves,
            y = dendro_leaves,
            z = heat_data,
            colorscale = 'YIGnBu'
        )
    ])
    heatmap[0]['x'] = figure['layout']['xaxis']['tickvals']
    heatmap[0]['y'] = dendro_side['layout']['yaxis']['tickvals']

    # Add Heatmap Data to Figure
    figure['data'].extend(go.Data(heatmap))

    # Edit Layout
    figure['layout'].update({'width':800, 'height':800,
                         'showlegend':False, 'hovermode': 'closest',
                         })
    # Edit xaxis
    figure['layout']['xaxis'].update({'domain': [.15, 1],
                                  'mirror': False,
                                  'showgrid': False,
                                  'showline': False,
                                  'zeroline': False,
                                  'ticks':""})
    # Edit xaxis2
    figure['layout'].update({'xaxis2': {'domain': [0, .15],
                                   'mirror': False,
                                   'showgrid': False,
                                   'showline': False,
                                   'zeroline': False,
                                   'showticklabels': False,
                                   'ticks':""}})

    # Edit yaxis
    figure['layout']['yaxis'].update({'domain': [0, .85],
                                  'mirror': False,
                                  'showgrid': False,
                                  'showline': False,
                                  'zeroline': False,
                                  'showticklabels': False,
                                  'ticks': ""})
    # Edit yaxis2
    figure['layout'].update({'yaxis2':{'domain':[.825, .975],
                                   'mirror': False,
                                   'showgrid': False,
                                   'showline': False,
                                   'zeroline': False,
                                   'showticklabels': False,
                                   'ticks':""}})

    py.plot(figure, filename='dendrogram_with_labels')

def mk_axis(terms, kb, args, spacechar="<br>"):
    # TODO - more elegant solution to blank node hack
    return [label_or_id(x, kb).replace(" ",spacechar).replace("some variant of ","") for x in terms]

def label_or_id(x, kb):
    label = kb.label(x)
    if label is None:
        return x
    else:
        return label

def read_ids_from_file(fn):
    f = open(fn, 'r')
    ids = [id.strip() for id in f.readlines()]
    f.close()
    return ids
    
if __name__ == "__main__":
    main()
