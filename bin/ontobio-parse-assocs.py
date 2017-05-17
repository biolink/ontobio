#!/usr/bin/env python

"""
Command line wrapper to gafparser.py

Type:

    ogr-parse-assocs -h

For instructions

Examples:

```
```

"""

import argparse
import networkx as nx
from networkx.algorithms.dag import ancestors, descendants
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory
from ontobio.io.gafparser import GafParser
from ontobio.slimmer import get_minimal_subgraph
import logging

def main():
    """
    Wrapper for Assoc Parsing
    """
    parser = argparse.ArgumentParser(description='Wrapper for obographs assocmodel library'
                                                 """
                                                 By default, ontologies and assocs are cached locally and synced from a remote sparql endpoint
                                                 """,
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('-r', '--resource', type=str, required=False,
                        help='Name of ontology')
    parser.add_argument('-f', '--file', type=str, required=False,
                        help='Name of input file for associations - currently GAF is assumed')
    parser.add_argument('-o', '--outfile', type=str, required=False,
                        help='Path to output file')
    parser.add_argument('-m', '--messagefile', type=str, required=False,
                        help='Path to messages (report) markdown file')
    parser.add_argument('-t', '--to', type=str, required=False,
                        help='Output to (tree, dot, ...)')
    parser.add_argument('-T', '--taxon', nargs='*', required=False,
                        help='valid taxon (NCBITaxon ID) - validate against this')
    parser.add_argument('--subject_prefix', nargs='*', required=False,
                        help='E.g PomBase - validate against this')
    parser.add_argument('--object_prefix', nargs='*', required=False,
                        help='E.g GO - validate against this')
    parser.add_argument('-v', '--verbosity', default=0, action='count',
                        help='Increase output verbosity')

    subparsers = parser.add_subparsers(dest='subcommand', help='sub-command help')
    
    parser_n = subparsers.add_parser('validate', help='Validate associations')
    parser_n.set_defaults(function=validate_assocs)

    parser_n = subparsers.add_parser('filter', help='Filter associations')
    parser_n.set_defaults(function=filter_assocs)

    parser_n = subparsers.add_parser('map2slim', help='Map to a subset/slim')
    parser_n.set_defaults(function=map2slim)
    parser_n.add_argument('-p', '--properties', nargs='*', type=str, required=False,
                          help='Properties')
    parser_n.add_argument('-s', '--subset', type=str, required=True,
                          help='subset (e.g. map2slim)')
    
    args = parser.parse_args()

    if args.verbosity >= 2:
        logging.basicConfig(level=logging.DEBUG)
    if args.verbosity == 1:
        logging.basicConfig(level=logging.INFO)
    logging.info("Welcome!")
    
    handle = args.resource

    # Ontology Factory
    ofactory = OntologyFactory()
    logging.info("Creating ont object from: {} {}".format(handle, ofactory))
    ont = ofactory.create(handle)
    logging.info("ont: {}".format(ont))

    func = args.function
    p = GafParser()

    # set configuration
    config = p.config
    config.valid_taxa = args.taxon
    config.class_idspaces = args.object_prefix
    config.entity_idspaces = args.subject_prefix
    
    outfh = None
    if args.outfile is not None:
        outfh = open(args.outfile, "w")
    func(ont, args.file, outfh,  p, args)
    if outfh is not None:
        outfh.close()
    if args.messagefile is not None:
        mfh = open(args.messagefile, "w")
        mfh.write(p.report.to_markdown())
        mfh.close()
    else:
        print(p.report.to_markdown())
        
def filter_assocs(ont, file, outfile, p, args):
    assocs = p.parse(open(file, "r"), outfile)

def validate_assocs(ont, file, outfile, p, args):
    assocs = p.parse(open(file, "r"), outfile)

def map2slim(ont, file, outfile, p, args):
    assocs = p.map_to_subset(open(file, "r"),
                             ontology=ont, outfile=outfile, subset=args.subset, relations=args.properties)
    


    


if __name__ == "__main__":
    main()
