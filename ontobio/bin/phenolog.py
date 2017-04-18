#!/usr/bin/env python

"""
Command line wrapper to obographs library.

Example:
(venv) ~/repos/biolink-api(master) $ python obographs/bin/phenolog.py -vvv -r obo:mp -R go 'abnormal cardiovascular system physiology'

With background:
python obographs/bin/phenolog.py -b 'nervous system phenotype' -v -r cache/ontologies/monarch.json -R go 'abnormal nervous system morphology'



"""

import argparse
import networkx as nx
from networkx.algorithms.dag import ancestors, descendants
from ontobio.ontol_factory import OntologyFactory
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.graph_io import GraphRenderer
from ontobio.slimmer import get_minimal_subgraph
import logging
import sys

def main():
    """
    Phenologs
    """
    parser = argparse.ArgumentParser(description='Phenologs'
                                                 """
                                                 By default, ontologies are cached locally and synced from a remote sparql endpoint
                                                 """,
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-r', '--resource1', type=str, required=False,
                        help='Name of ontology1')
    parser.add_argument('-R', '--resource2', type=str, required=False,
                        help='Name of ontology2')
    parser.add_argument('-T', '--taxon', type=str, default='NCBITaxon:10090', required=False,
                        help='NCBITaxon ID')
    parser.add_argument('-s', '--search', type=str, default='', required=False,
                        help='Search type. p=partial, r=regex')
    parser.add_argument('-b', '--background', type=str, default=None, required=False,
                        help='Class to use for background')
    parser.add_argument('-p', '--pthreshold', type=float, default=0.05, required=False,
                        help='P-value threshold')
    parser.add_argument('-v', '--verbosity', default=0, action='count',
                        help='Increase output verbosity')

    parser.add_argument('ids',nargs='*')

    args = parser.parse_args()

    if args.verbosity >= 2:
        logging.basicConfig(level=logging.DEBUG)
    if args.verbosity == 1:
        logging.basicConfig(level=logging.INFO)
    logging.info("Welcome!")

    ofactory = OntologyFactory()
    afactory = AssociationSetFactory()
    handle = args.resource1
    ont1 = ofactory.create(args.resource1)
    ont2 = ofactory.create(args.resource2)
    logging.info("onts: {} {}".format(ont1, ont2))
    searchp = args.search

    category = 'gene'

    aset1 = afactory.create(ontology=ont1,
                            subject_category=category,
                            object_category='phenotype',
                            taxon=args.taxon)
    aset2 = afactory.create(ontology=ont2,
                            subject_category=category,
                            object_category='function',
                            taxon=args.taxon)

    bg_cls = None
    if args.background is not None:
        bg_ids = resolve(ont1,[args.background],searchp)
        if len(bg_ids) == 0:
            logging.error("Cannnot resolve: '{}' using {} in {}".format(args.background, searchp, ont1))
            sys.exit(1)
        elif len(bg_ids) > 1:
            logging.error("Multiple matches: '{}' using {} MATCHES={}".format(args.background, searchp,bg_ids))
            sys.exit(1)
        else:
            logging.info("Background: {}".format(bg_cls))
            [bg_cls] = bg_ids
    
    for id in resolve(ont1,args.ids,searchp):

        sample = aset1.query([id],[])
        print("Gene set class:{} Gene set: {}".format(id, sample))
        bg = None
        if bg_cls is not None:
            bg = aset1.query([bg_cls],[])
            print("BACKGROUND SUBJECTS: {}".format(bg))

        rs = aset2.enrichment_test(sample, bg, threshold=args.pthreshold, labels=True)
        print("RESULTS: {} < {}".format(len(rs), args.pthreshold))
        for r in rs:
            print(str(r))

def resolve(ont, names, searchp):
    return ont.resolve_names(names,
                              is_remote = searchp.find('x') > -1,
                              is_partial_match = searchp.find('p') > -1,
                              is_regex = searchp.find('r') > -1)
    

    
if __name__ == "__main__":
    main()
